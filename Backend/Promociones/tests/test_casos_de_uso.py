"""Pruebas de los casos de uso de Promociones, sin base de datos."""
import unittest
from datetime import datetime

from Domain.entities import Promocion, ProductoEnPromocion
from Application.promocion_use_cases import (
    PromocionRepository, GestionarPromociones, NoEncontradoError, DatosInvalidosError, UsuarioRepository, RevisarPermisos, PermisoDenegadoError,
)

PRODUCTOS = {1: ("Balatas", 650.0), 2: ("Disco", 890.0)}
HOY = datetime(2026, 10, 15, 12, 0)     # fecha fija para que las pruebas no dependan del día

class PromocionesFalsas(PromocionRepository):
    def __init__(self):
        self.datos = {}
        self.relaciones = set()   # (id_promocion, id_producto)

    def find_all(self, solo_vigentes, ahora):
        return [p for p in self.datos.values()
                if not solo_vigentes or (p.activa and p.fecha_inicio <= ahora <= p.fecha_fin)]
    
    def find_by_id(self, id_promocion):
        promo = self.datos.get(id_promocion)
        if promo:
            promo.productos = [ProductoEnPromocion(i, *PRODUCTOS[i], promo.descuento)
                               for (p, i) in sorted(self.relaciones) if p == id_promocion]
        return promo

    def save(self, promocion, ids_productos):
        promocion.id = len(self.datos) + 1
        self.datos[promocion.id] = promocion
        self.relaciones |= {(promocion.id, i) for i in ids_productos}
        return promocion

    def update(self, promocion, ids_productos=None):
        if promocion.id not in self.datos:
            return False
        self.datos[promocion.id] = promocion
        if ids_productos is not None:
            self.relaciones = {(p, i) for (p, i) in self.relaciones if p != promocion.id}
            self.relaciones |= {(promocion.id, i) for i in ids_productos}
        return True

    def delete(self, id_promocion):
        return self.datos.pop(id_promocion, None) is not None

    def delete_vencidas(self, ahora):
        vencidas = [i for i, p in self.datos.items() if p.fecha_fin < ahora]
        for i in vencidas:
            del self.datos[i]
        return len(vencidas)

    def producto_existe(self, id_producto):
        return id_producto in PRODUCTOS

    def add_producto(self, id_promocion, id_producto):
        if (id_promocion, id_producto) in self.relaciones:
            return False
        self.relaciones.add((id_promocion, id_producto))
        return True

    def remove_producto(self, id_promocion, id_producto):
        if (id_promocion, id_producto) not in self.relaciones:
            return False
        self.relaciones.remove((id_promocion, id_producto))
        return True

def promocion(inicio="2026-10-15", fin="2026-10-31", descuento=15):
    return Promocion(nombre="Mes de los frenos", descuento=descuento,
                     fecha_inicio=datetime.fromisoformat(inicio), fecha_fin=datetime.fromisoformat(fin))

class PruebasPromociones(unittest.TestCase):
    def setUp(self):
        self.repo = PromocionesFalsas()
        self.casos = GestionarPromociones(promocion_repository=self.repo, ahora=lambda: HOY)

    def test_precio_con_descuento(self):
        self.assertEqual(ProductoEnPromocion(1, "Balatas", 650.0, 15).precio_con_descuento, 552.5)
        self.assertEqual(ProductoEnPromocion(2, "Disco", 890.0, 15).precio_con_descuento, 756.5)

    def test_crear_promocion_valida(self):
        self.assertEqual(self.casos.crear(promocion()).id, 1)

    def test_no_crea_promocion_con_fechas_al_reves(self):
        with self.assertRaises(DatosInvalidosError):
            self.casos.crear(promocion(inicio="2026-12-01", fin="2026-10-01"))
        self.assertEqual(self.repo.datos, {})

    def test_no_actualiza_con_fechas_al_reves(self):
        creada = self.casos.crear(promocion())
        cambio = promocion(inicio="2026-12-01", fin="2026-10-01")
        cambio.id = creada.id
        with self.assertRaises(DatosInvalidosError):
            self.casos.actualizar(cambio)

    def test_agregar_producto_y_calcular_su_descuento(self):
        creada = self.casos.crear(promocion())
        resultado = self.casos.agregar_producto(creada.id, 1)
        self.assertEqual([(p.nombre, p.precio_con_descuento) for p in resultado.productos], [("Balatas", 552.5)])

    def test_no_agrega_el_mismo_producto_dos_veces(self):
        creada = self.casos.crear(promocion())
        self.casos.agregar_producto(creada.id, 1)
        with self.assertRaises(DatosInvalidosError):
            self.casos.agregar_producto(creada.id, 1)

    def test_no_agrega_a_promocion_o_producto_que_no_existe(self):
        creada = self.casos.crear(promocion())
        with self.assertRaises(NoEncontradoError):
            self.casos.agregar_producto(999, 1)
        with self.assertRaises(NoEncontradoError):
            self.casos.agregar_producto(creada.id, 999)

    def test_crear_con_productos_de_una_vez(self):
        creada = self.casos.crear(promocion(), [1, 2])
        self.assertEqual([p.nombre for p in creada.productos], ["Balatas", "Disco"])

    def test_no_crea_nada_si_un_producto_no_existe(self):
        with self.assertRaises(NoEncontradoError):
            self.casos.crear(promocion(), [1, 999])
        self.assertEqual(self.repo.datos, {})   # no quedó una promoción a medias

    def test_no_crea_promocion_que_ya_vencio(self):
        with self.assertRaises(DatosInvalidosError):
            self.casos.crear(promocion(inicio="2026-09-01", fin="2026-09-30"))

    def test_no_crea_promocion_que_empieza_en_un_dia_pasado(self):
        with self.assertRaises(DatosInvalidosError):
            self.casos.crear(promocion(inicio="2026-10-14", fin="2026-10-31"))   # ayer
        self.assertEqual(self.repo.datos, {})
        self.assertEqual(self.casos.crear(promocion(inicio="2026-10-15", fin="2026-10-31")).id, 1)   # hoy sí

    def test_al_editar_no_se_mueve_el_inicio_a_un_dia_pasado(self):
        ya_empezo = promocion(inicio="2026-10-01", fin="2026-10-31")
        self.repo.save(ya_empezo, [])   # se guarda directo, como si se hubiera creado el día 1
        cambio = promocion(inicio="2026-10-01", fin="2026-11-15", descuento=20)
        cambio.id = ya_empezo.id
        self.assertEqual(self.casos.actualizar(cambio).descuento, 20)   # puede dejar su inicio como estaba
        cambio = promocion(inicio="2026-10-05", fin="2026-11-15")
        cambio.id = ya_empezo.id
        with self.assertRaises(DatosInvalidosError):
            self.casos.actualizar(cambio)   # pero no moverlo a otro día pasado

    def test_las_vencidas_se_borran_al_listar(self):
        vigente = self.casos.crear(promocion(inicio="2026-10-15", fin="2026-10-31"))
        termina_hoy = self.casos.crear(promocion(inicio="2026-10-15", fin="2026-10-15T23:59:59"))
        vencida = promocion(inicio="2026-09-01", fin="2026-09-30")
        self.repo.save(vencida, [])   # se guarda directo, como si se hubiera creado el mes pasado
        ids = [p.id for p in self.casos.listar()]
        self.assertEqual(ids, [vigente.id, termina_hoy.id])
        self.assertNotIn(vencida.id, self.repo.datos)   # se borró de verdad

    def test_vigentes_son_las_que_van_hoy(self):
        actual = self.casos.crear(promocion(inicio="2026-10-15", fin="2026-10-31"))
        self.casos.crear(promocion(inicio="2026-11-01", fin="2026-11-30"))   # todavía no empieza
        self.assertEqual([p.id for p in self.casos.listar(solo_vigentes=True)], [actual.id])

    def test_quitar_producto_que_no_esta_lanza_error(self):
        creada = self.casos.crear(promocion())
        with self.assertRaises(NoEncontradoError):
            self.casos.quitar_producto(creada.id, 1)
    
    def test_editar_cambia_datos_y_productos(self):
        creada = self.casos.crear(promocion(), [1])
        cambio = promocion(descuento=25)
        cambio.id = creada.id
        editada = self.casos.actualizar(cambio, [2])
        self.assertEqual(editada.descuento, 25)
        self.assertEqual([p.nombre for p in editada.productos], ["Disco"])   # se quitó Balatas y entró Disco

    def test_editar_sin_productos_deja_los_que_tenia(self):
        creada = self.casos.crear(promocion(), [1, 2])
        cambio = promocion(descuento=30)
        cambio.id = creada.id
        self.assertEqual(len(self.casos.actualizar(cambio).productos), 2)

    def test_no_edita_promocion_que_no_existe_ni_con_producto_que_no_existe(self):
        cambio = promocion()
        cambio.id = 999
        with self.assertRaises(NoEncontradoError):
            self.casos.actualizar(cambio)
        creada = self.casos.crear(promocion(), [1])
        cambio.id = creada.id
        with self.assertRaises(NoEncontradoError):
            self.casos.actualizar(cambio, [1, 999])
        self.assertEqual([p.id for p in self.casos.obtener(creada.id).productos], [1])   # no cambió nada

class UsuariosFalsos(UsuarioRepository):
    ROLES = {1: "Administrador", 2: "Empleado", 3: "Almacenista", 4: "Cliente"}

    def rol_de_usuario(self, id_login):
        return self.ROLES.get(id_login)

class PruebasPermisos(unittest.TestCase):
    def setUp(self):
        self.permisos = RevisarPermisos(usuario_repository=UsuariosFalsos())

    def test_el_administrador_puede_hacer_cambios(self):
        self.permisos.solo_administrador(1)   # no lanza error

    def test_los_demas_roles_no_pueden(self):
        for id_login in (2, 3, 4):
            with self.assertRaises(PermisoDenegadoError):
                self.permisos.solo_administrador(id_login)

    def test_usuario_que_no_existe(self):
        with self.assertRaises(PermisoDenegadoError):
            self.permisos.solo_administrador(999)

if __name__ == "__main__":
    unittest.main()

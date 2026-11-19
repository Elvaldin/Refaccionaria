"""Pruebas de los casos de uso de Órdenes, sin base de datos.

Aquí están las reglas más importantes del negocio: estados de la orden,
precios, totales y que una venta no pueda dejar el stock negativo.
"""
import unittest
from datetime import datetime

from Domain.entities import Orden, DetalleOrden
from Application.orden_use_cases import (
    OrdenRepository, ProductoInfo, GestionarOrdenes, NoEncontradoError, DatosInvalidosError, ConflictoError,
    PermisoDenegadoError,
)

ADMIN = 1      # id_login del Administrador en el repositorio falso
EMPLEADO = 2   # id_login del Empleado
CLIENTE = 3    # id_login del Cliente
OTRO_CLIENTE = 4
ALMACENISTA = 5

class OrdenesFalsas(OrdenRepository):
    def __init__(self):
        self.ordenes = {}
        self.stock = {1: ProductoInfo("Balatas", 650.0, 20), 2: ProductoInfo("Batería", 2300.0, 6)}
        self.completadas = []

    def find_all(self, tipo, estado, id_login=None):
        return [o for o in self.ordenes.values() if id_login is None or o.id_login == id_login]

    def find_by_id(self, id_orden):
        return self.ordenes.get(id_orden)

    def save(self, orden):
        orden.id = len(self.ordenes) + 1
        for d in orden.detalles:
            d.producto = self.stock[d.id_producto].nombre
        self.ordenes[orden.id] = orden
        return orden.id

    def rol_de_usuario(self, id_login):
        return {ADMIN: "Administrador", EMPLEADO: "Empleado", ALMACENISTA: "Almacenista",
                CLIENTE: "Cliente", OTRO_CLIENTE: "Cliente"}.get(id_login)

    def find_productos(self, ids):
        return {i: self.stock[i] for i in ids if i in self.stock}

    def update_estado(self, id_orden, estado, estado_actual):
        if getattr(self, "alguien_la_cambio", False):
            return False
        self.ordenes[id_orden].estado = estado
        return True

    def completar(self, orden, fecha):
        self.completadas.append(orden.id)
        self.fecha_movimiento = fecha
        signo = -1 if orden.tipo == "Venta" else 1
        for d in orden.detalles:
            self.stock[d.id_producto].stock += signo * d.cantidad
        orden.estado = "Completada"

    def find_movimientos(self, id_producto):
        return []


def orden(tipo="Venta", *detalles, id_login=ADMIN):
    return Orden(id_login=id_login, tipo=tipo, detalles=list(detalles))


class PruebasOrdenes(unittest.TestCase):
    def setUp(self):
        self.repo = OrdenesFalsas()
        self.casos = GestionarOrdenes(orden_repository=self.repo)

    # ----- Crear -----
    def test_si_no_mandan_precio_usa_el_del_producto_y_calcula_el_total(self):
        creada = self.casos.crear(orden("Venta", DetalleOrden(1, 2), DetalleOrden(2, 1, precio_unitario=2000)))
        self.assertEqual([d.precio_unitario for d in creada.detalles], [650.0, 2000])
        self.assertEqual([d.subtotal for d in creada.detalles], [1300.0, 2000])
        self.assertEqual(creada.total, 3300.0)
        self.assertEqual(creada.estado, "Pendiente")

    def test_no_crea_orden_sin_productos(self):
        with self.assertRaises(DatosInvalidosError):
            self.casos.crear(orden("Venta"))

    def test_no_crea_orden_con_productos_repetidos(self):
        with self.assertRaises(DatosInvalidosError):
            self.casos.crear(orden("Venta", DetalleOrden(1, 1), DetalleOrden(1, 2)))

    def test_no_crea_orden_si_el_usuario_o_el_producto_no_existen(self):
        with self.assertRaises(NoEncontradoError):
            self.casos.crear(orden("Venta", DetalleOrden(1, 1), id_login=999))
        with self.assertRaises(NoEncontradoError):
            self.casos.crear(orden("Venta", DetalleOrden(999, 1)))

    # ----- Estados -----
    def test_pendiente_a_en_proceso(self):
        creada = self.casos.crear(orden("Venta", DetalleOrden(1, 1)))
        self.assertEqual(self.casos.cambiar_estado(creada.id, "En Proceso", ADMIN).estado, "En Proceso")
        self.assertEqual(self.repo.completadas, [])   # todavía no mueve el inventario

    def test_completada_y_cancelada_son_estados_finales(self):
        a = self.casos.crear(orden("Venta", DetalleOrden(1, 1)))
        self.casos.cambiar_estado(a.id, "Completada", ADMIN)
        with self.assertRaises(ConflictoError):
            self.casos.cambiar_estado(a.id, "Pendiente", ADMIN)

        b = self.casos.crear(orden("Venta", DetalleOrden(1, 1)))
        self.casos.cambiar_estado(b.id, "Cancelada", ADMIN)
        with self.assertRaises(ConflictoError):
            self.casos.cambiar_estado(b.id, "Completada", ADMIN)

    def test_no_cambia_el_estado_si_alguien_mas_lo_cambio_antes(self):
        # Ej. el Administrador cancela justo cuando un Empleado ya la completó
        creada = self.casos.crear(orden("Venta", DetalleOrden(1, 2)))
        self.repo.alguien_la_cambio = True
        with self.assertRaises(ConflictoError):
            self.casos.cambiar_estado(creada.id, "Cancelada", ADMIN)

    def test_cancelar_no_mueve_el_inventario(self):
        creada = self.casos.crear(orden("Venta", DetalleOrden(1, 5)))
        self.casos.cambiar_estado(creada.id, "Cancelada", ADMIN)
        self.assertEqual(self.repo.stock[1].stock, 20)

    # ----- Inventario -----
    def test_completar_venta_resta_stock(self):
        creada = self.casos.crear(orden("Venta", DetalleOrden(1, 2)))
        self.casos.cambiar_estado(creada.id, "Completada", ADMIN)
        self.assertEqual(self.repo.stock[1].stock, 18)

    def test_completar_compra_suma_stock(self):
        creada = self.casos.crear(orden("Compra", DetalleOrden(2, 4, precio_unitario=1500)))
        self.casos.cambiar_estado(creada.id, "Completada", ADMIN)
        self.assertEqual(self.repo.stock[2].stock, 10)

    def test_venta_sin_stock_suficiente_no_se_completa(self):
        creada = self.casos.crear(orden("Venta", DetalleOrden(2, 999)))
        with self.assertRaises(ConflictoError) as error:
            self.casos.cambiar_estado(creada.id, "Completada", ADMIN)
        self.assertIn("hay 6 y se piden 999", str(error.exception))
        self.assertEqual(self.repo.completadas, [])
        self.assertEqual(self.repo.stock[2].stock, 6)
        self.assertEqual(self.repo.ordenes[creada.id].estado, "Pendiente")

    # ----- Roles -----
    def test_empleado_puede_crear_ventas(self):
        creada = self.casos.crear(orden("Venta", DetalleOrden(1, 1), id_login=EMPLEADO))
        self.assertEqual(creada.estado, "Pendiente")

    def test_empleado_no_puede_registrar_compras(self):
        with self.assertRaises(PermisoDenegadoError):
            self.casos.crear(orden("Compra", DetalleOrden(2, 4, precio_unitario=1500), id_login=EMPLEADO))
        self.assertEqual(self.repo.ordenes, {})   # no se guardó nada

    def test_administrador_puede_registrar_compras(self):
        creada = self.casos.crear(orden("Compra", DetalleOrden(2, 4, precio_unitario=1500), id_login=ADMIN))
        self.assertEqual(creada.tipo, "Compra")

    def test_empleado_puede_avanzar_y_completar(self):
        creada = self.casos.crear(orden("Venta", DetalleOrden(1, 2), id_login=EMPLEADO))
        self.casos.cambiar_estado(creada.id, "En Proceso", EMPLEADO)
        self.assertEqual(self.casos.cambiar_estado(creada.id, "Completada", EMPLEADO).estado, "Completada")
        self.assertEqual(self.repo.stock[1].stock, 18)

    def test_empleado_no_puede_cancelar(self):
        creada = self.casos.crear(orden("Venta", DetalleOrden(1, 1), id_login=EMPLEADO))
        with self.assertRaises(PermisoDenegadoError):
            self.casos.cambiar_estado(creada.id, "Cancelada", EMPLEADO)
        self.assertEqual(self.repo.ordenes[creada.id].estado, "Pendiente")

    def test_administrador_puede_cancelar(self):
        creada = self.casos.crear(orden("Venta", DetalleOrden(1, 1), id_login=EMPLEADO))
        self.assertEqual(self.casos.cambiar_estado(creada.id, "Cancelada", ADMIN).estado, "Cancelada")

    def test_almacenista_registra_y_completa_compras(self):
        creada = self.casos.crear(orden("Compra", DetalleOrden(2, 4, precio_unitario=1500), id_login=ALMACENISTA))
        self.casos.cambiar_estado(creada.id, "En Proceso", ALMACENISTA)
        self.assertEqual(self.casos.cambiar_estado(creada.id, "Completada", ALMACENISTA).estado, "Completada")
        self.assertEqual(self.repo.stock[2].stock, 10)

    def test_almacenista_no_hace_ventas_ni_las_avanza(self):
        with self.assertRaises(PermisoDenegadoError):
            self.casos.crear(orden("Venta", DetalleOrden(1, 1), id_login=ALMACENISTA))
        venta = self.casos.crear(orden("Venta", DetalleOrden(1, 1), id_login=EMPLEADO))
        with self.assertRaises(PermisoDenegadoError):
            self.casos.cambiar_estado(venta.id, "Completada", ALMACENISTA)
        self.assertEqual(self.repo.stock[1].stock, 20)

    def test_empleado_no_avanza_compras(self):
        compra = self.casos.crear(orden("Compra", DetalleOrden(2, 4, precio_unitario=1500), id_login=ALMACENISTA))
        with self.assertRaises(PermisoDenegadoError):
            self.casos.cambiar_estado(compra.id, "Completada", EMPLEADO)
        self.assertEqual(self.repo.stock[2].stock, 6)

    def test_almacenista_no_puede_cancelar(self):
        compra = self.casos.crear(orden("Compra", DetalleOrden(2, 1, precio_unitario=1500), id_login=ALMACENISTA))
        with self.assertRaises(PermisoDenegadoError):
            self.casos.cambiar_estado(compra.id, "Cancelada", ALMACENISTA)

    def test_cliente_puede_hacer_pedidos(self):
        creada = self.casos.crear(orden("Venta", DetalleOrden(1, 1), id_login=CLIENTE))
        self.assertEqual(creada.estado, "Pendiente")

    def test_cliente_paga_el_precio_de_la_tienda(self):
        creada = self.casos.crear(orden("Venta", DetalleOrden(1, 2, precio_unitario=1), id_login=CLIENTE))
        self.assertEqual(creada.detalles[0].precio_unitario, 650.0)
        self.assertEqual(creada.total, 1300.0)

    def test_el_empleado_cobra_el_precio_de_la_tienda(self):
        # Un Empleado no puede vender a otro precio (ej. a $1 a un conocido)
        creada = self.casos.crear(orden("Venta", DetalleOrden(1, 2, precio_unitario=1), id_login=EMPLEADO))
        self.assertEqual(creada.detalles[0].precio_unitario, 650.0)

    def test_el_administrador_si_puede_dar_un_precio_especial(self):
        creada = self.casos.crear(orden("Venta", DetalleOrden(1, 2, precio_unitario=600), id_login=ADMIN))
        self.assertEqual(creada.detalles[0].precio_unitario, 600)

    def test_la_venta_respeta_la_promocion_vigente(self):
        self.repo.stock[1].descuento = 15   # Balatas está en una promoción del 15%
        creada = self.casos.crear(orden("Venta", DetalleOrden(1, 2), id_login=CLIENTE))
        self.assertEqual(creada.detalles[0].precio_unitario, 552.5)
        self.assertEqual(creada.total, 1105.0)

    def test_la_compra_al_proveedor_no_lleva_descuento(self):
        self.repo.stock[2].descuento = 10
        creada = self.casos.crear(orden("Compra", DetalleOrden(2, 1), id_login=ALMACENISTA))
        self.assertEqual(creada.detalles[0].precio_unitario, 2300.0)

    def test_la_orden_y_sus_movimientos_usan_la_hora_de_la_computadora(self):
        hora_orden = datetime(2026, 11, 2, 22, 38)
        hora_completada = datetime(2026, 11, 3, 9, 15)
        horas = iter([hora_orden, hora_completada])
        casos = GestionarOrdenes(orden_repository=self.repo, ahora=lambda: next(horas))
        creada = casos.crear(orden("Venta", DetalleOrden(1, 1)))
        self.assertEqual(creada.fecha, hora_orden)
        casos.cambiar_estado(creada.id, "En Proceso", ADMIN)    # No gasta hora: solo cambia el estado
        casos.cambiar_estado(creada.id, "Completada", ADMIN)
        self.assertEqual(self.repo.fecha_movimiento, hora_completada)

    def test_cliente_no_puede_registrar_compras(self):
        with self.assertRaises(PermisoDenegadoError):
            self.casos.crear(orden("Compra", DetalleOrden(2, 1, precio_unitario=1500), id_login=CLIENTE))

    def test_cliente_no_puede_cambiar_estados(self):
        creada = self.casos.crear(orden("Venta", DetalleOrden(1, 1), id_login=CLIENTE))
        for estado in ("En Proceso", "Completada", "Cancelada"):
            with self.assertRaises(PermisoDenegadoError):
                self.casos.cambiar_estado(creada.id, estado, CLIENTE)
        self.assertEqual(self.repo.ordenes[creada.id].estado, "Pendiente")
        self.assertEqual(self.repo.stock[1].stock, 20)

    def test_cliente_solo_ve_sus_ordenes(self):
        mia = self.casos.crear(orden("Venta", DetalleOrden(1, 1), id_login=CLIENTE))
        self.casos.crear(orden("Venta", DetalleOrden(1, 1), id_login=OTRO_CLIENTE))
        self.casos.crear(orden("Compra", DetalleOrden(2, 1, precio_unitario=1500), id_login=ADMIN))
        self.assertEqual([o.id for o in self.casos.listar(id_login=CLIENTE)], [mia.id])
        self.assertEqual(len(self.casos.listar(id_login=EMPLEADO)), 3)   # el personal ve todas

    def test_cliente_no_puede_ver_orden_de_otro(self):
        ajena = self.casos.crear(orden("Venta", DetalleOrden(1, 1), id_login=OTRO_CLIENTE))
        with self.assertRaises(PermisoDenegadoError):
            self.casos.obtener(ajena.id, CLIENTE)
        self.assertEqual(self.casos.obtener(ajena.id, OTRO_CLIENTE).id, ajena.id)
        self.assertEqual(self.casos.obtener(ajena.id, EMPLEADO).id, ajena.id)

    def test_cliente_no_puede_ver_movimientos(self):
        with self.assertRaises(PermisoDenegadoError):
            self.casos.movimientos(id_login=CLIENTE)
        self.assertEqual(self.casos.movimientos(id_login=ADMIN), [])

    def test_cambiar_estado_con_usuario_que_no_existe(self):
        creada = self.casos.crear(orden("Venta", DetalleOrden(1, 1)))
        with self.assertRaises(NoEncontradoError):
            self.casos.cambiar_estado(creada.id, "En Proceso", 999)

    def test_obtener_orden_que_no_existe_lanza_error(self):
        with self.assertRaises(NoEncontradoError):
            self.casos.obtener(999, ADMIN)

    def test_consultar_con_usuario_que_no_existe(self):
        # Sin un usuario válido no se ve nada: ni la lista, ni una orden, ni el inventario
        creada = self.casos.crear(orden("Venta", DetalleOrden(1, 1)))
        with self.assertRaises(NoEncontradoError):
            self.casos.listar(999)
        with self.assertRaises(NoEncontradoError):
            self.casos.obtener(creada.id, 999)
        with self.assertRaises(NoEncontradoError):
            self.casos.movimientos(999)


if __name__ == "__main__":
    unittest.main()
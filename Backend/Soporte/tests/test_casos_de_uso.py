"""Pruebas de los casos de uso de Soporte, sin base de datos."""
import unittest
from datetime import datetime

from Domain.entities import Soporte, Conversacion
from Application.soporte_use_cases import (
    SoporteRepository, GestionarSoporte, NoEncontradoError, DatosInvalidosError, ConversacionRepository,
    GestionarConversaciones, PermisoDenegadoError, ConflictoError,
)

class SoporteFalso(SoporteRepository):
    def __init__(self):
        self.datos = {}

    def find_all(self):
        return list(self.datos.values())

    def find_by_id(self, id_soporte):
        return self.datos.get(id_soporte)

    def save(self, soporte):
        soporte.id = len(self.datos) + 1
        self.datos[soporte.id] = soporte
        return soporte

    def update(self, soporte):
        if soporte.id not in self.datos:
            return False
        self.datos[soporte.id] = soporte
        return True

    def delete(self, id_soporte):
        return self.datos.pop(id_soporte, None) is not None


class UsuariosFalsos:
    def rol_de_usuario(self, id_login):
        return {1: "Administrador", 2: "Empleado", 4: "Cliente"}.get(id_login)

ADMIN_SOPORTE = 1

class PruebasSoporte(unittest.TestCase):
    def setUp(self):
        self.repo = SoporteFalso()
        self.casos = GestionarSoporte(soporte_repository=self.repo, usuario_repository=UsuariosFalsos())

    def test_crear_contacto_completo_con_horario(self):
        creado = self.casos.crear(Soporte(correo="ventas@refaccionaria.com", telefono="55 1234 5678",
                                          direccion="Av. Insurgentes 123", horario="Lunes a sábado"), ADMIN_SOPORTE)
        self.assertEqual(self.casos.obtener(creado.id).horario, "Lunes a sábado")

    def test_basta_con_un_dato(self):
        self.assertEqual(self.casos.crear(Soporte(telefono="55 1234 5678"), ADMIN_SOPORTE).id, 1)

    def test_no_crea_contacto_vacio(self):
        with self.assertRaises(DatosInvalidosError):
            self.casos.crear(Soporte(), ADMIN_SOPORTE)

    def test_solo_horario_no_es_suficiente(self):
        with self.assertRaises(DatosInvalidosError):
            self.casos.crear(Soporte(horario="Lunes a sábado"), ADMIN_SOPORTE)

    def test_ver_editar_y_borrar_un_contacto_que_no_existe(self):
        with self.assertRaises(NoEncontradoError):
            self.casos.obtener(999)
        with self.assertRaises(NoEncontradoError):
            self.casos.actualizar(Soporte(correo="a@b.com", id_soporte=999), ADMIN_SOPORTE)
        with self.assertRaises(NoEncontradoError):
            self.casos.eliminar(999, ADMIN_SOPORTE)

    def test_solo_el_administrador_cambia_el_contacto(self):
        creado = self.casos.crear(Soporte(correo="ventas@refaccionaria.com"), ADMIN_SOPORTE)
        for quien in (2, 4):   # Empleado y Cliente
            with self.assertRaises(PermisoDenegadoError):
                self.casos.crear(Soporte(correo="falso@pirata.com"), quien)
            with self.assertRaises(PermisoDenegadoError):
                self.casos.actualizar(Soporte(correo="falso@pirata.com", id_soporte=creado.id), quien)
            with self.assertRaises(PermisoDenegadoError):
                self.casos.eliminar(creado.id, quien)
        with self.assertRaises(NoEncontradoError):
            self.casos.eliminar(creado.id, 999)   # usuario que no existe
        self.assertEqual(self.casos.obtener(creado.id).correo, "ventas@refaccionaria.com")   # no cambió



# ===== Chat de soporte =====
# Usuarios falsos: id → (nombre, rol)
USUARIOS = {1: ("admin", "Administrador"), 2: ("empleado", "Empleado"), 3: ("almacen", "Almacenista"),
            4: ("cliente", "Cliente"), 5: ("otro_cliente", "Cliente")}
ADMIN, EMPLEADO, ALMACEN, CLIENTE, OTRO_CLIENTE = 1, 2, 3, 4, 5
HOY = datetime(2026, 10, 27, 18, 30)


class ConversacionesFalsas(ConversacionRepository):
    def __init__(self):
        self.datos = {}
        self.siguiente_mensaje = 1

    def find_all(self, id_login):
        return [c for c in self.datos.values() if id_login is None or c.id_login == id_login]

    def find_by_id(self, id_conversacion):
        return self.datos.get(id_conversacion)

    def save(self, conversacion):
        conversacion.id = len(self.datos) + 1
        conversacion.cliente = USUARIOS[conversacion.id_login][0]
        self.datos[conversacion.id] = conversacion
        for mensaje in conversacion.mensajes:
            mensaje.id_conversacion = conversacion.id
            self._completar(mensaje)
        return conversacion

    def add_mensaje(self, mensaje):
        self._completar(mensaje)
        self.datos[mensaje.id_conversacion].mensajes.append(mensaje)

    def update_estado(self, id_conversacion, estado):
        self.datos[id_conversacion].estado = estado

    def delete(self, id_conversacion):
        return self.datos.pop(id_conversacion, None) is not None

    def rol_de_usuario(self, id_login):
        return USUARIOS[id_login][1] if id_login in USUARIOS else None

    def _completar(self, mensaje):
        mensaje.id = self.siguiente_mensaje
        self.siguiente_mensaje += 1
        mensaje.autor, mensaje.rol = USUARIOS[mensaje.id_login]


class PruebasChat(unittest.TestCase):
    def setUp(self):
        self.repo = ConversacionesFalsas()
        self.chat = GestionarConversaciones(conversacion_repository=self.repo, ahora=lambda: HOY)

    def test_el_cliente_empieza_una_conversacion(self):
        conversacion = self.chat.crear(CLIENTE, " Garantía ", " Mi batería ya no carga ")
        self.assertEqual((conversacion.asunto, conversacion.estado, conversacion.cliente), ("Garantía", "Abierta", "cliente"))
        self.assertEqual(conversacion.mensajes[0].texto, "Mi batería ya no carga")
        self.assertEqual(conversacion.mensajes[0].fecha, HOY)
        self.assertTrue(conversacion.esperando_respuesta)

    def test_el_personal_no_empieza_conversaciones(self):
        for id_login in (ADMIN, EMPLEADO, ALMACEN):
            with self.assertRaises(PermisoDenegadoError):
                self.chat.crear(id_login, "Hola", "Prueba")

    def test_no_se_mandan_mensajes_vacios(self):
        with self.assertRaises(DatosInvalidosError):
            self.chat.crear(CLIENTE, "Garantía", "   ")
        with self.assertRaises(DatosInvalidosError):
            self.chat.crear(CLIENTE, "   ", "Hola")
        conversacion = self.chat.crear(CLIENTE, "Garantía", "Hola")
        with self.assertRaises(DatosInvalidosError):
            self.chat.responder(conversacion.id, ADMIN, "  ")

    def test_admin_y_empleado_contestan(self):
        conversacion = self.chat.crear(CLIENTE, "Pedido", "¿Ya salió mi pedido?")
        self.chat.responder(conversacion.id, EMPLEADO, "Sale hoy en la tarde")
        conversacion = self.chat.responder(conversacion.id, ADMIN, "Te avisamos al enviarlo")
        self.assertEqual([m.rol for m in conversacion.mensajes], ["Cliente", "Empleado", "Administrador"])
        self.assertFalse(conversacion.esperando_respuesta)   # lo último lo escribió el personal
        conversacion = self.chat.responder(conversacion.id, CLIENTE, "Gracias")
        self.assertTrue(conversacion.esperando_respuesta)

    def test_el_almacenista_no_atiende_el_chat(self):
        conversacion = self.chat.crear(CLIENTE, "Pedido", "Hola")
        with self.assertRaises(PermisoDenegadoError):
            self.chat.listar(ALMACEN)
        with self.assertRaises(PermisoDenegadoError):
            self.chat.responder(conversacion.id, ALMACEN, "Hola")

    def test_cada_cliente_ve_solo_las_suyas_y_el_personal_ve_todas(self):
        mia = self.chat.crear(CLIENTE, "Pedido", "Hola")
        ajena = self.chat.crear(OTRO_CLIENTE, "Garantía", "Hola")
        self.assertEqual([c.id for c in self.chat.listar(CLIENTE)], [mia.id])
        self.assertEqual(len(self.chat.listar(EMPLEADO)), 2)
        with self.assertRaises(PermisoDenegadoError):
            self.chat.obtener(ajena.id, CLIENTE)
        with self.assertRaises(PermisoDenegadoError):
            self.chat.responder(ajena.id, CLIENTE, "Me meto en otra conversación")

    def test_en_una_conversacion_cerrada_ya_no_se_escribe(self):
        conversacion = self.chat.crear(CLIENTE, "Pedido", "Hola")
        self.chat.cambiar_estado(conversacion.id, "Cerrada", ADMIN)
        for id_login in (CLIENTE, EMPLEADO):
            with self.assertRaises(ConflictoError):
                self.chat.responder(conversacion.id, id_login, "¿Sigues ahí?")
        self.assertEqual(self.chat.cambiar_estado(conversacion.id, "Abierta", EMPLEADO).estado, "Abierta")

    def test_solo_el_personal_cierra_conversaciones(self):
        conversacion = self.chat.crear(CLIENTE, "Pedido", "Hola")
        with self.assertRaises(PermisoDenegadoError):
            self.chat.cambiar_estado(conversacion.id, "Cerrada", CLIENTE)
        with self.assertRaises(DatosInvalidosError):
            self.chat.cambiar_estado(conversacion.id, "Archivada", ADMIN)

    def test_solo_el_administrador_elimina_conversaciones(self):
        conversacion = self.chat.crear(CLIENTE, "Pedido", "Hola")
        for id_login in (EMPLEADO, CLIENTE):
            with self.assertRaises(PermisoDenegadoError):
                self.chat.eliminar(conversacion.id, id_login)
        self.chat.eliminar(conversacion.id, ADMIN)
        self.assertEqual(self.repo.datos, {})
        with self.assertRaises(NoEncontradoError):
            self.chat.eliminar(conversacion.id, ADMIN)

    def test_conversacion_o_usuario_que_no_existe(self):
        with self.assertRaises(NoEncontradoError):
            self.chat.obtener(999, ADMIN)
        with self.assertRaises(NoEncontradoError):
            self.chat.listar(999)

if __name__ == "__main__":
    unittest.main()

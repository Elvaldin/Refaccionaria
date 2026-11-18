"""Pruebas de los casos de uso de Login y Registro, sin base de datos.

Gracias a la arquitectura limpia, los casos de uso reciben interfaces: aquí
les damos versiones "falsas" en memoria en lugar de SQL Server y bcrypt.
"""
import unittest

from Domain.entities import User
from Application.login_use_case import (
    LoginUser, RegisterUser, CambiarContrasena, UserRepository, PasswordHasher,
    DatosInvalidosError, ConflictoError, PermisoDenegadoError, NoEncontradoError,
)


class RepositorioFalso(UserRepository):
    def __init__(self, usuarios):
        self.usuarios = {u.username: u for u in usuarios}

    def find_by_username(self, username):
        return self.usuarios.get(username)

    def find_by_id(self, id_user):
        return next((u for u in self.usuarios.values() if u.id == id_user), None)

    def email_existe(self, email):
        return any(u.email == email for u in self.usuarios.values())

    def save(self, user):
        user.id = len(self.usuarios) + 1
        self.usuarios[user.username] = user
        return user.id

    def update_password(self, id_user, password_hash):
        self.find_by_id(id_user).password_hash = password_hash


class HasherFalso(PasswordHasher):
    """Para la prueba, el "hash" de una contraseña es la contraseña al revés."""
    def __init__(self):
        self.llamadas = 0

    def verify(self, plain_password, hashed_password):
        self.llamadas += 1
        return plain_password[::-1] == hashed_password

    def hash(self, plain_password):
        return plain_password[::-1]


class PruebasLogin(unittest.TestCase):
    def setUp(self):
        self.hasher = HasherFalso()
        self.repo = RepositorioFalso([
            User(username="admin", password_hash="321nimdA", id_user=1, rol="Administrador", email="admin@r.com"),
            User(username="empleado", password_hash="321odaelpmE", id_user=2, rol="Empleado", email="empleado@r.com"),
            User(username="almacen", password_hash="321necamlA", id_user=3, rol="Almacenista", email="almacen@r.com"),
            User(username="cliente", password_hash="321etneilC", id_user=4, rol="Cliente", email="cliente@r.com"),
        ])
        self.login = LoginUser(user_repository=self.repo, password_hasher=self.hasher)
        self.registro = RegisterUser(user_repository=self.repo, password_hasher=self.hasher)

    # ----- Iniciar sesión -----
    def test_credenciales_correctas_regresa_el_usuario(self):
        usuario = self.login.execute("admin", "Admin123")
        self.assertIsNotNone(usuario)
        self.assertEqual(usuario.id, 1)
        self.assertEqual(usuario.username, "admin")
        self.assertEqual(usuario.rol, "Administrador")
        self.assertTrue(usuario.es_administrador)

    def test_cada_usuario_entra_con_su_rol(self):
        self.assertEqual(self.login.execute("empleado", "Empleado123").rol, "Empleado")
        self.assertEqual(self.login.execute("almacen", "Almacen123").rol, "Almacenista")
        cliente = self.login.execute("cliente", "Cliente123")
        self.assertEqual(cliente.rol, "Cliente")
        self.assertTrue(cliente.es_cliente)
        self.assertFalse(cliente.es_administrador)

    def test_un_usuario_nuevo_es_cliente_por_defecto(self):
        self.assertEqual(User(username="x", password_hash="y").rol, "Cliente")

    def test_contrasena_incorrecta_regresa_none(self):
        self.assertIsNone(self.login.execute("admin", "otra"))

    def test_usuario_que_no_existe_regresa_none_sin_revisar_contrasena(self):
        self.assertIsNone(self.login.execute("nadie", "Admin123"))
        self.assertEqual(self.hasher.llamadas, 0)

    # ----- Registrar usuario -----
    def test_cualquiera_se_registra_como_cliente_y_luego_puede_entrar(self):
        nuevo = self.registro.execute("juan", "Juan@Correo.com", "secreta1")
        self.assertEqual((nuevo.rol, nuevo.email), ("Cliente", "juan@correo.com"))
        self.assertIsNotNone(nuevo.id)
        self.assertEqual(self.repo.usuarios["juan"].password_hash, "1aterces")   # se guarda el hash
        self.assertEqual(self.login.execute("juan", "secreta1").id, nuevo.id)

    def test_sin_ser_administrador_no_se_puede_crear_personal(self):
        for rol in ("Administrador", "Empleado", "Almacenista"):
            with self.assertRaises(PermisoDenegadoError):
                self.registro.execute("intruso", "intruso@r.com", "secreta1", rol)            # sin sesión
            with self.assertRaises(PermisoDenegadoError):
                self.registro.execute("intruso", "intruso@r.com", "secreta1", rol, id_creador=2)   # Empleado
        self.assertNotIn("intruso", self.repo.usuarios)

    def test_el_administrador_crea_usuarios_de_cualquier_rol(self):
        nuevo = self.registro.execute("bodega", "bodega@r.com", "secreta1", "Almacenista", id_creador=1)
        self.assertEqual(nuevo.rol, "Almacenista")

    def test_no_se_repiten_usuario_ni_correo(self):
        with self.assertRaises(ConflictoError):
            self.registro.execute("cliente", "otro@r.com", "secreta1")
        with self.assertRaises(ConflictoError):
            self.registro.execute("otro", "CLIENTE@r.com", "secreta1")

    def test_datos_invalidos(self):
        with self.assertRaises(DatosInvalidosError):
            self.registro.execute("ab", "ab@r.com", "secreta1")          # usuario muy corto
        with self.assertRaises(DatosInvalidosError):
            self.registro.execute("con espacio", "e@r.com", "secreta1")  # usuario con espacio
        with self.assertRaises(DatosInvalidosError):
            self.registro.execute("pedro", "pedro@r.com", "123")         # contraseña corta
        with self.assertRaises(DatosInvalidosError):
            self.registro.execute("pedro", "pedro@r.com", "secreta1", "Jefe", id_creador=1)

    # ----- Cambiar contraseña -----
    def test_cambiar_contrasena_y_entrar_con_la_nueva(self):
        cambiar = CambiarContrasena(user_repository=self.repo, password_hasher=self.hasher)
        cambiar.execute("admin", "una-contrasena-larga")
        self.assertIsNone(self.login.execute("admin", "Admin123"))              # la vieja ya no sirve
        self.assertEqual(self.login.execute("admin", "una-contrasena-larga").id, 1)

    def test_cambiar_contrasena_con_errores_no_cambia_nada(self):
        cambiar = CambiarContrasena(user_repository=self.repo, password_hasher=self.hasher)
        with self.assertRaises(NoEncontradoError):
            cambiar.execute("nadie", "una-contrasena-larga")
        with self.assertRaises(DatosInvalidosError):
            cambiar.execute("admin", "corta123")                    # menos de 12
        with self.assertRaises(DatosInvalidosError):
            cambiar.execute("admin", "x" * 73)                      # bcrypt solo usa 72 bytes
        cambiar.execute("empleado", "Empleado1234")                 # 12 caracteres: sí se acepta
        with self.assertRaises(DatosInvalidosError):
            cambiar.execute("empleado", "Empleado1234")             # pero no la misma que ya tiene
        self.assertIsNotNone(self.login.execute("admin", "Admin123"))   # el admin sigue igual


if __name__ == "__main__":
    unittest.main()
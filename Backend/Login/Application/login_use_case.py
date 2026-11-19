"""Aplicación: casos de uso "Iniciar sesión" y "Registrar usuario".

Solo dicen QUÉ necesitan (un repositorio de usuarios y un servicio de
contraseñas) mediante interfaces. No saben nada de SQL Server ni de bcrypt:
eso lo pone la capa de Infraestructura.
"""
from Domain.entities import User, ROLES, ROL_CLIENTE, ROL_ADMINISTRADOR
from abc import ABC, abstractmethod
import re
from typing import Optional

# Largo mínimo de la contraseña al registrarse
MINIMO_CONTRASENA = 10

# Lo mismo que revisa la API (RegistroRequest), para cuando se crea desde la terminal
FORMATO_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

class DatosInvalidosError(Exception):
    pass


class ConflictoError(Exception):
    pass


class PermisoDenegadoError(Exception):
    pass


class NoEncontradoError(Exception):
    pass


class UserRepository(ABC):
    @abstractmethod
    def find_by_username(self, username: str) -> Optional[User]:
        pass

    @abstractmethod
    def find_by_id(self, id_user: int) -> Optional[User]:
        pass

    @abstractmethod
    def email_existe(self, email: str) -> bool:
        pass

    @abstractmethod
    def save(self, user: User) -> int:
        """Guarda el usuario nuevo y regresa su id."""
        pass

    @abstractmethod
    def update_password(self, id_user: int, password_hash: str) -> None:
        """Guarda el hash de la contraseña nueva del usuario."""
        pass


class PasswordHasher(ABC):
    @abstractmethod
    def verify(self, plain_password: str, hashed_password: str) -> bool:
        pass

    @abstractmethod
    def hash(self, plain_password: str) -> str:
        pass


class LoginUser:
    def __init__(self, user_repository: UserRepository, password_hasher: PasswordHasher):
        self.user_repository = user_repository
        self.password_hasher = password_hasher

    def execute(self, username: str, password: str) -> Optional[User]:
        """Regresa el usuario si las credenciales son correctas, o None si no."""
        user = self.user_repository.find_by_username(username)
        if not user:
            # Se hace el mismo trabajo que al revisar una contraseña (bcrypt es lento a propósito):
            # si no, contestaría al instante y se sabría qué usuarios existen con solo medir el tiempo
            self.password_hasher.hash(password)
            return None
        if not self.password_hasher.verify(password, user.password_hash):
            return None
        return user


class RegisterUser:
    """Crea un usuario nuevo.

    Cualquier persona puede registrarse, pero queda como Cliente.
    Solo un Administrador (id_creador) puede crear usuarios con otro rol.
    """

    def __init__(self, user_repository: UserRepository, password_hasher: PasswordHasher):
        self.user_repository = user_repository
        self.password_hasher = password_hasher

    def execute(self, username: str, email: str, password: str,
                rol: str = ROL_CLIENTE, id_creador: Optional[int] = None) -> User:
        username = username.strip()
        email = email.strip().lower()
        if len(username) < 3 or " " in username:
            raise DatosInvalidosError("El usuario debe tener al menos 3 letras y no llevar espacios")
        if len(password) < MINIMO_CONTRASENA:
            raise DatosInvalidosError(f"La contraseña debe tener al menos {MINIMO_CONTRASENA} caracteres")
        if len(password.encode("utf-8")) > 72:
            # bcrypt solo toma en cuenta los primeros 72 bytes
            raise DatosInvalidosError("La contraseña es demasiado larga (máximo 72 caracteres)")
        if rol not in ROLES:
            raise DatosInvalidosError(f"El rol '{rol}' no existe")

        if rol != ROL_CLIENTE:
            creador = self.user_repository.find_by_id(id_creador) if id_creador else None
            if not creador or not creador.es_administrador:
                raise PermisoDenegadoError("Solo un Administrador puede crear usuarios con el rol " + rol)

        if self.user_repository.find_by_username(username):
            raise ConflictoError(f"El usuario '{username}' ya existe")
        if self.user_repository.email_existe(email):
            raise ConflictoError("Ese correo ya está registrado")

        user = User(username=username, password_hash=self.password_hasher.hash(password),
                    rol=rol, email=email)
        user.id = self.user_repository.save(user)
        return user


class CrearAdministrador:
    """Crea una cuenta de Administrador desde la terminal (crear_administrador.py).

    Sirve para el primer Administrador de la tienda publicada: así en el
    servidor nunca existe un admin con una contraseña escrita en el README.
    Pide una contraseña más larga que al registrarse, igual que CambiarContrasena.
    """

    MINIMO = 12

    def __init__(self, user_repository: UserRepository, password_hasher: PasswordHasher):
        self.user_repository = user_repository
        self.password_hasher = password_hasher

    def execute(self, username: str, email: str, password: str) -> User:
        username = username.strip()
        email = email.strip().lower()
        if len(username) < 3 or len(username) > 50 or " " in username:
            raise DatosInvalidosError("El usuario debe tener de 3 a 50 letras y no llevar espacios")
        if len(email) > 100 or not FORMATO_CORREO.match(email):
            raise DatosInvalidosError("El correo no es válido")
        if len(password) < self.MINIMO:
            raise DatosInvalidosError(f"La contraseña debe tener al menos {self.MINIMO} caracteres")
        if len(password.encode("utf-8")) > 72:
            # bcrypt solo toma en cuenta los primeros 72 bytes
            raise DatosInvalidosError("La contraseña es demasiado larga (máximo 72 caracteres)")
        if self.user_repository.find_by_username(username):
            raise ConflictoError(f"El usuario '{username}' ya existe")
        if self.user_repository.email_existe(email):
            raise ConflictoError("Ese correo ya está registrado")

        user = User(username=username, password_hash=self.password_hasher.hash(password),
                    rol=ROL_ADMINISTRADOR, email=email)
        user.id = self.user_repository.save(user)
        return user


class CambiarContrasena:
    """Le pone una contraseña nueva a un usuario.

    Lo usa el programa cambiar_contrasena.py, por ejemplo para cambiar la
    contraseña de prueba del admin antes de publicar la tienda.
    """

    MINIMO = 12   # más que al registrarse: es para cuentas del personal

    def __init__(self, user_repository: UserRepository, password_hasher: PasswordHasher):
        self.user_repository = user_repository
        self.password_hasher = password_hasher

    def execute(self, username: str, nueva: str) -> User:
        user = self.user_repository.find_by_username(username.strip())
        if not user:
            raise NoEncontradoError(f"No existe el usuario '{username.strip()}'")
        if len(nueva) < self.MINIMO:
            raise DatosInvalidosError(f"La contraseña nueva debe tener al menos {self.MINIMO} caracteres")
        if len(nueva.encode("utf-8")) > 72:
            # bcrypt solo toma en cuenta los primeros 72 bytes
            raise DatosInvalidosError("La contraseña nueva es demasiado larga (máximo 72 caracteres)")
        if self.password_hasher.verify(nueva, user.password_hash):
            raise DatosInvalidosError("La contraseña nueva es igual a la anterior")
        user.password_hash = self.password_hasher.hash(nueva)
        self.user_repository.update_password(user.id, user.password_hash)
        return user

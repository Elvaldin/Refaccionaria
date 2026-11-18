from Domain.entities import Soporte, Conversacion, Mensaje
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Callable, List, Optional

class NoEncontradoError(Exception):
    pass

class DatosInvalidosError(Exception):
    pass

class PermisoDenegadoError(Exception):
    pass

class SoporteRepository(ABC):
    @abstractmethod
    def find_all(self) -> List[Soporte]:
        pass

    @abstractmethod
    def find_by_id(self, id_soporte: int) -> Optional[Soporte]:
        pass

    @abstractmethod
    def save(self, soporte: Soporte) -> Soporte:
        pass

    @abstractmethod
    def update(self, soporte: Soporte) -> bool:
        pass

    @abstractmethod
    def delete(self, id_soporte: int) -> bool:
        pass

class UsuarioRepository(ABC):
    @abstractmethod
    def rol_de_usuario(self, id_login: int) -> Optional[str]:
        """Regresa el rol del usuario, o None si el usuario no existe."""
        pass

class GestionarSoporte:
    """Los datos de contacto los ve cualquiera, pero solo el Administrador los cambia."""

    def __init__(self, soporte_repository: SoporteRepository, usuario_repository: UsuarioRepository):
        self.soporte_repository = soporte_repository
        self.usuario_repository = usuario_repository

    def listar(self) -> List[Soporte]:
        return self.soporte_repository.find_all()

    def obtener(self, id_soporte: int) -> Soporte:
        soporte = self.soporte_repository.find_by_id(id_soporte)
        if not soporte:
            raise NoEncontradoError(f"No existe el contacto {id_soporte}")
        return soporte

    def crear(self, soporte: Soporte, id_login: int) -> Soporte:
        self._solo_administrador(id_login)
        self._validar(soporte)
        return self.soporte_repository.save(soporte)

    def actualizar(self, soporte: Soporte, id_login: int) -> Soporte:
        self._solo_administrador(id_login)
        self._validar(soporte)
        if not self.soporte_repository.update(soporte):
            raise NoEncontradoError(f"No existe el contacto de soporte {soporte.id}")
        return self.obtener(soporte.id)

    def eliminar(self, id_soporte: int, id_login: int) -> None:
        self._solo_administrador(id_login)
        if not self.soporte_repository.delete(id_soporte):
            raise NoEncontradoError(f"No existe el contacto de soporte {id_soporte}")

    def _validar(self, soporte: Soporte) -> None:
        if not (soporte.correo or soporte.telefono or soporte.direccion):
            raise DatosInvalidosError("Debes poner al menos correo, telefono o direccion")

    def _solo_administrador(self, id_login: int) -> None:
        rol = self.usuario_repository.rol_de_usuario(id_login)
        if rol is None:
            raise NoEncontradoError(f"No existe el usuario {id_login}")
        if rol != ROL_ADMINISTRADOR:
            raise PermisoDenegadoError(f"Solo el Administrador cambia los datos de contacto (tu rol es {rol})")



# ===== Chat de soporte =====
# Roles (vienen de la columna Rol de la tabla LOGIN)
ROL_ADMINISTRADOR = "Administrador"
ROL_EMPLEADO = "Empleado"
ROL_CLIENTE = "Cliente"
PERSONAL_DE_SOPORTE = [ROL_ADMINISTRADOR, ROL_EMPLEADO]   # los que contestan los mensajes
ESTADOS_CONVERSACION = ["Abierta", "Cerrada"]

class ConflictoError(Exception):
    pass

class ConversacionRepository(ABC):
    @abstractmethod
    def find_all(self, id_login: Optional[int]) -> List[Conversacion]:
        """Las conversaciones con sus mensajes. id_login=None trae las de todos los clientes."""
        pass

    @abstractmethod
    def find_by_id(self, id_conversacion: int) -> Optional[Conversacion]:
        pass

    @abstractmethod
    def save(self, conversacion: Conversacion) -> Conversacion:
        """Guarda la conversación junto con su primer mensaje."""
        pass

    @abstractmethod
    def add_mensaje(self, mensaje: Mensaje) -> None:
        pass

    @abstractmethod
    def update_estado(self, id_conversacion: int, estado: str) -> None:
        pass

    @abstractmethod
    def delete(self, id_conversacion: int) -> bool:
        """Borra la conversación con todos sus mensajes."""
        pass

    @abstractmethod
    def rol_de_usuario(self, id_login: int) -> Optional[str]:
        """Regresa el rol del usuario, o None si el usuario no existe."""
        pass

class GestionarConversaciones:
    def __init__(self, conversacion_repository: ConversacionRepository,
                 ahora: Callable[[], datetime] = datetime.now):
        self.conversacion_repository = conversacion_repository
        self.ahora = ahora   # la hora de la computadora (el reloj de SQL Server en Docker está en UTC)

    def listar(self, id_login: int) -> List[Conversacion]:
        # El Cliente ve solo las suyas; el personal ve las de todos
        if self._rol(id_login) == ROL_CLIENTE:
            return self.conversacion_repository.find_all(id_login)
        self._revisar_personal(id_login)
        return self.conversacion_repository.find_all(None)

    def obtener(self, id_conversacion: int, id_login: int) -> Conversacion:
        conversacion = self.conversacion_repository.find_by_id(id_conversacion)
        if not conversacion:
            raise NoEncontradoError(f"No existe la conversación {id_conversacion}")
        if self._rol(id_login) == ROL_CLIENTE:
            if conversacion.id_login != id_login:
                raise PermisoDenegadoError("Solo puedes ver tus propias conversaciones")
        else:
            self._revisar_personal(id_login)
        return conversacion

    def crear(self, id_login: int, asunto: str, texto: str) -> Conversacion:
        if self._rol(id_login) != ROL_CLIENTE:
            raise PermisoDenegadoError("Solo los clientes empiezan conversaciones; el personal las contesta")
        asunto = asunto.strip()
        if not asunto:
            raise DatosInvalidosError("Escribe el asunto")
        ahora = self.ahora()
        conversacion = Conversacion(id_login=id_login, asunto=asunto, fecha=ahora,
                                    mensajes=[Mensaje(None, id_login, self._limpiar(texto), fecha=ahora)])
        conversacion = self.conversacion_repository.save(conversacion)
        return self.obtener(conversacion.id, id_login)

    def responder(self, id_conversacion: int, id_login: int, texto: str) -> Conversacion:
        conversacion = self.obtener(id_conversacion, id_login)   # aquí se revisa que pueda verla
        if conversacion.estado == "Cerrada":
            raise ConflictoError("La conversación está cerrada")
        mensaje = Mensaje(id_conversacion, id_login, self._limpiar(texto), fecha=self.ahora())
        self.conversacion_repository.add_mensaje(mensaje)
        return self.obtener(id_conversacion, id_login)

    def cambiar_estado(self, id_conversacion: int, estado: str, id_login: int) -> Conversacion:
        self._revisar_personal(id_login)
        if estado not in ESTADOS_CONVERSACION:
            raise DatosInvalidosError(f"El estado debe ser uno de {ESTADOS_CONVERSACION}")
        self.obtener(id_conversacion, id_login)
        self.conversacion_repository.update_estado(id_conversacion, estado)
        return self.obtener(id_conversacion, id_login)

    def eliminar(self, id_conversacion: int, id_login: int) -> None:
        if self._rol(id_login) != ROL_ADMINISTRADOR:
            raise PermisoDenegadoError("Solo el Administrador elimina conversaciones")
        if not self.conversacion_repository.delete(id_conversacion):
            raise NoEncontradoError(f"No existe la conversación {id_conversacion}")

    def _rol(self, id_login: int) -> str:
        rol = self.conversacion_repository.rol_de_usuario(id_login)
        if rol is None:
            raise NoEncontradoError(f"No existe el usuario {id_login}")
        return rol

    def _revisar_personal(self, id_login: int) -> None:
        rol = self._rol(id_login)
        if rol not in PERSONAL_DE_SOPORTE:
            raise PermisoDenegadoError(f"Un {rol} no atiende el chat de soporte")

    def _limpiar(self, texto: str) -> str:
        texto = texto.strip()
        if not texto:
            raise DatosInvalidosError("Escribe un mensaje")
        return texto
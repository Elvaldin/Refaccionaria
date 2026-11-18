from Domain.entities import Promocion
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Callable, List, Optional

class NoEncontradoError(Exception):
    pass

class DatosInvalidosError(Exception):
    pass

class PromocionRepository(ABC):
    @abstractmethod
    def find_all(self, solo_vigentes: bool, ahora: datetime) -> List[Promocion]:
        """Con solo_vigentes=True regresa solo las activas que van en esa fecha y hora."""
        pass

    @abstractmethod
    def find_by_id(self, id_promocion: int) -> Optional[Promocion]:
        pass

    @abstractmethod
    def save(self, promocion: Promocion, ids_productos: List[int]) -> Promocion:
        """Guarda la promoción con sus productos, todo junto: si algo falla, no se guarda nada."""
        pass

    @abstractmethod
    def update(self, promocion: Promocion, ids_productos: Optional[List[int]] = None) -> bool:
        """Cambia los datos. Si llegan ids_productos, esos quedan como sus productos (todo junto)."""
        pass

    @abstractmethod
    def delete(self, id_promocion: int) -> bool:
        pass

    @abstractmethod
    def delete_vencidas(self, ahora: datetime) -> int:
        """Borra las promociones cuya fecha de fin ya pasó. Regresa cuántas borró."""
        pass

    @abstractmethod
    def producto_existe(self, id_producto: int) -> bool:
        pass

    @abstractmethod
    def add_producto(self, id_promocion: int, id_producto: int) -> bool:
        pass

    @abstractmethod
    def remove_producto(self, id_promocion: int, id_producto: int) -> bool:
        pass

class GestionarPromociones:
    # "ahora" es la función que da la fecha y hora actual. En las pruebas se cambia
    # por una fecha fija, así no fallan cuando pasen los días.
    def __init__(self, promocion_repository: PromocionRepository, ahora: Callable[[], datetime] = datetime.now):
        self.promocion_repository = promocion_repository
        self.ahora = ahora

    def listar(self, solo_vigentes: bool = False) -> List[Promocion]:
        # Antes de listar se borran las vencidas: así nunca aparece una promoción que ya terminó
        self.borrar_vencidas()
        return self.promocion_repository.find_all(solo_vigentes, self.ahora())

    def borrar_vencidas(self) -> int:
        return self.promocion_repository.delete_vencidas(self.ahora())

    def obtener(self, id_promocion: int) -> Promocion:
        promocion = self.promocion_repository.find_by_id(id_promocion)
        if not promocion:
            raise NoEncontradoError(f"No existe la promocion {id_promocion}")
        return promocion

    def crear(self, promocion: Promocion, ids_productos: Optional[List[int]] = None) -> Promocion:
        """Crea la promoción y le agrega sus productos de una vez."""
        ids_productos = ids_productos or []
        self._validar_fechas(promocion)
        if promocion.fecha_inicio.date() < self.ahora().date():
            raise DatosInvalidosError("La promoción no puede empezar en un día que ya pasó")
        self._validar_productos(ids_productos)
        creada = self.promocion_repository.save(promocion, ids_productos)
        return self.obtener(creada.id)

    def actualizar(self, promocion: Promocion, ids_productos: Optional[List[int]] = None) -> Promocion:
        """Cambia los datos de la promoción. Si llegan ids_productos, esos quedan como sus productos."""
        actual = self.obtener(promocion.id)
        self._validar_fechas(promocion)
        # Si ya empezó puede dejar su fecha de inicio como está, pero no moverla a otro día pasado
        if (promocion.fecha_inicio.date() < self.ahora().date()
                and promocion.fecha_inicio.date() != actual.fecha_inicio.date()):
            raise DatosInvalidosError("La promoción no puede empezar en un día que ya pasó")
        if ids_productos is not None:
            self._validar_productos(ids_productos)
        self.promocion_repository.update(promocion, ids_productos)
        return self.obtener(promocion.id)

    def eliminar(self, id_promocion: int) -> None:
        if not self.promocion_repository.delete(id_promocion):
            raise NoEncontradoError(f"No existe la promocion {id_promocion}")

    def agregar_producto(self, id_promocion: int, id_producto: int) -> Promocion:
        self.obtener(id_promocion)
        if not self.promocion_repository.producto_existe(id_producto):
            raise NoEncontradoError(f"No existe el producto {id_producto}")
        if not self.promocion_repository.add_producto(id_promocion, id_producto):
            raise DatosInvalidosError(f"El producto {id_producto} ya esta en la promocion")
        return self.obtener(id_promocion)

    def quitar_producto(self, id_promocion: int, id_producto: int) -> Promocion:
        if not self.promocion_repository.remove_producto(id_promocion, id_producto):
            raise NoEncontradoError(f"El producto {id_producto} no esta en la promocion {id_promocion}")
        return self.obtener(id_promocion)

    def _validar_productos(self, ids_productos: List[int]) -> None:
        if len(ids_productos) != len(set(ids_productos)):
            raise DatosInvalidosError("Hay productos repetidos en la promoción")
        # Se revisan todos los productos ANTES de guardar, para no dejar una promoción a medias
        for id_producto in ids_productos:
            if not self.promocion_repository.producto_existe(id_producto):
                raise NoEncontradoError(f"No existe el producto {id_producto}")

    def _validar_fechas(self, promocion: Promocion) -> None:
        if promocion.fecha_inicio > promocion.fecha_fin:
            raise DatosInvalidosError("La fecha de inicio debe ser antes de la fecha de fin")
        if promocion.fecha_fin < self.ahora():
            raise DatosInvalidosError("La fecha de fin ya pasó: la promoción nacería vencida")

# ===== Permisos =====
# Solo el Administrador cambia las promociones; ver la lista es libre
ROL_ADMINISTRADOR = "Administrador"

class PermisoDenegadoError(Exception):
    pass

class UsuarioRepository(ABC):
    @abstractmethod
    def rol_de_usuario(self, id_login: int) -> Optional[str]:
        """Regresa el rol del usuario, o None si el usuario no existe"""
        pass

class RevisarPermisos:
    def __init__(self, usuario_repository: UsuarioRepository):
        self.usuario_repository = usuario_repository

    def solo_administrador(self, id_login: int) -> None:
        rol = self.usuario_repository.rol_de_usuario(id_login)
        if rol is None:
            raise PermisoDenegadoError(f"No existe el usuario {id_login}")
        if rol != ROL_ADMINISTRADOR:
            raise PermisoDenegadoError(f"Solo el Administrador puede hacer este cambio (tu rol es {rol})")
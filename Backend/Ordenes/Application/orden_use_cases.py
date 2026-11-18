from Domain.entities import Orden, MovimientoInventario
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Callable, Dict, List, Optional

# A qué estados puede pasar una orden desde su estado actual
TRANSICIONES = {
    "Pendiente": ["En Proceso", "Completada", "Cancelada"],
    "En Proceso": ["Completada", "Cancelada"],
    "Completada": [],
    "Cancelada": [],
}

# Roles (vienen de la columna Rol de la tabla LOGIN)
ROL_ADMINISTRADOR = "Administrador"   # puede todo
ROL_EMPLEADO = "Empleado"             # hace ventas y las avanza; no compras ni cancelar
ROL_ALMACENISTA = "Almacenista"       # registra compras (mercancía que entra) y las avanza
ROL_CLIENTE = "Cliente"               # solo hace pedidos (Ventas) y solo ve sus propias órdenes

# Quién puede crear cada tipo de orden
PUEDEN_CREAR = {
    "Venta": [ROL_ADMINISTRADOR, ROL_EMPLEADO, ROL_CLIENTE],
    "Compra": [ROL_ADMINISTRADOR, ROL_ALMACENISTA],
}

# Quién puede avanzar cada tipo de orden (a En Proceso o Completada).
# Cancelar es solo del Administrador.
PUEDEN_AVANZAR = {
    "Venta": [ROL_ADMINISTRADOR, ROL_EMPLEADO],
    "Compra": [ROL_ADMINISTRADOR, ROL_ALMACENISTA],
}


class NoEncontradoError(Exception):
    pass


class PermisoDenegadoError(Exception):
    pass


class DatosInvalidosError(Exception):
    pass


class ConflictoError(Exception):
    pass

class ProductoInfo:
    def __init__(self, nombre: str, precio: float, stock: int, descuento: float = 0):
        self.nombre = nombre
        self.precio = precio
        self.stock = stock
        self.descuento = descuento  # % de la promoción vigente hoy (0 si no tiene)

    def precio_de_venta(self) -> float:
        """El precio que paga el cliente: con el descuento de la promoción, si tiene."""
        return round(self.precio * (1 - self.descuento / 100), 2)

class OrdenRepository(ABC):
    @abstractmethod
    def find_all(self, tipo: Optional[str], estado: Optional[str], id_login: Optional[int] = None) -> List[Orden]:
        """Si llega id_login, solo regresa las órdenes de ese usuario."""
        pass

    @abstractmethod
    def find_by_id(self, id_orden: int) -> Optional[Orden]:
        pass

    @abstractmethod
    def save(self, orden: Orden) -> int:
        pass

    @abstractmethod
    def rol_de_usuario(self, id_login: int) -> Optional[str]:
        """Regresa el rol del usuario, o None si el usuario no existe."""
        pass

    @abstractmethod
    def find_productos(self, ids: List[int]) -> Dict[int, ProductoInfo]:
        """Cada producto con su precio, stock y el descuento de su promoción vigente."""
        pass

    @abstractmethod
    def update_estado(self, id_orden: int, estado: str, estado_actual: str) -> bool:
        """Cambia el estado solo si la orden sigue en estado_actual.
        Regresa False si alguien más la cambió antes (no se guarda nada)."""
        pass

    @abstractmethod
    def completar(self, orden: Orden, fecha: datetime) -> None:
        """Mueve el inventario y marca la orden como Completada, todo junto."""
        pass

    @abstractmethod
    def find_movimientos(self, id_producto: Optional[int]) -> List[MovimientoInventario]:
        pass


class GestionarOrdenes:
    def __init__(self, orden_repository: OrdenRepository, ahora: Callable[[], datetime] = datetime.now):
        self.orden_repository = orden_repository
        self.ahora = ahora      # La hora de la computadora (el reloj de SQL Server en Docker está en UTC) 

    def listar(self, id_login: int, tipo: Optional[str] = None,
               estado: Optional[str] = None) -> List[Orden]:
        """id_login es quién consulta (obligatorio): un Cliente solo ve sus propias órdenes."""
        if self._rol(id_login) == ROL_CLIENTE:
            return self.orden_repository.find_all(tipo, estado, id_login)
        return self.orden_repository.find_all(tipo, estado)

    def obtener(self, id_orden: int, id_login: int) -> Orden:
        """id_login es quién consulta (obligatorio): un Cliente solo ve sus propias órdenes."""
        orden = self._buscar(id_orden)
        if self._rol(id_login) == ROL_CLIENTE and orden.id_login != id_login:
            raise PermisoDenegadoError("Un Cliente solo puede ver sus propias órdenes")
        return orden

    def _buscar(self, id_orden: int) -> Orden:
        # Uso interno: aquí ya se revisaron los permisos
        orden = self.orden_repository.find_by_id(id_orden)
        if not orden:
            raise NoEncontradoError(f"No existe la orden {id_orden}")
        return orden

    def crear(self, orden: Orden) -> Orden:
        if not orden.detalles:
            raise DatosInvalidosError("La orden debe tener al menos un producto")
        ids = [d.id_producto for d in orden.detalles]
        if len(ids) != len(set(ids)):
            raise DatosInvalidosError("Hay productos repetidos en la orden")
        rol = self._rol(orden.id_login)
        if rol not in PUEDEN_CREAR[orden.tipo]:
            quienes = " o ".join(PUEDEN_CREAR[orden.tipo])
            raise PermisoDenegadoError(f"Las órdenes de {orden.tipo} solo las registra un {quienes}")

        productos = self.orden_repository.find_productos(ids)
        for detalle in orden.detalles:
            if detalle.id_producto not in productos:
                raise NoEncontradoError(f"No existe el producto {detalle.id_producto}")
            # Si no mandan precio, se usa el precio actual del producto.
            # Un Cliente siempre paga el precio de la tienda (no puede poner el suyo).
            # En una venta se respeta la promoción vigente; en una compra al proveedor, no
            if detalle.precio_unitario is None or rol == ROL_CLIENTE:
                producto = productos[detalle.id_producto]
                detalle.precio_unitario = producto.precio_de_venta() if orden.tipo == "Venta" else producto.precio

        orden.fecha = self.ahora()
        id_orden = self.orden_repository.save(orden)
        return self._buscar(id_orden)

    def cambiar_estado(self, id_orden: int, nuevo_estado: str, id_login: int) -> Orden:
        """id_login es quién hace el cambio: de eso depende si tiene permiso."""
        orden = self._buscar(id_orden)
        rol = self._rol(id_login)
        if rol == ROL_CLIENTE:
            raise PermisoDenegadoError("Un Cliente no puede cambiar el estado de las órdenes")
        if nuevo_estado not in TRANSICIONES[orden.estado]:
            raise ConflictoError(f"No se puede pasar de '{orden.estado}' a '{nuevo_estado}'")
        if nuevo_estado == "Cancelada":
            if rol != ROL_ADMINISTRADOR:
                raise PermisoDenegadoError("Solo un Administrador puede cancelar órdenes")
        elif rol not in PUEDEN_AVANZAR[orden.tipo]:
            raise PermisoDenegadoError(f"Un {rol} no puede avanzar órdenes de {orden.tipo}")

        if nuevo_estado == "Completada":
            if orden.tipo == "Venta":
                self._validar_stock(orden)
            self.orden_repository.completar(orden, self.ahora())
        elif not self.orden_repository.update_estado(id_orden, nuevo_estado, orden.estado):
            # Otra persona la completó o canceló al mismo tiempo
            raise ConflictoError(f"La orden {id_orden} cambio de estado, intenta de nuevo")
        return self._buscar(id_orden)

    def movimientos(self, id_login: int, id_producto: Optional[int] = None) -> List[MovimientoInventario]:
        # El inventario es información interna de la tienda (id_login = quién consulta, obligatorio)
        if self._rol(id_login) == ROL_CLIENTE:
            raise PermisoDenegadoError("Un Cliente no puede ver los movimientos de inventario")
        return self.orden_repository.find_movimientos(id_producto)

    def _rol(self, id_login: int) -> str:
        rol = self.orden_repository.rol_de_usuario(id_login)
        if rol is None:
            raise NoEncontradoError(f"No existe el usuario {id_login}")
        return rol

    def _validar_stock(self, orden: Orden) -> None:
        productos = self.orden_repository.find_productos([d.id_producto for d in orden.detalles])
        for detalle in orden.detalles:
            disponible = productos[detalle.id_producto].stock
            if detalle.cantidad > disponible:
                raise ConflictoError(
                    f"No hay suficiente stock de '{detalle.producto}': "
                    f"hay {disponible} y se piden {detalle.cantidad}"
                )
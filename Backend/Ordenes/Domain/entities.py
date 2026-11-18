from datetime import datetime
from typing import List, Optional


class DetalleOrden:
    def __init__(self, id_producto: int, cantidad: int, precio_unitario: Optional[float] = None,
                 producto: Optional[str] = None):
        self.id_producto = id_producto
        self.producto = producto
        self.cantidad = cantidad
        self.precio_unitario = precio_unitario

    @property
    def subtotal(self) -> float:
        return round(self.cantidad * self.precio_unitario, 2)


class Orden:
    def __init__(self, id_login: int, tipo: str, detalles: List[DetalleOrden],
                 observaciones: Optional[str] = None, estado: str = "Pendiente",
                 fecha: Optional[datetime] = None, id_orden: int = None):
        self.id = id_orden
        self.id_login = id_login
        self.tipo = tipo
        self.observaciones = observaciones
        self.estado = estado
        self.fecha = fecha
        self.detalles = detalles

    @property
    def total(self) -> float:
        return round(sum(d.subtotal for d in self.detalles), 2)


class MovimientoInventario:
    def __init__(self, id_movimiento: int, id_producto: int, producto: str, id_orden: Optional[int],
                 tipo: str, cantidad: int, observaciones: Optional[str], fecha: datetime):
        self.id = id_movimiento
        self.id_producto = id_producto
        self.producto = producto
        self.id_orden = id_orden
        self.tipo = tipo
        self.cantidad = cantidad
        self.observaciones = observaciones
        self.fecha = fecha
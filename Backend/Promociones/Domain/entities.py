from datetime import datetime
from typing import List, Optional

class ProductoEnPromocion:
    def __init__(self, id_producto: int, nombre: str, precio: float, descuento: float):
        self.id = id_producto
        self.nombre = nombre
        self.precio = precio
        self.precio_con_descuento = round(precio *  (1 - descuento / 100), 2)

class Promocion:
    def __init__(self, nombre: str, descuento: float, fecha_inicio: datetime, fecha_fin: datetime,
                 activa: bool = True, descripcion: Optional[str] = None, id_promocion: int = None):
        self.id = id_promocion
        self.nombre = nombre
        self.descripcion = descripcion
        self.descuento = descuento
        self.fecha_inicio = fecha_inicio
        self.fecha_fin = fecha_fin
        self.activa = activa
        self.productos: List[ProductoEnPromocion] = []
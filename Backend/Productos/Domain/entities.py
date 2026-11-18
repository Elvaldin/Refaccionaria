from typing import Optional

class Categoria:
    def __init__(self, nombre: str, descripcion: Optional[str] = None, id_categoria: int = None):
        self.id = id_categoria
        self.nombre = nombre
        self.descripcion = descripcion

class Producto:
    def __init__(self, nombre: str, precio: float, stock: int, id_categoria: int,
                 descripcion: Optional[str] = None, id_producto: int = None,
                 categoria: Optional[str] = None, imagen: Optional[str] = None):
        self.id = id_producto
        self.nombre = nombre
        self.descripcion = descripcion
        self.precio = precio
        self.stock = stock
        self.id_categoria = id_categoria
        self.categoria = categoria
        self.imagen = imagen   # ruta de la foto, ej. "img/productos/bujia.jpg" (None = sin foto)

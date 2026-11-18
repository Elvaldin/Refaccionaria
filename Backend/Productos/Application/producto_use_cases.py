from Domain.entities import Categoria, Producto
from abc import ABC, abstractmethod
from typing import List, Optional


class NoEncontradoError(Exception):
    pass

class ProductoEnUsoError(Exception):
    pass

class CategoriaEnUsoError(Exception):
    pass

class CategoriaRepetidaError(Exception):
    pass

class CategoriaRepository(ABC):
    @abstractmethod
    def find_all(self) -> List[Categoria]:
        pass
    @abstractmethod
    def find_by_id(self, id_categoria: int) -> Optional[Categoria]:
        pass
    @abstractmethod
    def save(self, categoria: Categoria) -> Categoria:
        """Lanza CategoriaRepetidaError si ya existe una con ese nombre."""
        pass
    @abstractmethod
    def contar_productos(self, id_categoria: int) -> int:
        pass
    @abstractmethod
    def delete(self, id_categoria: int) -> bool:
        pass

class ProductoRepository(ABC):
    @abstractmethod
    def find_all(self, id_categoria: Optional[int] = None, buscar: Optional[str] = None) -> List[Producto]:
        pass
    @abstractmethod
    def find_by_id(self, id_producto: int) -> Optional[Producto]:
        pass
    @abstractmethod
    def save(self, producto: Producto) -> Producto:
        pass
    @abstractmethod
    def update(self, producto: Producto) -> bool:
        pass
    @abstractmethod
    def delete(self, id_producto: int) -> bool:
        pass

class GestionarCategorias:
    def __init__(self, categoria_repository: CategoriaRepository):
        self.categoria_repository = categoria_repository
    def listar(self) -> List[Categoria]:
        return self.categoria_repository.find_all()
    def crear(self, nombre: str, descripcion: Optional[str]) -> Categoria:
        return self.categoria_repository.save(Categoria(nombre=nombre.strip(), descripcion=descripcion))
    def eliminar(self, id_categoria: int) -> None:
        categoria = self.categoria_repository.find_by_id(id_categoria)
        if not categoria:
            raise NoEncontradoError(f"No existe la categoria {id_categoria}")
        # Una categoría con productos no se borra: los productos se quedarían sin categoría
        total = self.categoria_repository.contar_productos(id_categoria)
        if total > 0:
            raise CategoriaEnUsoError(
                f"La categoría '{categoria.nombre}' tiene {total} {'producto' if total == 1 else 'productos'}: "
                "cámbialos de categoría o bórralos primero"
            )
        self.categoria_repository.delete(id_categoria)


class GestionarProductos:
    def __init__(self, producto_repository: ProductoRepository, categoria_repository: CategoriaRepository):
        self.producto_repository = producto_repository
        self.categoria_repository = categoria_repository

    def listar(self, id_categoria: Optional[int] = None, buscar: Optional[str] = None) -> List[Producto]:
        return self.producto_repository.find_all(id_categoria, buscar)
    
    def obtener(self, id_producto: int) -> Producto:
        producto = self.producto_repository.find_by_id(id_producto)
        if not producto:
            raise NoEncontradoError(f"No existe el producto {id_producto}")
        return producto
    
    def crear(self, producto: Producto) -> Producto:
        self._validar_categoria(producto.id_categoria)
        return self.producto_repository.save(producto)
    
    def actualizar(self, producto: Producto) -> Producto:
        actual = self.obtener(producto.id)

        self._validar_categoria(producto.id_categoria)
        # El stock no se edita a mano: solo cambia con las órdenes, así quedan los movimientos de inventario

        producto.stock = actual.stock
        self.producto_repository.update(producto)
        return self.obtener(producto.id)
    
    def eliminar(self, id_producto: int) -> None:
        if not self.producto_repository.delete(id_producto):
            raise NoEncontradoError(f"No existe el producto {id_producto}")
    def _validar_categoria(self, id_categoria: int) -> None:
        if not self.categoria_repository.find_by_id(id_categoria):
            raise NoEncontradoError(f"No existe la categoria {id_categoria}")

# ===== Permisos =====
# Solo el Administrador cambia productos y categorías; ver la lista es libre
ROL_ADMINISTRADOR = "Administrador"

class PermisoDenegadoError(Exception):
    pass

class UsuarioRepository(ABC):
    @abstractmethod
    def rol_de_usuario(self, id_login: int) -> Optional[str]:
        """Regresa el rol del usuario, o None si el usuario no existe."""
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
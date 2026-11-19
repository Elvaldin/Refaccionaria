from typing import List, Optional
import pyodbc
from Domain.entities import Categoria, Producto
from Application.producto_use_cases import (
    CategoriaRepository, ProductoRepository, ProductoEnUsoError, CategoriaRepetidaError, UsuarioRepository
)
from Infrastructure.database import get_db_connection

PRODUCTO_SELECT = """
    SELECT p.Id_producto, p.Nombre, p.Descripcion, p.Precio, p.Stock, p.Id_categoria, p.Imagen,
           c.Nombre AS Categoria
    FROM PRODUCTOS p
    JOIN CATEGORIAS c ON c.Id_categoria = p.Id_categoria
"""


def _row_to_producto(row) -> Producto:
    return Producto(
        id_producto=row.Id_producto,
        nombre=row.Nombre,
        descripcion=row.Descripcion,
        precio=float(row.Precio),
        stock=row.Stock,
        id_categoria=row.Id_categoria,
        categoria=row.Categoria,
        imagen=row.Imagen,
    )


class SQLServerCategoriaRepository(CategoriaRepository):
    def find_all(self) -> List[Categoria]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT Id_categoria, Nombre, Descripcion FROM CATEGORIAS ORDER BY Nombre")
            return [Categoria(id_categoria=r.Id_categoria, nombre=r.Nombre, descripcion=r.Descripcion)
                    for r in cursor.fetchall()]
        finally:
            conn.close()

    def find_by_id(self, id_categoria: int) -> Optional[Categoria]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT Id_categoria, Nombre, Descripcion FROM CATEGORIAS WHERE Id_categoria = ?",
                id_categoria,
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return Categoria(id_categoria=row.Id_categoria, nombre=row.Nombre, descripcion=row.Descripcion)
        finally:
            conn.close()

    def save(self, categoria: Categoria) -> Categoria:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO CATEGORIAS (Nombre, Descripcion) OUTPUT INSERTED.Id_categoria VALUES (?, ?)",
                categoria.nombre, categoria.descripcion,
            )
            categoria.id = cursor.fetchone()[0]
            conn.commit()
            return categoria
        except pyodbc.IntegrityError:
            # El nombre de la categoría es UNIQUE en la base de datos
            raise CategoriaRepetidaError(f"Ya existe la categoría '{categoria.nombre}'")
        finally:
            conn.close()

    def contar_productos(self, id_categoria: int) -> int:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM PRODUCTOS WHERE Id_categoria = ?", id_categoria)
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def delete(self, id_categoria: int) -> bool:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM CATEGORIAS WHERE Id_categoria = ?", id_categoria)
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


class SQLServerProductoRepository(ProductoRepository):
    def find_all(self, id_categoria: Optional[int] = None, buscar: Optional[str] = None) -> List[Producto]:
        query = PRODUCTO_SELECT + " WHERE 1 = 1"
        params = []
        if id_categoria is not None:
            query += " AND p.Id_categoria = ?"
            params.append(id_categoria)
        if buscar:
            # %, _ y [ son comodines de LIKE: se "escapan" para que busquen el carácter tal cual
            # (si no, buscar "%" regresaría todos los productos)
            literal = buscar.replace("[", "[[]").replace("%", "[%]").replace("_", "[_]")
            query += " AND p.Nombre LIKE ?"
            params.append(f"%{literal}%")
        query += " ORDER BY p.Nombre"

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, *params)
            return [_row_to_producto(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def find_by_id(self, id_producto: int) -> Optional[Producto]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(PRODUCTO_SELECT + " WHERE p.Id_producto = ?", id_producto)
            row = cursor.fetchone()
            return _row_to_producto(row) if row else None
        finally:
            conn.close()

    def save(self, producto: Producto) -> Producto:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO PRODUCTOS (Nombre, Descripcion, Precio, Stock, Id_categoria, Imagen) "
                "OUTPUT INSERTED.Id_producto VALUES (?, ?, ?, ?, ?, ?)",
                producto.nombre, producto.descripcion, producto.precio, producto.stock, producto.id_categoria,
                producto.imagen,
            )
            producto.id = cursor.fetchone()[0]
            conn.commit()
        finally:
            conn.close()
        return self.find_by_id(producto.id)

    def update(self, producto: Producto) -> bool:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                # El Stock no va aquí a propósito: solo lo cambian las órdenes. Si se reescribiera,
                # se perdería una venta o compra que se complete al mismo tiempo que se edita
                "UPDATE PRODUCTOS SET Nombre = ?, Descripcion = ?, Precio = ?, Id_categoria = ?, Imagen = ? "
                "WHERE Id_producto = ?",
                producto.nombre, producto.descripcion, producto.precio,
                producto.id_categoria, producto.imagen, producto.id,
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete(self, id_producto: int) -> bool:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM PRODUCTOS WHERE Id_producto = ?", id_producto)
            conn.commit()
            return cursor.rowcount > 0
        except pyodbc.IntegrityError:
            # El producto ya está en una orden, promoción o movimiento de inventario
                raise ProductoEnUsoError("Este producto ya está en órdenes, promociones o movimientos de inventario: no se puede eliminar")
        finally:
            conn.close()

class SQLServerUsuarioRepository(UsuarioRepository):
    def rol_de_usuario(self, id_login: int) -> Optional[str]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT Rol FROM LOGIN WHERE Id_login = ?", id_login)
            row = cursor.fetchone()
            return row.Rol if row else None
        finally:
            conn.close()
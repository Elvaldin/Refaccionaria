from datetime import datetime
from typing import List, Optional
import pyodbc
from Domain.entities import Promocion, ProductoEnPromocion
from Application.promocion_use_cases import PromocionRepository, UsuarioRepository
from Infrastructure.database import get_db_connection

PROMOCION_SELECT = """
    SELECT Id_promocion, Nombre, Descripcion, Descuento, Fecha_inicio, Fecha_fin, Activa
    FROM PROMOCION
"""


def _row_to_promocion(row) -> Promocion:
    return Promocion(
        id_promocion=row.Id_promocion,
        nombre=row.Nombre,
        descripcion=row.Descripcion,
        descuento=float(row.Descuento),
        fecha_inicio=row.Fecha_inicio,
        fecha_fin=row.Fecha_fin,
        activa=bool(row.Activa),
    )


def _cargar_productos(cursor, promocion: Promocion) -> Promocion:
    cursor.execute(
        """
        SELECT p.Id_producto, p.Nombre, p.Precio
        FROM PROMOCIONPRODUCTO pp
        JOIN PRODUCTOS p ON p.Id_producto = pp.Id_producto
        WHERE pp.Id_promocion = ?
        ORDER BY p.Nombre
        """,
        promocion.id,
    )
    promocion.productos = [
        ProductoEnPromocion(r.Id_producto, r.Nombre, float(r.Precio), promocion.descuento)
        for r in cursor.fetchall()
    ]
    return promocion


class SQLServerPromocionRepository(PromocionRepository):
    def find_all(self, solo_vigentes: bool, ahora: datetime) -> List[Promocion]:
        query = PROMOCION_SELECT
        params = []
        if solo_vigentes:
            # Se usa la hora de Python y no GETDATE(): el SQL Server de Docker tiene la hora UTC
            query += " WHERE Activa = 1 AND ? BETWEEN Fecha_inicio AND Fecha_fin"
            params.append(ahora)
        query += " ORDER BY Fecha_inicio DESC"

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, *params)
            promociones = [_row_to_promocion(r) for r in cursor.fetchall()]
            return [_cargar_productos(cursor, p) for p in promociones]
        finally:
            conn.close()

    def find_by_id(self, id_promocion: int) -> Optional[Promocion]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(PROMOCION_SELECT + " WHERE Id_promocion = ?", id_promocion)
            row = cursor.fetchone()
            if row is None:
                return None
            return _cargar_productos(cursor, _row_to_promocion(row))
        finally:
            conn.close()

    def save(self, promocion: Promocion, ids_productos: List[int]) -> Promocion:
        # La promoción y sus productos se guardan juntos: si algo falla, no se guarda nada
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO PROMOCION (Nombre, Descripcion, Descuento, Fecha_inicio, Fecha_fin, Activa) "
                "OUTPUT INSERTED.Id_promocion VALUES (?, ?, ?, ?, ?, ?)",
                promocion.nombre, promocion.descripcion, promocion.descuento,
                promocion.fecha_inicio, promocion.fecha_fin, promocion.activa,
            )
            id_promocion = cursor.fetchone()[0]
            for id_producto in ids_productos:
                cursor.execute(
                    "INSERT INTO PROMOCIONPRODUCTO (Id_promocion, Id_producto) VALUES (?, ?)",
                    id_promocion, id_producto,
                )
            conn.commit()
            promocion.id = id_promocion
            return promocion
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def update(self, promocion: Promocion, ids_productos: Optional[List[int]] = None) -> bool:
        # Los datos y la lista de productos cambian juntos, en una sola transacción
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE PROMOCION SET Nombre = ?, Descripcion = ?, Descuento = ?, "
                "Fecha_inicio = ?, Fecha_fin = ?, Activa = ? WHERE Id_promocion = ?",
                promocion.nombre, promocion.descripcion, promocion.descuento,
                promocion.fecha_inicio, promocion.fecha_fin, promocion.activa, promocion.id,
            )
            actualizada = cursor.rowcount > 0
            if actualizada and ids_productos is not None:
                cursor.execute("DELETE FROM PROMOCIONPRODUCTO WHERE Id_promocion = ?", promocion.id)
                for id_producto in ids_productos:
                    cursor.execute(
                        "INSERT INTO PROMOCIONPRODUCTO (Id_promocion, Id_producto) VALUES (?, ?)",
                        promocion.id, id_producto,
                    )
            conn.commit()
            return actualizada
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete(self, id_promocion: int) -> bool:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            # Primero se quitan sus productos, porque PROMOCIONPRODUCTO depende de PROMOCION
            cursor.execute("DELETE FROM PROMOCIONPRODUCTO WHERE Id_promocion = ?", id_promocion)
            cursor.execute("DELETE FROM PROMOCION WHERE Id_promocion = ?", id_promocion)
            borradas = cursor.rowcount
            conn.commit()
            return borradas > 0
        finally:
            conn.close()

    def delete_vencidas(self, ahora: datetime) -> int:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            # Igual que en delete: primero sus productos y después la promoción, en una sola transacción
            cursor.execute(
                "DELETE FROM PROMOCIONPRODUCTO WHERE Id_promocion IN "
                "(SELECT Id_promocion FROM PROMOCION WHERE Fecha_fin < ?)",
                ahora,
            )
            cursor.execute("DELETE FROM PROMOCION WHERE Fecha_fin < ?", ahora)
            borradas = cursor.rowcount
            conn.commit()
            return borradas
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def producto_existe(self, id_producto: int) -> bool:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM PRODUCTOS WHERE Id_producto = ?", id_producto)
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def add_producto(self, id_promocion: int, id_producto: int) -> bool:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO PROMOCIONPRODUCTO (Id_promocion, Id_producto) VALUES (?, ?)",
                id_promocion, id_producto,
            )
            conn.commit()
            return True
        except pyodbc.IntegrityError as e:
            # Error 2627 de SQL Server = llave primaria repetida: el producto ya estaba agregado.
            # Cualquier otro (ej. 547: el producto o la promoción ya no existen) sí es un error
            if "2627" in str(e):
                return False
            raise
        finally:
            conn.close()

    def remove_producto(self, id_promocion: int, id_producto: int) -> bool:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM PROMOCIONPRODUCTO WHERE Id_promocion = ? AND Id_producto = ?",
                id_promocion, id_producto,
            )
            conn.commit()
            return cursor.rowcount > 0
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
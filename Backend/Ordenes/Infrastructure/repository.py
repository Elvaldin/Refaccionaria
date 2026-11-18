from datetime import datetime
from typing import Dict, List, Optional
from Domain.entities import Orden, DetalleOrden, MovimientoInventario
from Application.orden_use_cases import OrdenRepository, ProductoInfo, ConflictoError
from Infrastructure.database import get_db_connection

ORDEN_SELECT = "SELECT Id_orden, Id_login, Tipo, Observaciones, Estado, Fecha FROM ORDENES"


def _row_to_orden(row) -> Orden:
    return Orden(
        id_orden=row.Id_orden,
        id_login=row.Id_login,
        tipo=row.Tipo,
        observaciones=row.Observaciones,
        estado=row.Estado,
        fecha=row.Fecha,
        detalles=[],
    )


def _cargar_detalles(cursor, orden: Orden) -> Orden:
    cursor.execute(
        """
        SELECT d.Id_producto, p.Nombre, d.Cantidad, d.precio_unitario
        FROM DETALLEORDEN d
        JOIN PRODUCTOS p ON p.Id_producto = d.Id_producto
        WHERE d.Id_orden = ?
        ORDER BY d.Id_detalle
        """,
        orden.id,
    )
    orden.detalles = [
        DetalleOrden(id_producto=r.Id_producto, producto=r.Nombre, cantidad=r.Cantidad,
                     precio_unitario=float(r.precio_unitario))
        for r in cursor.fetchall()
    ]
    return orden


class SQLServerOrdenRepository(OrdenRepository):
    def find_all(self, tipo: Optional[str], estado: Optional[str], id_login: Optional[int] = None) -> List[Orden]:
        query = ORDEN_SELECT + " WHERE 1 = 1"
        params = []
        if tipo:
            query += " AND Tipo = ?"
            params.append(tipo)
        if estado:
            query += " AND Estado = ?"
            params.append(estado)
        if id_login is not None:
            query += " AND Id_login = ?"
            params.append(id_login)
        query += " ORDER BY Fecha DESC"

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, *params)
            ordenes = [_row_to_orden(r) for r in cursor.fetchall()]
            return [_cargar_detalles(cursor, o) for o in ordenes]
        finally:
            conn.close()

    def find_by_id(self, id_orden: int) -> Optional[Orden]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(ORDEN_SELECT + " WHERE Id_orden = ?", id_orden)
            row = cursor.fetchone()
            if row is None:
                return None
            return _cargar_detalles(cursor, _row_to_orden(row))
        finally:
            conn.close()

    def save(self, orden: Orden) -> int:
        # La orden y sus detalles se guardan juntos: si algo falla, no se guarda nada
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO ORDENES (Id_login, Tipo, Observaciones, Fecha) OUTPUT INSERTED.Id_orden VALUES (?, ?, ?, ?)",
                orden.id_login, orden.tipo, orden.observaciones, orden.fecha,
            )
            id_orden = cursor.fetchone()[0]
            for d in orden.detalles:
                cursor.execute(
                    "INSERT INTO DETALLEORDEN (Id_orden, Id_producto, Cantidad, precio_unitario) VALUES (?, ?, ?, ?)",
                    id_orden, d.id_producto, d.cantidad, d.precio_unitario,
                )
            conn.commit()
            return id_orden
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def rol_de_usuario(self, id_login: int) -> Optional[str]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT Rol FROM LOGIN WHERE Id_login = ?", id_login)
            row = cursor.fetchone()
            return row.Rol if row else None
        finally:
            conn.close()

    def find_productos(self, ids: List[int]) -> Dict[int, ProductoInfo]:
        marcas = ", ".join("?" for _ in ids)
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            # Descuento = el de la mejor promoción activa y vigente ahora (0 si no está en ninguna).
            # La hora sale de Python y no de SQL Server, por el reloj UTC de Docker
            cursor.execute(
                f"""
                SELECT p.Id_producto, p.Nombre, p.Precio, p.Stock,
                       ISNULL((SELECT MAX(pr.Descuento)
                               FROM PROMOCIONPRODUCTO pp
                               JOIN PROMOCION pr ON pr.Id_promocion = pp.Id_promocion
                               WHERE pp.Id_producto = p.Id_producto
                                 AND pr.Activa = 1 AND ? BETWEEN pr.Fecha_inicio AND pr.Fecha_fin), 0) AS Descuento
                FROM PRODUCTOS p
                WHERE p.Id_producto IN ({marcas})
                """,
                datetime.now(), *ids,
            )
            return {
                r.Id_producto: ProductoInfo(r.Nombre, float(r.Precio), r.Stock, float(r.Descuento))
                for r in cursor.fetchall()
            }
        finally:
            conn.close()

    def update_estado(self, id_orden: int, estado: str, estado_actual: str) -> bool:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            # Solo cambia si sigue en el estado que leímos (igual que en completar)
            cursor.execute(
                "UPDATE ORDENES SET Estado = ? WHERE Id_orden = ? AND Estado = ?",
                estado, id_orden, estado_actual,
            )
            cambiada = cursor.rowcount > 0
            conn.commit()
            return cambiada
        finally:
            conn.close()

    def completar(self, orden: Orden, fecha: datetime) -> None:
        # Todo va en una sola transacción: el stock, los movimientos y el estado
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            for d in orden.detalles:
                if orden.tipo == "Venta":
                    # El "AND Stock >= ?" evita que el stock quede negativo
                    cursor.execute(
                        "UPDATE PRODUCTOS SET Stock = Stock - ? WHERE Id_producto = ? AND Stock >= ?",
                        d.cantidad, d.id_producto, d.cantidad,
                    )
                    if cursor.rowcount == 0:
                        raise ConflictoError(f"No hay suficiente stock de '{d.producto}'")
                    tipo_movimiento = "Salida"
                else:
                    cursor.execute(
                        "UPDATE PRODUCTOS SET Stock = Stock + ? WHERE Id_producto = ?",
                        d.cantidad, d.id_producto,
                    )
                    tipo_movimiento = "Entrada"

                cursor.execute(
                    "INSERT INTO MOVIMIENTOS_INVENTARIO (Id_producto, Id_orden, Tipo, Cantidad, Observaciones, Fecha) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    d.id_producto, orden.id, tipo_movimiento, d.cantidad, f"{orden.tipo} - orden {orden.id}", fecha,
                )

            # Solo se completa si sigue en el estado que leímos (evita completarla dos veces)
            cursor.execute(
                "UPDATE ORDENES SET Estado = 'Completada' WHERE Id_orden = ? AND Estado = ?",
                orden.id, orden.estado,
            )
            if cursor.rowcount == 0:
                raise ConflictoError(f"La orden {orden.id} cambio de estado, intenta de nuevo")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def find_movimientos(self, id_producto: Optional[int]) -> List[MovimientoInventario]:
        query = """
            SELECT m.Id_movimiento, m.Id_producto, p.Nombre, m.Id_orden, m.Tipo, m.Cantidad,
                   m.Observaciones, m.Fecha
            FROM MOVIMIENTOS_INVENTARIO m
            JOIN PRODUCTOS p ON p.Id_producto = m.Id_producto
        """
        params = []
        if id_producto is not None:
            query += " WHERE m.Id_producto = ?"
            params.append(id_producto)
        query += " ORDER BY m.Fecha DESC, m.Id_movimiento DESC"

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, *params)
            return [
                MovimientoInventario(r.Id_movimiento, r.Id_producto, r.Nombre, r.Id_orden,
                                     r.Tipo, r.Cantidad, r.Observaciones, r.Fecha)
                for r in cursor.fetchall()
            ]
        finally:
            conn.close()
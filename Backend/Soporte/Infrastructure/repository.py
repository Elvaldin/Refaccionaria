from typing import List, Optional
from Domain.entities import Soporte, Conversacion, Mensaje
from Application.soporte_use_cases import SoporteRepository, ConversacionRepository, UsuarioRepository
from Infrastructure.database import get_db_connection

SOPORTE_SELECT = "SELECT Id_soporte, Correo, Telefono, Direccion, Horario FROM SOPORTE"

def _row_to_soporte(row) -> Soporte:
    return Soporte(
        id_soporte=row.Id_soporte,
        correo=row.Correo,
        telefono=row.Telefono,
        direccion=row.Direccion,
        horario=row.Horario,
    )

class SQLServerSoporteRepository(SoporteRepository):
    def find_all(self) -> List[Soporte]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(SOPORTE_SELECT +  " ORDER BY Id_soporte")
            return [_row_to_soporte(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def find_by_id(self, id_soporte: int) -> Optional[Soporte]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(SOPORTE_SELECT + " WHERE Id_soporte = ?", id_soporte)
            row = cursor.fetchone()
            return _row_to_soporte(row) if row else None
        finally:
            conn.close()

    def save(self, soporte: Soporte) -> Soporte:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO SOPORTE (Correo, Telefono, Direccion, Horario) OUTPUT INSERTED.Id_soporte VALUES (?, ?, ?, ?)",
                soporte.correo, soporte.telefono, soporte.direccion, soporte.horario,
                )
            soporte.id = cursor.fetchone()[0]
            conn.commit()
            return soporte
        finally:
            conn.close()

    def update(self, soporte: Soporte) -> bool:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE SOPORTE SET Correo = ?, Telefono = ?, Direccion = ?, Horario = ? WHERE Id_soporte = ?",
                soporte.correo, soporte.telefono, soporte.direccion, soporte.horario, soporte.id,
                )
            conn.commit()
            return cursor.rowcount > 0
        finally: 
            conn.close()

    def delete(self, id_soporte: int) -> bool:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM SOPORTE WHERE Id_soporte = ?", id_soporte)
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()



# ===== Chat de soporte =====
CONVERSACION_SELECT = """
    SELECT c.Id_conversacion, c.Id_login, l.Username, c.Asunto, c.Estado, c.CREATE_at
    FROM CONVERSACION c JOIN LOGIN l ON l.Id_login = c.Id_login
"""

MENSAJE_SELECT = """
    SELECT m.Id_mensaje, m.Id_conversacion, m.Id_login, l.Username, l.Rol, m.Texto, m.CREATE_at
    FROM MENSAJE m JOIN LOGIN l ON l.Id_login = m.Id_login
"""

def _row_to_conversacion(row) -> Conversacion:
    return Conversacion(id_conversacion=row.Id_conversacion, id_login=row.Id_login, cliente=row.Username,
                        asunto=row.Asunto, estado=row.Estado, fecha=row.CREATE_at)

def _row_to_mensaje(row) -> Mensaje:
    return Mensaje(id_mensaje=row.Id_mensaje, id_conversacion=row.Id_conversacion, id_login=row.Id_login,
                   autor=row.Username, rol=row.Rol, texto=row.Texto, fecha=row.CREATE_at)

class SQLServerConversacionRepository(ConversacionRepository, UsuarioRepository):
    def find_all(self, id_login: Optional[int]) -> List[Conversacion]:
        filtro, parametros = ("WHERE c.Id_login = ?", [id_login]) if id_login is not None else ("", [])
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(CONVERSACION_SELECT + filtro, *parametros)
            conversaciones = {r.Id_conversacion: _row_to_conversacion(r) for r in cursor.fetchall()}
            # Los mensajes de esas conversaciones, en una sola consulta
            cursor.execute(MENSAJE_SELECT + " JOIN CONVERSACION c ON c.Id_conversacion = m.Id_conversacion "
                           + filtro + " ORDER BY m.Id_mensaje", *parametros)
            for r in cursor.fetchall():
                conversaciones[r.Id_conversacion].mensajes.append(_row_to_mensaje(r))
        finally:
            conn.close()
        # Primero las que tienen el mensaje más reciente
        return sorted(conversaciones.values(), key=lambda c: c.ultimo_mensaje.id if c.ultimo_mensaje else 0, reverse=True)

    def find_by_id(self, id_conversacion: int) -> Optional[Conversacion]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(CONVERSACION_SELECT + " WHERE c.Id_conversacion = ?", id_conversacion)
            row = cursor.fetchone()
            if not row:
                return None
            conversacion = _row_to_conversacion(row)
            cursor.execute(MENSAJE_SELECT + " WHERE m.Id_conversacion = ? ORDER BY m.Id_mensaje", id_conversacion)
            conversacion.mensajes = [_row_to_mensaje(r) for r in cursor.fetchall()]
            return conversacion
        finally:
            conn.close()

    def save(self, conversacion: Conversacion) -> Conversacion:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO CONVERSACION (Id_login, Asunto, Estado, CREATE_at) OUTPUT INSERTED.Id_conversacion VALUES (?, ?, ?, ?)",
                conversacion.id_login, conversacion.asunto, conversacion.estado, conversacion.fecha,
            )
            conversacion.id = cursor.fetchone()[0]
            for mensaje in conversacion.mensajes:
                cursor.execute(
                    "INSERT INTO MENSAJE (Id_conversacion, Id_login, Texto, CREATE_at) VALUES (?, ?, ?, ?)",
                    conversacion.id, mensaje.id_login, mensaje.texto, mensaje.fecha,
                )
            conn.commit()   # la conversación y su primer mensaje se guardan juntos
            return conversacion
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def add_mensaje(self, mensaje: Mensaje) -> None:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO MENSAJE (Id_conversacion, Id_login, Texto, CREATE_at) VALUES (?, ?, ?, ?)",
                mensaje.id_conversacion, mensaje.id_login, mensaje.texto, mensaje.fecha,
            )
            conn.commit()
        finally:
            conn.close()

    def update_estado(self, id_conversacion: int, estado: str) -> None:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE CONVERSACION SET Estado = ? WHERE Id_conversacion = ?", estado, id_conversacion)
            conn.commit()
        finally:
            conn.close()

    def delete(self, id_conversacion: int) -> bool:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM MENSAJE WHERE Id_conversacion = ?", id_conversacion)
            cursor.execute("DELETE FROM CONVERSACION WHERE Id_conversacion = ?", id_conversacion)
            borrada = cursor.rowcount > 0
            conn.commit()   # los mensajes y la conversación se borran juntos
            return borrada
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
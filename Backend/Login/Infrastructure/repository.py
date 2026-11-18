from typing import Optional
from Domain.entities import User
from Infrastructure.database import get_db_connection
from Application.login_use_case import UserRepository

USER_SELECT = "SELECT Id_login, Username, Email, Password, Rol FROM LOGIN"


def _row_to_user(row) -> User:
    return User(username=row.Username, password_hash=row.Password, id_user=row.Id_login,
                rol=row.Rol, email=row.Email)


class SQLServerUserRepository(UserRepository):
    def find_by_username(self, username: str) -> Optional[User]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(USER_SELECT + " WHERE Username = ?", username)
            row = cursor.fetchone()
            return _row_to_user(row) if row else None
        finally:
            conn.close()

    def find_by_id(self, id_user: int) -> Optional[User]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(USER_SELECT + " WHERE Id_login = ?", id_user)
            row = cursor.fetchone()
            return _row_to_user(row) if row else None
        finally:
            conn.close()

    def email_existe(self, email: str) -> bool:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM LOGIN WHERE Email = ?", email)
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def save(self, user: User) -> int:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO LOGIN (Username, Email, Password, Rol) OUTPUT INSERTED.Id_login VALUES (?, ?, ?, ?)",
                user.username, user.email, user.password_hash, user.rol,
            )
            id_user = cursor.fetchone()[0]
            conn.commit()
            return id_user
        finally:
            conn.close()

    def update_password(self, id_user: int, password_hash: str) -> None:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE LOGIN SET Password = ? WHERE Id_login = ?", password_hash, id_user)
            conn.commit()
        finally:
            conn.close()

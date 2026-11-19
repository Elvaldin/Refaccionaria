"""Crea una cuenta de Administrador de la Refaccionaria desde la terminal.

Sirve para el primer Administrador del servidor de producción, donde no se
corre BD/12_usuarios_de_prueba.sql (sus contraseñas están en el README).
Después, ese Administrador crea las demás cuentas del personal desde la página.

    cd Backend/Login
    ../../.venv/bin/python crear_administrador.py          # lo guarda en la base del .env
    ../../.venv/bin/python crear_administrador.py --sql    # solo escribe el INSERT

Con --sql no se conecta a ninguna base: escribe en pantalla la instrucción
INSERT (con el hash bcrypt, nunca la contraseña) para pegarla en Cloud SQL
Studio, cuando la base de Google Cloud no se puede alcanzar desde tu computadora.

La contraseña se escribe sin que se vea en la pantalla y se guarda como
hash bcrypt, igual que cuando alguien se registra en la página.
"""
import os
import sys
from getpass import getpass

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Infrastructure.auth_services import BcryptPasswordHasher
from Application.login_use_case import CrearAdministrador, DatosInvalidosError, ConflictoError, UserRepository


class SoloEnMemoria(UserRepository):
    """Para --sql: no hay base; el usuario repetido lo rechaza SQL Server al pegar el INSERT."""
    def __init__(self):
        self.guardado = None

    def find_by_username(self, username):
        return None

    def find_by_id(self, id_user):
        return None

    def email_existe(self, email):
        return False

    def save(self, user):
        self.guardado = user
        return 0

    def update_password(self, id_user, password_hash):
        pass


def texto_sql(valor: str) -> str:
    """Un texto entre comillas para SQL Server (una ' se escribe '')."""
    return "N'" + valor.replace("'", "''") + "'"


def main():
    solo_sql = "--sql" in sys.argv[1:]
    username = input("Usuario del Administrador: ").strip()
    email = input("Correo: ").strip()
    password = getpass(f"Contraseña (mínimo {CrearAdministrador.MINIMO} caracteres): ")
    if getpass("Escríbela otra vez: ") != password:
        sys.exit("❌ No coinciden. No se creó nada.")

    if solo_sql:
        repositorio = SoloEnMemoria()
    else:
        from Infrastructure.repository import SQLServerUserRepository   # solo aquí hace falta la base
        repositorio = SQLServerUserRepository()
    crear = CrearAdministrador(user_repository=repositorio, password_hasher=BcryptPasswordHasher())
    try:
        user = crear.execute(username, email, password)
    except (DatosInvalidosError, ConflictoError) as e:
        sys.exit(f"❌ {e}. No se creó nada.")

    if solo_sql:
        print("\n-- Pega esto en Cloud SQL Studio, en la base Refaccionaria:")
        print("INSERT INTO LOGIN (Username, Email, Password, Rol) VALUES ("
              f"{texto_sql(user.username)}, {texto_sql(user.email)}, {texto_sql(user.password_hash)}, N'Administrador');")
        return
    print(f"✅ Listo: se creó el Administrador '{user.username}' (id {user.id}).")


if __name__ == "__main__":
    main()

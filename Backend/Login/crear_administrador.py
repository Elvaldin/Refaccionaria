"""Crea una cuenta de Administrador de la Refaccionaria desde la terminal.

Sirve para el primer Administrador del servidor de producción, donde no se
corre BD/12_usuarios_de_prueba.sql (sus contraseñas están en el README).
Después, ese Administrador crea las demás cuentas del personal desde la página.

    cd Backend/Login
    ../../.venv/bin/python crear_administrador.py

La contraseña se escribe sin que se vea en la pantalla y se guarda como
hash bcrypt, igual que cuando alguien se registra en la página.
"""
import os
import sys
from getpass import getpass

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Infrastructure.repository import SQLServerUserRepository
from Infrastructure.auth_services import BcryptPasswordHasher
from Application.login_use_case import CrearAdministrador, DatosInvalidosError, ConflictoError


def main():
    username = input("Usuario del Administrador: ").strip()
    email = input("Correo: ").strip()
    password = getpass(f"Contraseña (mínimo {CrearAdministrador.MINIMO} caracteres): ")
    if getpass("Escríbela otra vez: ") != password:
        sys.exit("❌ No coinciden. No se creó nada.")

    crear = CrearAdministrador(user_repository=SQLServerUserRepository(),
                               password_hasher=BcryptPasswordHasher())
    try:
        user = crear.execute(username, email, password)
    except (DatosInvalidosError, ConflictoError) as e:
        sys.exit(f"❌ {e}. No se creó nada.")
    print(f"✅ Listo: se creó el Administrador '{user.username}' (id {user.id}).")


if __name__ == "__main__":
    main()

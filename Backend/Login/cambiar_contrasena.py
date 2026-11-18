"""Cambia la contraseña de un usuario de la Refaccionaria desde la terminal.

Sirve, por ejemplo, para ponerle al admin una contraseña real y larga antes
de publicar la tienda (la de prueba, Admin123, está escrita en el README).

    cd Backend/Login
    ../../.venv/bin/python cambiar_contrasena.py admin

La contraseña se escribe sin que se vea en la pantalla y se guarda como
hash bcrypt, igual que cuando alguien se registra en la página.
"""
import os
import sys
from getpass import getpass

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Infrastructure.repository import SQLServerUserRepository
from Infrastructure.auth_services import BcryptPasswordHasher
from Application.login_use_case import CambiarContrasena, DatosInvalidosError, NoEncontradoError


def main():
    username = sys.argv[1] if len(sys.argv) > 1 else input("Usuario: ").strip()
    nueva = getpass(f"Contraseña nueva para '{username}' (mínimo {CambiarContrasena.MINIMO} caracteres): ")
    if getpass("Escríbela otra vez: ") != nueva:
        sys.exit("❌ No coinciden. No se cambió nada.")

    cambiar = CambiarContrasena(user_repository=SQLServerUserRepository(),
                                password_hasher=BcryptPasswordHasher())
    try:
        user = cambiar.execute(username, nueva)
    except (NoEncontradoError, DatosInvalidosError) as e:
        sys.exit(f"❌ {e}. No se cambió nada.")
    print(f"✅ Listo: se cambió la contraseña de '{user.username}' ({user.rol}).")
    print("   Las sesiones que ya estaban abiertas siguen activas hasta que venza su token (8 horas).")


if __name__ == "__main__":
    main()

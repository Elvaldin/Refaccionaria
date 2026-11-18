"""Infraestructura: tokens de sesión firmados (sin librerías extra).

El token lleva el id del usuario y cuándo vence, firmado con TOKEN_SECRETO
(HMAC-SHA256). Si alguien cambia el id dentro del token, la firma ya no
coincide y el token se rechaza. Este archivo es igual en los 5 microservicios.
"""
import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# .env de este microservicio, sin importar desde qué carpeta se corra uvicorn
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DURACION_SEGUNDOS = 8 * 60 * 60   # la sesión dura 8 horas


def _secreto() -> bytes:
    secreto = os.getenv("TOKEN_SECRETO")
    if not secreto or len(secreto) < 32:
        raise RuntimeError("Falta TOKEN_SECRETO (mínimo 32 caracteres) en el .env de este microservicio")
    return secreto.encode()


def _a_b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def _desde_b64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _firmar(carga: str) -> str:
    return _a_b64(hmac.new(_secreto(), carga.encode(), hashlib.sha256).digest())


def crear_token(id_login: int) -> str:
    """Regresa un token como 'carga.firma' para el usuario que inició sesión."""
    datos = {"id": id_login, "vence": int(time.time()) + DURACION_SEGUNDOS}
    carga = _a_b64(json.dumps(datos).encode())
    return f"{carga}.{_firmar(carga)}"


def leer_token(token: str) -> Optional[int]:
    """Regresa el id_login del token, o None si es falso, está alterado o ya venció."""
    try:
        carga, firma = token.split(".")
        if not hmac.compare_digest(firma, _firmar(carga)):
            return None
        datos = json.loads(_desde_b64(carga))
        if datos["vence"] < time.time():
            return None
        return int(datos["id"])
    except (ValueError, KeyError, TypeError):
        return None
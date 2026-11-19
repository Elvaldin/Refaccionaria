"""Infraestructura: conexión a SQL Server.

Lee los datos de conexión del archivo .env que está en la carpeta del
microservicio (por ejemplo Backend/Productos/.env). Este archivo es igual
en los 5 microservicios.
"""
import os
from pathlib import Path

import pyodbc
from dotenv import load_dotenv

# .env de este microservicio, sin importar desde qué carpeta se corra uvicorn
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def confiar_en_certificado() -> bool:
    """¿Se acepta el certificado del servidor sin revisar quién lo firmó?

    La conexión SIEMPRE va cifrada (Encrypt=yes). Lo que cambia es si se
    revisa el certificado de SQL Server:
      - En tu computadora, SQL Server (Docker) usa un certificado hecho por él
        mismo, así que se acepta tal cual (BD_CONFIAR_CERTIFICADO=si).
      - En producción (ENTORNO=produccion) se revisa, salvo que se pida otra
        cosa: así nadie en medio puede hacerse pasar por la base de datos.
    """
    valor = os.getenv("BD_CONFIAR_CERTIFICADO", "").strip().lower()
    if valor in ("si", "sí", "yes"):
        return True
    if valor == "no":
        return False
    return os.getenv("ENTORNO") != "produccion"


def get_db_connection():
    driver = os.getenv("BD_DRIVER", "ODBC Driver 17 for SQL Server")
    server = os.getenv("BD_SERVER", "localhost,1433")
    database = os.getenv("BD_NAME", "Refaccionaria")
    username = os.getenv("BD_USER")
    password = os.getenv("BD_PASSWORD")

    # Sin usuario no se entra con "sa" por omisión: hay que decir con cuál
    if not username or not password:
        raise RuntimeError("Faltan BD_USER o BD_PASSWORD en el archivo .env de este microservicio (copia Backend/.env.example)")

    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        "Encrypt=yes;"
        f"TrustServerCertificate={'yes' if confiar_en_certificado() else 'no'};"
    )

    return pyodbc.connect(conn_str)

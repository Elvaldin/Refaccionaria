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


def get_db_connection():
    driver = os.getenv("BD_DRIVER", "ODBC Driver 17 for SQL Server")
    server = os.getenv("BD_SERVER", "localhost,1433")
    database = os.getenv("BD_NAME", "Refaccionaria")
    username = os.getenv("BD_USER", "sa")
    password = os.getenv("BD_PASSWORD")

    if not password:
        raise RuntimeError("Falta BD_PASSWORD en el archivo .env de este microservicio (copia Backend/.env.example)")

    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
    )

    return pyodbc.connect(conn_str)

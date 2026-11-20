"""Corre scripts .sql (con GO) en Amazon RDS con el usuario maestro.

Lo usa aws/cargar_base.sh, dentro de un contenedor con la imagen de los
microservicios (que ya trae pyodbc, el conector ODBC 18 y los certificados de RDS).

- La contraseña llega por la entrada estándar: no queda en variables de entorno,
  en la lista de procesos ni en la pantalla.
- Acepta lo que se copie de Secrets Manager: solo la contraseña (con o sin
  comillas) o el texto completo del secreto ({"username": ..., "password": ...}).
- La conexión va cifrada y revisa el certificado de RDS (TrustServerCertificate=no).
- No imprime el contenido de los resultados, solo cuántas filas hubo.
"""
import json
import os
import re
import sys

import pyodbc

texto = sys.stdin.readline().strip()
if texto.startswith("{"):
    try:
        texto = json.loads(texto)["password"]
        print("(Se pegó el texto completo del secreto: se tomó solo el campo password)")
    except (ValueError, KeyError):
        pass
if len(texto) >= 2 and texto[0] == texto[-1] and texto[0] in "\"'":
    texto = texto[1:-1]
    print("(Se quitaron las comillas de los extremos)")
clave = texto
print(f"Contraseña recibida: {len(clave)} caracteres (no se muestra)")
if not clave:
    sys.exit("❌ No llegó ninguna contraseña. Vuelve a intentarlo y pégala antes de presionar Enter.")

servidor = os.environ["BD_SERVER"]
usuario = os.environ["MAESTRO_USUARIO"]
conexion = pyodbc.connect(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={servidor};DATABASE=master;UID={usuario};"
    "PWD={" + clave.replace("}", "}}") + "};"
    "Encrypt=yes;TrustServerCertificate=no;",
    autocommit=True, timeout=20,
)
del clave, texto
cursor = conexion.cursor()
cursor.execute("SELECT @@VERSION")
print("Conectado (certificado de RDS revisado):", cursor.fetchone()[0].splitlines()[0])

for archivo in sys.argv[1:]:
    contenido = open(archivo, encoding="utf-8-sig").read()
    lotes = [l for l in re.split(r"^\s*GO\s*;?\s*$", contenido, flags=re.M | re.I) if l.strip()]
    print(f"== {os.path.basename(archivo)} ({len(lotes)} partes)")
    for numero, lote in enumerate(lotes, 1):
        try:
            cursor.execute(lote)
            while True:
                if cursor.description:
                    print(f"   parte {numero}: {len(cursor.fetchall())} filas")
                if not cursor.nextset():
                    break
        except pyodbc.Error as error:
            print(f"   ❌ parte {numero}: {error}")
            sys.exit(1)
print("✅ Scripts terminados")

# Una sola receta para los 5 microservicios de Python.
# Al construir se dice cuál: SERVICIO=Login, Productos, Promociones, Ordenes o Soporte
#   docker build --build-arg SERVICIO=Login -t refaccionaria-login Backend
#
# La imagen NO lleva contraseñas: BD_PASSWORD, TOKEN_SECRETO, etc. se dan al
# arrancar el contenedor (docker-compose.yml en tu Mac, Secret Manager en Google Cloud).
FROM python:3.15-slim-bookworm

# Conector de Microsoft para SQL Server (ODBC Driver 18).
# ACCEPT_EULA=Y acepta la licencia de Microsoft de ese conector.
# libgssapi-krb5-2 se instala a propósito: el conector la necesita y, si no,
# el "autoremove" del final la borra junto con curl y gnupg.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl gnupg ca-certificates \
 && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
      | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
      > /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update \
 && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc libgssapi-krb5-2 tzdata \
 && apt-get purge -y curl gnupg \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Primero las librerías: así Docker las reutiliza para los 5 servicios
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ARG SERVICIO
COPY ${SERVICIO}/ .

# Corre como un usuario normal, no como administrador (root)
RUN useradd --create-home --uid 10001 app
USER app

# TZ: la hora de la tienda. Sin esto el contenedor (y Google Cloud) usa UTC,
# 6 horas adelante: las órdenes se guardarían con otra hora y una promoción
# que empieza "hoy" en México se vería como si hubiera empezado "ayer".
ENV BD_DRIVER="ODBC Driver 18 for SQL Server" \
    TZ=America/Mexico_City \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Google Cloud Run dice en qué puerto escuchar con la variable PORT (8080 si no viene)
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn API.main:app --host 0.0.0.0 --port ${PORT:-8080}"]

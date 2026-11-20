#!/bin/bash
# Carga la base de la Refaccionaria en Amazon RDS y crea los .env del servidor.
# Se corre EN EL SERVIDOR EC2, desde la carpeta del proyecto:
#
#   ./aws/cargar_base.sh <endpoint-de-RDS> <dominio>
#   ./aws/cargar_base.sh refaccionaria-bd.xxxx.us-east-2.rds.amazonaws.com 3-148-60-126.sslip.io
#
# - Pide la contraseña del usuario maestro de RDS (la de Secrets Manager); no se ve al escribir.
# - Corre BD/01_crear_base.sql, BD/02_datos_ejemplo.sql y BD/13_usuarios_por_microservicio.sql.
# - Las 5 contraseñas de los microservicios y el TOKEN_SECRETO los inventa aquí, al azar,
#   y los escribe directo en los .env del servidor: nadie los ve.
# - RDS nunca se abre a Internet: el servidor llega a ella por la red privada de AWS.
#
# ⚠️ Pégale la contraseña desde la app Terminal de tu Mac (por ssh -t): el panel
#    Terminal de Claude no pega texto en una contraseña oculta.
set -euo pipefail
ENDPOINT="${1:?Falta el endpoint de RDS (RDS -> refaccionaria-bd -> Conectividad)}"
DOMINIO="${2:?Falta el dominio, por ejemplo 3-148-60-126.sslip.io}"
cd "$(dirname "$0")/.."

# La imagen de los microservicios trae pyodbc, el conector ODBC 18 y los certificados de RDS
if ! docker image inspect refaccionaria-herramienta >/dev/null 2>&1; then
    echo "Construyendo la imagen para cargar la base (solo la primera vez)..."
    docker build -q --build-arg SERVICIO=Login -t refaccionaria-herramienta Backend >/dev/null
fi

echo "Refaccionaria: cargar la base en $ENDPOINT"
read -rp "Usuario administrador de RDS [adminrds]: " USUARIO; USUARIO=${USUARIO:-adminrds}
read -rsp "Contraseña de $USUARIO (cópiala de Secrets Manager; no se ve al escribir): " CLAVE; echo

# 5 contraseñas nuevas para los microservicios: nadie las ve
nueva() { python3 -c "import secrets; print(secrets.token_urlsafe(24) + 'Aa1_')"; }
TMP=$(mktemp -d); chmod 700 "$TMP"; trap 'rm -rf "$TMP"' EXIT
cp BD/01_crear_base.sql BD/02_datos_ejemplo.sql "$TMP/"
cp BD/13_usuarios_por_microservicio.sql "$TMP/13.sql"
declare -A CLAVES
for S in LOGIN PRODUCTOS PROMOCIONES ORDENES SOPORTE; do
    CLAVES[$S]=$(nueva)
    sed -i "s|N'PEGA-AQUI-LA-CONTRASENA-DE-$S'|N'${CLAVES[$S]}'|" "$TMP/13.sql"
done
# (El 13 menciona "PEGA-AQUI" también en sus comentarios: se revisan solo los 5 lugares)
if grep -q "N'PEGA-AQUI-LA-CONTRASENA-DE-" "$TMP/13.sql"; then echo "❌ No se pusieron las 5 contraseñas"; exit 1; fi

# El contenedor corre con el usuario del servidor, para poder leer la carpeta privada $TMP
printf '%s\n' "$CLAVE" | docker run --rm -i --user "$(id -u):$(id -g)" \
    -e BD_SERVER="$ENDPOINT,1433" -e MAESTRO_USUARIO="$USUARIO" \
    -v "$TMP":/trabajo:ro -v "$PWD/aws/correr_sql.py":/correr_sql.py:ro \
    --entrypoint python refaccionaria-herramienta /correr_sql.py \
    /trabajo/01_crear_base.sql /trabajo/02_datos_ejemplo.sql /trabajo/13.sql
unset CLAVE

TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(32))")
umask 077
for PAR in Login:login Productos:productos Promociones:promociones Ordenes:ordenes Soporte:soporte; do
    CARPETA=${PAR%%:*}; NOMBRE=${PAR##*:}; MAYUS=$(echo "$NOMBRE" | tr a-z A-Z)
    cat > "Backend/$CARPETA/.env" <<EOF
BD_SERVER=$ENDPOINT,1433
BD_NAME=Refaccionaria
BD_USER=refaccionaria_$NOMBRE
BD_PASSWORD=${CLAVES[$MAYUS]}
TOKEN_SECRETO=$TOKEN
BD_CONFIAR_CERTIFICADO=no
EOF
done
echo "DOMINIO=$DOMINIO" > aws/.env
chmod 600 Backend/*/.env aws/.env
docker rmi -f refaccionaria-herramienta >/dev/null 2>&1 || true
echo "✅ Base cargada y los 6 archivos .env creados en el servidor (nadie vio las contraseñas)."

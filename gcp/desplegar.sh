#!/bin/bash
# Sube la Refaccionaria a Google Cloud Run: 5 microservicios privados + el Gateway
# público (que también entrega la página). Antes sigue los pasos 1 a 6 de
# docs/DESPLIEGUE_GCP.md (proyecto, red, Cloud SQL, base de datos y secretos).
#
#   PROYECTO=mi-proyecto BD_SERVER=10.20.0.3,1433 ./gcp/desplegar.sh
#
# Variables (las demás tienen un valor por omisión):
#   PROYECTO   (obligatoria) id del proyecto de Google Cloud
#   BD_SERVER  (obligatoria) IP privada de Cloud SQL y puerto, ej. 10.20.0.3,1433
#   REGION     us-central1
#   RED        refaccionaria       (la red VPC)
#   SUBRED     refaccionaria-run   (la subred para Cloud Run, con Private Google Access)
#   CORS_ORIGENES                  (vacía = ningún otro sitio puede llamar a la API)
#
# Se puede correr varias veces: cada vez construye y publica una versión nueva.
set -euo pipefail
cd "$(dirname "$0")/.."

: "${PROYECTO:?Falta PROYECTO=<id de tu proyecto de Google Cloud>}"
: "${BD_SERVER:?Falta BD_SERVER=<IP privada de Cloud SQL>,1433}"
REGION="${REGION:-us-central1}"
RED="${RED:-refaccionaria}"
SUBRED="${SUBRED:-refaccionaria-run}"
CORS_ORIGENES="${CORS_ORIGENES:-}"
REPO=refaccionaria
IMAGENES="$REGION-docker.pkg.dev/$PROYECTO/$REPO"
MICROSERVICIOS="login productos promociones ordenes soporte"

# La etiqueta de las imágenes es el commit: así se sabe qué versión está publicada
if [ -n "$(git status --porcelain)" ]; then
    echo "⚠️  Hay cambios sin commit: lo que se publique no corresponde a ningún commit."
    read -r -p "¿Seguir de todos modos? (s/N) " respuesta
    [ "$respuesta" = "s" ] || exit 1
    ETIQUETA="$(git rev-parse --short HEAD)-cambios-$(date +%Y%m%d%H%M)"
else
    ETIQUETA="$(git rev-parse --short HEAD)"
fi

g() { gcloud --project "$PROYECTO" --quiet "$@"; }

echo "== 1) Revisar los secretos de Secret Manager"
faltan=0
for secreto in refaccionaria-token $(for s in $MICROSERVICIOS; do echo "refaccionaria-bd-$s"; done); do
    if ! g secrets describe "$secreto" >/dev/null 2>&1; then
        echo "   ❌ falta el secreto $secreto (ver el paso 6 de docs/DESPLIEGUE_GCP.md)"
        faltan=1
    fi
done
[ $faltan -eq 0 ] || exit 1

echo "== 2) Repositorio de imágenes (Artifact Registry)"
g artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1 \
    || g artifacts repositories create "$REPO" --repository-format docker --location "$REGION"

echo "== 3) Construir las 6 imágenes en Cloud Build (etiqueta $ETIQUETA)"
g builds submit --config cloudbuild.yaml \
    --substitutions "_REGION=$REGION,_REPO=$REPO,_ETIQUETA=$ETIQUETA" .

# Una cuenta de servicio (identidad) para cada servicio: cada microservicio solo
# puede leer SUS secretos, y solo el Gateway puede llamar a los microservicios
cuenta() { echo "refaccionaria-$1@$PROYECTO.iam.gserviceaccount.com"; }
crear_cuenta() {
    g iam service-accounts describe "$(cuenta "$1")" >/dev/null 2>&1 \
        || g iam service-accounts create "refaccionaria-$1" --display-name "Refaccionaria: $1"
}

echo "== 4) Microservicios (privados: solo el Gateway llega a ellos)"
crear_cuenta gateway
for s in $MICROSERVICIOS; do
    crear_cuenta "$s"
    for secreto in "refaccionaria-bd-$s" refaccionaria-token; do
        g secrets add-iam-policy-binding "$secreto" --member "serviceAccount:$(cuenta "$s")" \
            --role roles/secretmanager.secretAccessor >/dev/null
    done
    # "^|^" al principio: las variables se separan con | porque BD_SERVER lleva coma
    g run deploy "$s" \
        --image "$IMAGENES/$s:$ETIQUETA" \
        --region "$REGION" \
        --service-account "$(cuenta "$s")" \
        --no-allow-unauthenticated \
        --ingress internal \
        --network "$RED" --subnet "$SUBRED" --vpc-egress private-ranges-only \
        --set-env-vars "^|^ENTORNO=produccion|BD_SERVER=$BD_SERVER|BD_NAME=Refaccionaria|BD_USER=refaccionaria_$s|BD_CONFIAR_CERTIFICADO=si" \
        --set-secrets "BD_PASSWORD=refaccionaria-bd-$s:latest,TOKEN_SECRETO=refaccionaria-token:latest" \
        --memory 512Mi --max-instances 3
    # URL_login, URL_productos... (con printf -v porque el bash de macOS no tiene arreglos con nombre)
    printf -v "URL_$s" '%s' "$(g run services describe "$s" --region "$REGION" --format 'value(status.url)')"
    # Solo la cuenta del Gateway puede llamar a este microservicio
    g run services add-iam-policy-binding "$s" --region "$REGION" \
        --member "serviceAccount:$(cuenta gateway)" --role roles/run.invoker >/dev/null
done

echo "== 5) Gateway (público: la página y /api)"
# --vpc-egress all-traffic: sus llamadas a los microservicios salen por la red
# privada, que es lo único que aceptan (--ingress internal).
# --max-instances 1: el límite de intentos de login vive en memoria; con una sola
# copia del Gateway cuenta todos los intentos juntos.
g run deploy gateway \
    --image "$IMAGENES/gateway:$ETIQUETA" \
    --region "$REGION" \
    --service-account "$(cuenta gateway)" \
    --allow-unauthenticated \
    --ingress all \
    --network "$RED" --subnet "$SUBRED" --vpc-egress all-traffic \
    --set-env-vars "^|^ENTORNO=produccion|PROXIES_DE_CONFIANZA=1|IDENTIDAD_GOOGLE=si|CORS_ORIGENES=$CORS_ORIGENES|URL_LOGIN=$URL_login|URL_PRODUCTOS=$URL_productos|URL_PROMOCIONES=$URL_promociones|URL_ORDENES=$URL_ordenes|URL_SOPORTE=$URL_soporte" \
    --memory 256Mi --max-instances 1

echo
echo "✅ Listo. La tienda quedó en: $(g run services describe gateway --region "$REGION" --format 'value(status.url)')"
echo "   Revisa el paso 8 de docs/DESPLIEGUE_GCP.md (comprobar que todo funciona)."

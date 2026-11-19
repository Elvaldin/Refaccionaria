# Publicar la Refaccionaria en Google Cloud

Esta guía sube la tienda a Google Cloud Platform (GCP) con **Cloud Run** para el Gateway y los 5 microservicios, y **Cloud SQL for SQL Server** para la base de datos.

> ⚠️ **Costo.** Cloud SQL se cobra por cada hora que está prendido, aunque nadie entre a la tienda: es lo más caro de todo. Cloud Run casi no cuesta con poco tráfico (tiene un nivel gratuito). Antes de empezar, revisa la [calculadora de precios](https://cloud.google.com/products/calculator) y crea una **alerta de presupuesto** (Facturación → Presupuestos y alertas). Si solo es para presentarlo en clase, borra todo al terminar (paso 12).

## Cómo queda

```
Internet ──HTTPS──▶ Cloud Run "gateway"  (público: la página y /api)
                       │  red privada (VPC) + token de identidad de Google
                       ▼
            Cloud Run "login", "productos", "promociones", "ordenes", "soporte"
            (privados: --ingress internal y --no-allow-unauthenticated)
                       │  red privada, conexión cifrada
                       ▼
            Cloud SQL for SQL Server (solo IP privada, sin IP pública)
```

- Solo el Gateway se puede abrir desde Internet. Los microservicios no aceptan nada que no venga de la red privada **y** con la identidad del Gateway.
- Cada servicio tiene su propia cuenta de servicio y solo puede leer **sus** secretos.
- HTTPS lo pone Google en la dirección `https://gateway-….run.app` (y en tu dominio, si conectas uno).
- Las contraseñas viven en **Secret Manager**, no en archivos `.env`.

Necesitas la [CLI de Google Cloud](https://cloud.google.com/sdk/docs/install) (`gcloud`), o usar **Cloud Shell** desde la consola, que ya la trae.

En los comandos, cambia `mi-proyecto` por el id de tu proyecto. La región de ejemplo es `us-central1`.

```bash
export PROYECTO=mi-proyecto REGION=us-central1
gcloud config set project $PROYECTO
```

## 1. Proyecto y servicios de Google

Crea el proyecto en la consola (con la facturación activada) y prende los servicios que se usan:

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com sqladmin.googleapis.com compute.googleapis.com \
  servicenetworking.googleapis.com iam.googleapis.com
```

## 2. Red privada (VPC)

Una red propia, una subred para Cloud Run (con **Private Google Access**, para que el Gateway llegue a los microservicios por dentro) y un rango reservado para Cloud SQL:

```bash
gcloud compute networks create refaccionaria --subnet-mode custom
gcloud compute networks subnets create refaccionaria-run --network refaccionaria \
  --region $REGION --range 10.10.0.0/24 --enable-private-ip-google-access

gcloud compute addresses create refaccionaria-cloudsql --global --purpose VPC_PEERING \
  --prefix-length 16 --network refaccionaria
gcloud services vpc-peerings connect --service servicenetworking.googleapis.com \
  --ranges refaccionaria-cloudsql --network refaccionaria
```

## 3. Cloud SQL for SQL Server

Edición **Express** (la más barata), solo con IP privada y con respaldos automáticos diarios:

```bash
gcloud sql instances create refaccionaria-bd \
  --database-version SQLSERVER_2022_EXPRESS --tier db-custom-1-3840 \
  --region $REGION --network refaccionaria --no-assign-ip \
  --backup-start-time 09:00 --root-password "$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
gcloud sql users set-password sqlserver --instance refaccionaria-bd --prompt-for-password
```

La segunda línea te pide la contraseña del administrador de la base (el usuario `sqlserver`, que en Cloud SQL hace las veces de `sa`); guárdala en tu gestor de contraseñas. Si Google rechaza el tamaño `db-custom-1-3840`, revisa los tamaños permitidos para SQL Server Express en tu región.

Anota la IP privada (la usarás como `BD_SERVER`):

```bash
gcloud sql instances describe refaccionaria-bd --format 'value(ipAddresses[0].ipAddress)'
```

## 4. Cargar la base de datos

Los scripts usan `GO`, así que hay que correrlos con `sqlcmd`, Azure Data Studio o SSMS. Como la base solo tiene IP privada, la forma más sencilla es **prenderle una IP pública por unos minutos**, solo para tu IP:

```bash
MI_IP=$(curl -s https://ifconfig.me)
gcloud sql instances patch refaccionaria-bd --assign-ip --authorized-networks "$MI_IP/32"
gcloud sql instances describe refaccionaria-bd --format 'value(ipAddresses)'   # la IP pública
```

Conéctate con el usuario `sqlserver` (con cifrado) y corre, en este orden:

1. `BD/01_crear_base.sql` (tablas e índices)
2. `BD/02_datos_ejemplo.sql` (catálogo y contacto: **cambia antes los precios y existencias por los tuyos**)
3. `BD/13_usuarios_por_microservicio.sql` con **5 contraseñas nuevas y distintas** (anótalas: van en el paso 6). Cierra el archivo sin guardar.

**No** corras `BD/10_usuario_app.sql` (un usuario con permiso en todo) ni `BD/12_usuarios_de_prueba.sql` (contraseñas públicas).

## 5. El primer Administrador

Con la IP pública todavía prendida, desde tu computadora:

```bash
cd Backend/Login
BD_SERVER="<IP pública>,1433" BD_DRIVER="ODBC Driver 17 for SQL Server" \
BD_USER=refaccionaria_login BD_PASSWORD="<la de refaccionaria_login>" \
  ../../.venv/bin/python crear_administrador.py
```

(Escribe la contraseña de `refaccionaria_login` directo en ese comando solo si tu terminal no guarda el historial; si no, ponla en `Backend/Login/.env` un momento y bórrala después.)

Otra opción, sin conectarte: `../../.venv/bin/python crear_administrador.py --sql` escribe la instrucción `INSERT` con el hash bcrypt para pegarla en **Cloud SQL Studio** (en la consola de Cloud SQL).

**Al terminar, quita la IP pública:**

```bash
gcloud sql instances patch refaccionaria-bd --no-assign-ip --clear-authorized-networks
```

## 6. Secretos (Secret Manager)

Un secreto para la clave de los tokens y uno por microservicio con su contraseña de SQL Server. `read -s` las pide sin que se vean ni queden en el historial:

```bash
python3 -c "import secrets; print(secrets.token_hex(32), end='')" \
  | gcloud secrets create refaccionaria-token --data-file=-

for s in login productos promociones ordenes soporte; do
  read -r -s -p "Contraseña de refaccionaria_$s: " clave; echo
  printf '%s' "$clave" | gcloud secrets create refaccionaria-bd-$s --data-file=-
done
unset clave
```

Para cambiar una contraseña después: `gcloud secrets versions add refaccionaria-bd-login --data-file=-` y vuelve a desplegar.

## 7. Desplegar

Con todo lo anterior listo (y los cambios con commit):

```bash
PROYECTO=$PROYECTO REGION=$REGION BD_SERVER="<IP privada de Cloud SQL>,1433" ./gcp/desplegar.sh
```

El script:

1. Revisa que existan los 6 secretos.
2. Crea el repositorio de imágenes (Artifact Registry) si no existe.
3. Construye las 6 imágenes en **Cloud Build** (`cloudbuild.yaml`), para linux/amd64. Solo se suben `Backend/`, `Backend-Go/` y `Frontend/` (ver `.gcloudignore`): nunca los `.env`.
4. Publica los 5 microservicios: privados, con su cuenta de servicio, `ENTORNO=produccion`, su usuario de SQL Server y sus secretos.
5. Publica el Gateway: público, `ENTORNO=produccion`, `PROXIES_DE_CONFIANZA=1`, `IDENTIDAD_GOOGLE=si`, las URL de los microservicios y **una sola copia** (`--max-instances 1`, para que el límite de intentos de login cuente todos los intentos juntos).

Al final escribe la dirección de la tienda.

## 8. Comprobar que todo funciona

```bash
TIENDA=$(gcloud run services describe gateway --region $REGION --format 'value(status.url)')
curl -sI $TIENDA/ | grep -i -E "strict-transport|content-security|x-frame"   # deben salir los 3
curl -s $TIENDA/api/categorias                                                  # la lista de categorías
curl -s -o /dev/null -w "%{http_code}\n" $TIENDA/gateway                        # 404: apagado en producción
curl -s -o /dev/null -w "%{http_code}\n" $(gcloud run services describe login --region $REGION --format 'value(status.url)')/openapi.json   # 404 o 403: privado
```

1. Abre la tienda en el navegador, entra con tu Administrador y haz una compra de prueba completa.
2. **Revisa la IP del límite de login.** En Cloud Logging (servicio `gateway`), cada petición empieza con la IP del visitante. Debe ser la de tu casa (compárala con `curl -s https://ifconfig.me`). Si sale otra, por ejemplo una `169.254.x.x` igual para todos, cambia `PROXIES_DE_CONFIANZA` en `gcp/desplegar.sh` y vuelve a desplegar.

## 9. Tu dominio (opcional)

La dirección `https://gateway-….run.app` ya tiene HTTPS. Para usar tu propio dominio:

- **Firebase Hosting** con una regla `rewrites` hacia el servicio `gateway`, o
- un **balanceador de carga HTTPS externo** con un certificado administrado por Google. En ese caso, en `gcp/desplegar.sh` cambia `PROXIES_DE_CONFIANZA=1` por `2`, y si quieres que solo se entre por el balanceador, usa `--ingress internal-and-cloud-load-balancing` en el Gateway.

Si otro sitio tiene que llamar a la API, ponlo en `CORS_ORIGENES` (ej. `CORS_ORIGENES=https://mitienda.com ./gcp/desplegar.sh`).

## 10. Registros, alertas y respaldos

- **Registros:** todo lo que escriben los servicios queda en **Cloud Logging** (ahí se ven los errores 500 de Python y los 502 del Gateway).
- **Alertas:** en **Cloud Monitoring** crea una alerta cuando haya muchas respuestas 5xx en el servicio `gateway`, y la alerta de presupuesto de facturación.
- **Respaldos:** Cloud SQL hace uno automático cada día (paso 3). Para poder regresar a cualquier minuto, activa la recuperación a un momento determinado (PITR). Prueba una vez restaurar un respaldo en una instancia nueva para saber que funciona.

## 11. Publicar una versión nueva o regresar a la anterior

- **Versión nueva:** haz commit de tus cambios y vuelve a correr `./gcp/desplegar.sh`.
- **Regresar:** cada despliegue deja una *revisión*. En la consola de Cloud Run (servicio → Revisiones) puedes mandar el 100 % del tráfico a la anterior, o con `gcloud run services update-traffic gateway --region $REGION --to-revisions <revisión>=100`.

## 12. Apagar todo (cuando ya no se use)

```bash
for s in gateway login productos promociones ordenes soporte; do gcloud run services delete $s --region $REGION --quiet; done
gcloud sql instances delete refaccionaria-bd          # ⚠️ borra la base y sus respaldos
```

O borra el proyecto completo desde la consola (IAM y administración → Configuración → Cerrar).

## Lo que queda pendiente

- **Certificado de Cloud SQL:** los microservicios usan `BD_CONFIAR_CERTIFICADO=si`: la conexión va cifrada y por la red privada, pero no se revisa quién firmó el certificado (Cloud SQL usa su propia autoridad). Para revisarlo, habría que meter el certificado de la autoridad de tu instancia (`gcloud sql instances describe … --format 'value(serverCaCert.cert)'`) en la imagen.
- **Límite de login en memoria:** con `--max-instances 1` cuenta bien; si algún día necesitas más copias del Gateway, los contadores tendrían que ir en un lugar compartido (por ejemplo Memorystore).
- **Listas sin paginación:** las órdenes, el inventario y el chat se cargan completos. Con los datos de una tienda pequeña no es problema.
- **Créditos de las fotos:** agrega una página con el autor y la licencia de cada foto de Wikimedia Commons.

# Refaccionaria — Sistema de refacciones para autos

Sistema web para una refaccionaria: catálogo de productos, promociones, órdenes de compra y venta con control de inventario, inicio de sesión y un chat de soporte entre clientes y personal.

Está hecho con **microservicios en Python (FastAPI)**, un **Gateway en Go** que los conecta, una **página web en HTML, CSS y JavaScript** y una base de datos en **SQL Server**.

```
Página web (Frontend)          HTML, CSS y JavaScript
        │  fetch
        ▼
Gateway en Go  :8080           Una sola entrada para todas las APIs
        │  reenvía
        ▼
Microservicios en Python       Login :8000 · Productos :8001 · Promociones :8002
(FastAPI)                      Órdenes :8003 · Soporte :8004
        │  SQL
        ▼
SQL Server                     Base de datos "Refaccionaria"
```

## Qué hace

| Requisito | Dónde está |
|---|---|
| Inicio de sesión y roles | Ventana "Iniciar sesión" en la página → microservicio **Login** (contraseñas con bcrypt). 4 roles: Administrador, Empleado, Almacenista y Cliente |
| Registrar usuario nuevo | "Regístrate" en la ventana de inicio de sesión (queda como Cliente). El Administrador crea usuarios de cualquier rol desde el menú |
| Dashboard con promociones | Página de inicio → `GET /api/dashboard` (solo promociones vigentes) |
| Promociones de la tienda | Microservicio **Promociones**: descuentos por fechas y productos. El Administrador las crea, edita y elimina desde la portada |
| Menú hamburguesa / panel | Botón ☰ en todas las páginas |
| Productos | Página **Productos**: búsqueda, categorías y existencias. El Administrador agrega, edita y elimina productos ahí mismo |
| Detalle del producto | Clic en un producto → **detalle.html?id=3**: precio, promoción, existencia, productos de la misma categoría. El personal registra la venta desde ahí con la orden ya llenada |
| Carrito | El Cliente agrega piezas desde el catálogo o el detalle y hace su pedido en **carrito.html**. Se guarda en el navegador (`localStorage`); para hacer el pedido hay que iniciar sesión |
| Órdenes que entran y salen, con detalle | Página **Órdenes** → microservicio **Órdenes** (Compra = entra, Venta = sale) |
| Almacén (stock) | Página **Almacén**, solo para el Almacenista y el Administrador (aparece en el menú ☰): existencia de cada producto, piezas y valor del inventario, qué hay que surtir (8 o menos) o está agotado, lo que está por entrar y por salir, el historial de movimientos de cada producto y el botón **Surtir** que abre la compra ya llenada |
| Soporte: correo, teléfono y dirección | Página **Contacto** → microservicio **Soporte** |
| Chat de soporte | El Cliente escribe desde **Contacto** y platica en la página **Mensajes**. El Administrador y los Empleados contestan, cierran y reabren; solo el Administrador elimina |

## Estructura del proyecto

```
Login/
├── BD/
│   ├── 01_crear_base.sql        Crea la base y las 11 tablas
│   ├── 02_datos_ejemplo.sql     Catálogo real (5 categorías, 23 piezas) y el contacto (sin usuarios)
│   ├── 03_agregar_horario.sql   Solo para bases creadas antes de la columna Horario
│   ├── 04_agregar_roles.sql     Solo para bases creadas antes de los 4 roles
│   ├── 05_categoria_unicas.sql  Solo para bases creadas antes de los nombres de categoría únicos
│   ├── 06_texto_unicode.sql     Solo para bases creadas antes de que los textos aceptaran emojis
│   ├── 07_numeros_sin_saltos.sql Quita los saltos de 1000 en los números (REF-5021 → REF-011)
│   ├── 08_agregar_imagen.sql    Solo para bases creadas antes de la foto de cada producto
│   ├── 09_borrar_datos_de_prueba.sql ⚠️ Borra órdenes, chats, promociones y productos (una sola vez, antes de abrir; pide confirmación)
│   ├── 10_usuario_app.sql       Crea el usuario de SQL Server de la app (refaccionaria_app)
│   ├── 11_quitar_usuarios_de_prueba.sql Borra empleado, almacen y cliente de una base que los tenga
│   ├── 12_usuarios_de_prueba.sql ⚠️ Solo en tu computadora: admin, empleado, almacen y cliente
│   ├── 13_usuarios_por_microservicio.sql Para producción: un usuario de SQL Server por microservicio, solo con sus permisos
│   └── 14_indices.sql           Solo para bases creadas antes de los índices (búsquedas más rápidas)
├── Backend/                     Microservicios en Python
│   ├── requirements.txt
│   ├── .env.example             Plantilla de la conexión a la base de datos
│   ├── Login/                   :8000
│   ├── Productos/               :8001
│   ├── Promociones/             :8002
│   ├── Ordenes/                 :8003
│   └── Soporte/                 :8004
│       ├── Domain/              Entidades del negocio
│       ├── Application/         Casos de uso e interfaces
│       ├── Infrastructure/      SQL Server, bcrypt
│       ├── API/                 Rutas HTTP (FastAPI)
│       └── tests/               Pruebas de los casos de uso
├── Backend-Go/gateway/          Gateway en Go :8080
├── Frontend/                    Página web
│   ├── index.html               Inicio y dashboard de promociones
│   ├── producto.html            Catálogo
│   ├── detalle.html             Detalle de un producto
│   ├── carrito.html             Carrito del cliente
│   ├── ordenes.html             Órdenes e inventario
│   ├── almacen.html             Stock de la tienda (Almacenista y Administrador)
│   ├── contacto.html            Soporte
│   ├── mensajes.html            Chat de soporte
│   ├── img/productos/           Fotos de las piezas
│   ├── estilo.css
│   └── script.js
├── docs/
│   ├── ARQUITECTURA.md          Capas, dependencias y decisiones
│   ├── API.md                   Todas las rutas de la API
│   ├── DESPLIEGUE_AWS.md        Cómo publicarla en AWS (EC2 + RDS), paso a paso
│   └── DESPLIEGUE_GCP.md        Cómo publicarla en Google Cloud (Cloud Run + Cloud SQL), paso a paso
├── gcp/desplegar.sh             Construye las imágenes y publica los 6 servicios en Cloud Run
├── cloudbuild.yaml              Las 6 imágenes en Cloud Build (linux/amd64)
├── docker-compose.yml           Los 6 servicios en contenedores, en tu Mac
├── aws/                         docker-compose.yml, Caddyfile y cargar_base.sh para el servidor EC2 de AWS
├── pruebas/prueba_api.py        Prueba de punta a punta por el Gateway
├── iniciar.sh                   Arranca todo con un solo comando
└── pruebas.sh                   Corre todas las pruebas automáticas
```

Cada microservicio sigue **arquitectura limpia** con 4 capas. La explicación completa está en [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

## Requisitos

- **SQL Server** 2019 o 2022. En Mac se puede usar Docker:
  ```bash
  docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=TuContraseña123" -p 1433:1433 --name sql_server_container -d mcr.microsoft.com/mssql/server:2022-latest
  ```
- **ODBC Driver 17 for SQL Server**
- **Python 3.12** o más nuevo (el proyecto se probó con Python 3.15). Revisa tu versión con `python3 --version`
- **Go 1.22** o más nuevo (el proyecto se probó con Go 1.27)

## Instalación

**1. Base de datos.** En SQL Server (Azure Data Studio, SSMS o `sqlcmd`) ejecuta en este orden:

1. `BD/01_crear_base.sql`
2. `BD/02_datos_ejemplo.sql`
3. `BD/12_usuarios_de_prueba.sql` (los usuarios de prueba de abajo; **solo en tu computadora**, nunca en el servidor)

Los tres se pueden correr varias veces: solo crean lo que falta y no duplican datos. Si tu base ya existía, vuelve a correr `01_crear_base.sql` para que se creen las tablas nuevas, como las del chat. `BD/03_agregar_horario.sql`, `BD/04_agregar_roles.sql`, `BD/05_categoria_unicas.sql` y `BD/06_texto_unicode.sql` solo hacen falta si tu base se creó antes de que existieran la columna `Horario`, los roles, los nombres de categoría únicos o los textos con emojis (antes un 😀 en el chat se guardaba como `??`).

`BD/07_numeros_sin_saltos.sql` evita que SQL Server se brinque 1000 números cada vez que se reinicia (por eso un producto nuevo podía salir como `REF-5021`), y regresa cada contador al número más alto que existe. No cambia datos. Córrelo si tu base ya existía, o si ves códigos con saltos grandes. Las tablas que nunca han tenido filas no las toca, así que en una base nueva todo sigue empezando en 1. Es normal que falten números sueltos cuando algo se borra: SQL Server no reutiliza los números borrados.

`BD/08_agregar_imagen.sql` agrega la columna `Imagen` (la foto de cada producto) a una base que ya existía. `BD/14_indices.sql` agrega los índices que ahora crea `01_crear_base.sql` (para que las órdenes, el inventario y el chat se busquen rápido aunque haya muchos datos); córrelo si tu base ya existía. `BD/09_borrar_datos_de_prueba.sql` **borra para siempre** las órdenes, movimientos, promociones, chats, productos y categorías (no los usuarios ni el contacto) y reinicia los números; úsalo una sola vez antes de abrir la tienda y después vuelve a correr `02_datos_ejemplo.sql`. Para que no se corra por accidente, no borra nada hasta que cambies `N'NO'` por `N'SI, BORRAR TODO'` en la línea de `@confirmo` (cierra el archivo **sin guardar**).

`BD/10_usuario_app.sql` crea el usuario de SQL Server `refaccionaria_app`, con el que entran los 5 microservicios: solo puede leer y escribir datos de `Refaccionaria` (no borrar tablas ni tocar otras bases), así que la app ya no usa `sa`. Antes de ejecutarlo cambia `PEGA-AQUI-LA-CONTRASENA` por una contraseña nueva y, al terminar, cierra el archivo **sin guardar** (si no la cambias, no hace nada). `BD/11_quitar_usuarios_de_prueba.sql` y `BD/13_usuarios_por_microservicio.sql` son **para producción** (ver [Antes de publicar en Internet](#antes-de-publicar-en-internet)).

**Fotos de los productos.** Están en `Frontend/img/productos`. Si agregas una foto, ponla en esa carpeta y escribe su ruta (`img/productos/archivo.jpg`) en el campo **Foto** al editar el producto.

**2. Entorno de Python.** Desde la carpeta `Login`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r Backend/requirements.txt
```

**3. Conexión a la base de datos.** Copia la plantilla a cada microservicio:

```bash
for s in Login Productos Promociones Ordenes Soporte; do cp Backend/.env.example Backend/$s/.env; done
```

Después abre cada `.env` y llena:

- `BD_PASSWORD`: la contraseña que le pusiste a `refaccionaria_app` en `BD/10_usuario_app.sql`.
- `TOKEN_SECRETO`: la clave con la que Login firma los tokens de sesión y los demás servicios los revisan. **Debe ser la misma en los 5 `.env`**. Genera una con:
  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```
- `BD_CONFIAR_CERTIFICADO`: déjalo en `si` en tu computadora. La conexión a SQL Server **siempre va cifrada**; con `si` se acepta el certificado que SQL Server (en Docker) se hizo él mismo. Con `ENTORNO=produccion` se usa `no` si no lo pones: se revisa que el certificado sea válido, para que nadie en medio se haga pasar por la base de datos.
- `BD_USER` ya no tiene valor por omisión: si falta, el microservicio avisa en vez de intentar entrar como `sa`.

## Cómo correrlo

```bash
./iniciar.sh
```

Arranca los 5 microservicios y el Gateway. Para apagarlos todos, presiona **Ctrl+C**. Después abre http://127.0.0.1:8080/ en el navegador.

Antes de arrancar, el script:

- Avisa si SQL Server no responde (por ejemplo, si Docker está apagado).
- Revisa los puertos. Si quedó prendida una copia vieja de este proyecto (por ejemplo, un microservicio trabado de una vez anterior), la cierra sola (🔄). Si el puerto lo usa **otro programa**, dice cuál es y no arranca nada.
- Al final muestra ✅ o ❌ por cada servicio, según si de verdad contesta.

| Dirección | Qué hay |
|---|---|
| http://127.0.0.1:8080/ | La página de la Refaccionaria (la entrega el Gateway) |
| http://127.0.0.1:8080/gateway | Gateway: lista de todas las APIs y si cada microservicio está encendido |
| http://127.0.0.1:8080/docs | Documentación interactiva (Swagger) de las 5 APIs |
| http://127.0.0.1:8000/docs … 8004/docs | Documentación de cada microservicio por separado |

**Usuarios de prueba (solo para tu computadora):**

> ⚠️ Estas contraseñas son públicas porque están en este README. Sirven para desarrollar, para la demo y para `pruebas.sh`, pero **no deben existir en la tienda publicada**: ver [Antes de publicar en Internet](#antes-de-publicar-en-internet).

| Usuario | Contraseña | Rol | Qué puede hacer |
|---|---|---|---|
| `admin` | `Admin123` | Administrador | Todo: ventas, compras, cancelar, registrar usuarios de cualquier rol, administrar productos, categorías y promociones, y contestar o eliminar conversaciones del chat |
| `empleado` | `Empleado123` | Empleado | Hace ventas y las avanza. Contesta y cierra las conversaciones del chat. No registra compras ni cancela |
| `almacen` | `Almacen123` | Almacenista | Registra compras (mercancía que entra) y las avanza. Ve el inventario en la página **Almacén**. No atiende el chat |
| `cliente` | `Cliente123` | Cliente | Hace pedidos y solo ve los suyos. Escribe al chat de soporte. No ve el inventario |

**Sesión con token.** Al iniciar sesión, el microservicio de Login regresa un token firmado con `TOKEN_SECRETO` que dura 8 horas. La página lo manda en cada petición (`Authorization: Bearer <token>`) y cada microservicio saca de ahí quién eres; ya no se le cree al `id_login` que mande la página. Si el token es falso, está alterado o venció, la API responde 401 y la página cierra la sesión.

## Antes de publicar en Internet

En la base de datos del servidor (no en tu computadora):

1. Corre `BD/01_crear_base.sql` y `BD/02_datos_ejemplo.sql` (crean las tablas, el catálogo y el contacto). **No** corras `BD/12_usuarios_de_prueba.sql`: sus contraseñas están en este README.
2. Corre `BD/13_usuarios_por_microservicio.sql` con **5 contraseñas nuevas y distintas** (no la de tu computadora). Crea un usuario de SQL Server para cada microservicio (`refaccionaria_login`, `refaccionaria_productos`, `refaccionaria_promociones`, `refaccionaria_ordenes` y `refaccionaria_soporte`), cada uno solo con lo que necesita: por ejemplo, solo Login puede leer la columna `Password`, Órdenes solo puede cambiar el `Stock` de un producto (no su precio) y nadie puede borrar órdenes. Pon a cada microservicio **su** usuario y contraseña (`BD_USER` y `BD_PASSWORD`), y a los 5 el mismo `TOKEN_SECRETO` **nuevo**. En el servidor no hace falta `BD/10_usuario_app.sql`: ese usuario puede leer y cambiar todas las tablas.
3. Si esa base ya tenía los usuarios de prueba (por ejemplo, porque es una copia de la de tu computadora), corre `BD/11_quitar_usuarios_de_prueba.sql` y cámbiale la contraseña al admin con `cambiar_contrasena.py admin`.
4. Crea tu Administrador con un usuario, un correo y una contraseña de 12 caracteres o más (no se muestra en pantalla):
   ```bash
   cd Backend/Login && ../../.venv/bin/python crear_administrador.py
   ```
5. Crea las cuentas reales del personal desde la página, entrando como admin (**Registrar usuario**).
6. Arranca el Gateway **y los 5 microservicios** con `ENTORNO=produccion`. El Gateway así no publica `/gateway`, `/docs` ni `/openapi/...`, que muestran direcciones y puertos internos (la página web, `/`, sí se publica), cierra CORS y baja el límite de registros a 10 por hora. Los microservicios así revisan el certificado de SQL Server (ver `BD_CONFIAR_CERTIFICADO`).
7. Las fotos de los productos son de Wikimedia Commons: agrega una página de créditos con el autor y la licencia de cada una (muchas licencias, como CC BY-SA, lo piden).

**Protecciones del Gateway** (`Backend-Go/gateway`):

- **Intentos de login:** después de 5 contraseñas equivocadas con el mismo usuario desde la misma IP (o 20 con cualquier usuario), responde **429** durante 15 minutos. Entrar bien borra los fallos de ese usuario. Los contadores viven en memoria: reiniciar el Gateway los borra, y si hay varias copias del Gateway cada una cuenta por su lado.
- **IP real detrás de Google Cloud:** ahí todas las conexiones llegan desde Google y la IP del visitante viene en el encabezado `X-Forwarded-For`. Con `PROXIES_DE_CONFIANZA` se le dice al Gateway cuántas direcciones agrega Google al final de ese encabezado: `1` en Cloud Run directo, `2` con un balanceador de carga delante. Sin la variable (`0`, en tu computadora y en Docker) se usa la IP de la conexión y no se le cree a `X-Forwarded-For`, porque cualquiera lo puede escribir. Con IPv6 se cuenta por bloque `/64`.
- **Mismo tiempo exista o no el usuario:** si el usuario no existe, Login hace el mismo trabajo de bcrypt que al revisar una contraseña (~170 ms), así no se puede saber por el tiempo qué usuarios existen.
- **Cuentas nuevas:** con `ENTORNO=produccion`, máximo 10 intentos de registro por IP en una hora (**429**), para frenar a quien crea cuentas en masa o prueba qué correos ya están registrados. En tu computadora el límite es 100, para poder correr `pruebas.sh` varias veces.
- **Encabezados de seguridad:** la página lleva `Content-Security-Policy` (solo se ejecuta `script.js` de la misma tienda; si alguien lograra meter un `<script>` en un nombre o en el chat, el navegador no lo corre), y todas las respuestas llevan `X-Content-Type-Options`, `X-Frame-Options` (nadie mete la tienda dentro de otra página) y `Referrer-Policy`. Detrás de Google con HTTPS también `Strict-Transport-Security`. Las respuestas de la API no se guardan en caché ni dicen qué servidor hay detrás.
- **CORS:** como la página y la API están en la misma dirección, no hace falta. En tu computadora se deja abierto (`*`) para poder abrir `index.html` con doble clic; con `ENTORNO=produccion` ningún otro sitio puede llamar a la API desde el navegador, salvo los que pongas en `CORS_ORIGENES` (ej. `CORS_ORIGENES=https://mitienda.com`).
- **Tamaño:** rechaza peticiones de más de 1 MB (**413**).
- **Tiempos de espera:** corta las conexiones que no terminan de mandar su petición y deja de esperar a un microservicio trabado después de 20 segundos (**502**).

## Con Docker (opcional)

Para probar en tu Mac lo mismo que se va a subir a Google Cloud: el Gateway y los 5 microservicios, cada uno en su contenedor. SQL Server sigue en el suyo (`sql_server_container`).

```bash
docker compose up --build
```

Apaga antes `./iniciar.sh`, porque los dos usan el puerto 8080. Para apagar los contenedores, **Ctrl+C**; para borrarlos, `docker compose down`.

| Archivo | Qué hace |
|---|---|
| `Backend/Dockerfile` | Una sola receta para los 5 microservicios de Python (`--build-arg SERVICIO=Login`, `Productos`…). Instala el conector de SQL Server de Microsoft (ODBC Driver 18, acepta su licencia) y pone la hora de México (`TZ=America/Mexico_City`) |
| `Backend-Go/gateway/Dockerfile` | Compila el Gateway y lo deja, junto con la página web (`Frontend/`), en una imagen mínima de ~19 MB, sin shell y sin permisos de administrador. Se construye desde la carpeta principal del proyecto |
| `docker-compose.yml` | Levanta los 6 contenedores. Solo el Gateway se abre a tu Mac (en `127.0.0.1:8080`) |
| `.dockerignore` | Evita que los `.env`, las pruebas y `__pycache__` entren a las imágenes |

**Para publicarla en Internet** sigue [docs/DESPLIEGUE_AWS.md](docs/DESPLIEGUE_AWS.md): un servidor EC2 con `aws/docker-compose.yml` (Caddy pone el HTTPS y es lo único que se ve desde Internet) y Amazon RDS for SQL Server, sin acceso público y con el certificado revisado.

También está la versión para Google Cloud, [docs/DESPLIEGUE_GCP.md](docs/DESPLIEGUE_GCP.md): Google Cloud Run para el Gateway y los microservicios (estos últimos privados: solo el Gateway llega a ellos, con `IDENTIDAD_GOOGLE=si`), Cloud SQL for SQL Server con IP privada y las contraseñas en Secret Manager. `docker compose` no se puede subir tal cual a Cloud Run: cada servicio se publica por separado con `gcp/desplegar.sh`.

Las imágenes **no llevan contraseñas**: `docker compose` lee los `.env` de cada microservicio al arrancar. Dentro de Docker, el Gateway encuentra a los microservicios con las variables `URL_LOGIN`, `URL_PRODUCTOS`, `URL_PROMOCIONES`, `URL_ORDENES` y `URL_SOPORTE`, y escucha en `HOST=0.0.0.0`; sin esas variables usa las direcciones de `iniciar.sh`.

## Pruebas automáticas

```bash
./pruebas.sh
```

| Qué prueba | Cuántas | ¿Necesita la base de datos? |
|---|---|---|
| **Casos de uso** de los 5 microservicios (`Backend/*/tests/`): login, registro, roles y permisos, validaciones, descuentos, estados de las órdenes, stock que sube y baja, venta sin stock, chat de soporte, editar productos y promociones, precio con promoción en las ventas, hora de las órdenes, cambiar contraseña, crear el Administrador, promociones vencidas, quién puede cambiar el precio | 103 | No. Usan repositorios falsos en memoria, gracias a la arquitectura limpia |
| **Gateway en Go** (`Backend-Go/gateway/*_test.go`): la IP que usa el límite de login (con y sin proxy, IP fingida, IPv6), que un atacante no bloquee a los demás, encabezados de seguridad, CSP, CORS y límite de registros, el proxy (Host y token de identidad de Google) | 18 | No |
| **APIs de punta a punta** (`pruebas/prueba_api.py`): página → Gateway → Python → SQL Server, con el token de cada usuario de prueba, incluidos tokens falsos o alterados | 38 | Sí. Corre antes `./iniciar.sh`. Todo lo que crea lo borra al final |

También se pueden correr por separado:

```bash
cd Backend/Ordenes && ../../.venv/bin/python -m unittest discover -s tests -t . -v
cd Backend-Go/gateway && go test -v ./...
.venv/bin/python pruebas/prueba_api.py -v
```

## Cómo probar el flujo de órdenes

1. Inicia sesión con `admin` / `Admin123`.
2. Ve a **Órdenes** → **+ Nueva orden**.
3. Elige **Venta**, agrega productos y guarda. La orden queda **Pendiente**.
4. En el detalle, presiona **Pasar a Completada**. El stock baja y aparece una **Salida** en "Movimientos de inventario".
5. Haz lo mismo con una **Compra**: al completarla el stock sube y aparece una **Entrada**.

Si una venta pide más piezas de las que hay, no se puede completar y la página explica por qué.

## Cómo probar el chat de soporte

1. Inicia sesión con `cliente` / `Cliente123` → **Contacto** → elige un asunto, escribe y presiona **Enviar mensaje**. Se abre la conversación en **Mensajes**.
2. En otra ventana (por ejemplo, una ventana privada), inicia sesión con `empleado` o `admin` → **Mensajes**. La conversación aparece como **Sin contestar**. Contéstala.
3. En la ventana del cliente la respuesta aparece sola: la página busca mensajes nuevos cada 5 segundos.
4. El personal puede **Cerrar** la conversación; ya cerrada, nadie puede escribir. Solo el Administrador la puede **Eliminar**.

## Límites conocidos

- **El token no se puede revocar.** Si cambias la contraseña de alguien, las sesiones que ya tenía abiertas siguen activas hasta que venza su token (8 horas). Para cerrar todas las sesiones de golpe, cambia `TOKEN_SECRETO` en los 5 `.env` y reinicia.
- **El chat no es en tiempo real.** La página pregunta cada 5 segundos si hay mensajes nuevos. Para que lleguen al instante se usaría WebSocket.

## Notas

- Los archivos `.env` tienen la contraseña de la base de datos y **no se entregan** (ver `.gitignore`).
- El stock solo cambia cuando una orden pasa a **Completada**. Cancelarla no mueve inventario. Por eso, al editar un producto la existencia no se cambia a mano: solo se escribe al crearlo.
- Si SQL Server corre en Docker, su reloj está en hora UTC (6 horas adelante de México), y así se ven las horas de las órdenes.
- Para entregar el proyecto sin `.env` ni `.venv`:
  ```bash
  cd .. && zip -r Refaccionaria-entrega.zip Login -x "Login/.venv/*" "*/.env" "*/__pycache__/*" "*.DS_Store" "Login/.claude/*"
  ```

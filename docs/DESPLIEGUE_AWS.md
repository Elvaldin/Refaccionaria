# Publicar la Refaccionaria en AWS

Esta guía sube la tienda a Amazon Web Services (AWS) con **un servidor EC2** que corre los contenedores (`aws/docker-compose.yml`) y **Amazon RDS for SQL Server** para la base de datos.

> ⚠️ **Costo.** RDS y EC2 se cobran por cada hora que están prendidos, aunque nadie entre a la tienda. Las cuentas nuevas traen créditos (Free Tier), pero **revisa la [calculadora de precios](https://calculator.aws/)** y crea una **alerta de presupuesto** antes de empezar (paso 1). Si solo es para presentarlo en clase, borra todo al terminar (paso 11).

## Cómo queda

```
Visitante ──HTTPS──► EC2 (un servidor Ubuntu con Docker)
                     │
                     ├─ Caddy  (puertos 80 y 443: certificado HTTPS automático)
                     │    └─► Gateway (Go): la página web y /api/...
                     │          └─► Login, Productos, Promociones, Ordenes, Soporte
                     │               (sin puertos abiertos: solo el Gateway llega a ellos)
                     │
                     └──────────────────────────► RDS for SQL Server Express
                                                    (sin acceso desde Internet;
                                                     solo el servidor EC2 entra)
```

- **Solo Caddy** se ve desde Internet. El Gateway y los microservicios están en una red interna de Docker.
- **La base de datos** solo acepta conexiones del servidor EC2 (grupo de seguridad), siempre cifradas, y los microservicios **revisan su certificado** (la imagen trae los certificados de Amazon RDS).
- **Cada microservicio** entra a SQL Server con **su propio usuario** (`BD/13_usuarios_por_microservicio.sql`), con permiso solo para lo que necesita.
- Las contraseñas viven en los `.env` **del servidor**: nunca en GitHub ni en las imágenes.

## 1. Antes de empezar

1. **Región.** Arriba a la derecha de la consola elige **US East (N. Virginia) `us-east-1`**, y usa la misma en todos los pasos.
2. **Alerta de presupuesto.** Busca **Budgets** → **Create budget** → *Use a template* → **Monthly cost budget** (por ejemplo, 10 USD) con tu correo. AWS te avisa si el gasto se acerca a ese monto.

## 2. Grupos de seguridad (el "firewall" de AWS)

Busca **EC2** → **Security Groups** → **Create security group**. Crea dos:

| Nombre | Reglas de entrada (Inbound) |
|---|---|
| `refaccionaria-web` | **HTTP** (80) desde `0.0.0.0/0` · **HTTPS** (443) desde `0.0.0.0/0` · **SSH** (22) desde **My IP** |
| `refaccionaria-bd` | **MSSQL** (1433) desde el grupo **`refaccionaria-web`** (en *Source* escribe `sg-` y elígelo) |

Las reglas de salida (Outbound) se quedan como vienen.

## 3. La base de datos (RDS)

Busca **RDS** → **Create database**:

| Opción | Valor |
|---|---|
| Creation method | **Full configuration** |
| Engine | **Microsoft SQL Server** · Edition **SQL Server Express** |
| Templates | **Free tier** (si aparece) |
| DB instance identifier | `refaccionaria-bd` |
| Master username | por ejemplo `admin_rds` (no uses `sa`) |
| Credentials | **Self managed** · escribe una contraseña larga y guárdala en tu gestor de contraseñas |
| Instance class | **db.t3.micro** |
| Storage | 20 GiB, **gp3**; desactiva *Storage autoscaling* |
| Public access | **No** |
| VPC security group | **Choose existing** → `refaccionaria-bd` (quita `default`) |
| Backup | Retención **7 días** |
| Deletion protection | Activado |

Cuando diga **Available** (tarda unos 15 minutos), entra a la base y copia el **Endpoint** (algo como `refaccionaria-bd.xxxxx.us-east-1.rds.amazonaws.com`).

## 4. Cargar la base de datos

Los scripts usan `GO`, así que hay que correrlos con Azure Data Studio, VS Code (extensión *SQL Server (mssql)*) o SSMS. Como la base no tiene acceso desde Internet, ábrelo **solo unos minutos y solo para tu IP**:

1. En RDS → `refaccionaria-bd` → **Modify** → *Connectivity* → **Public access: Publicly accessible** → *Apply immediately*.
2. En el grupo `refaccionaria-bd` agrega otra regla: **MSSQL** (1433) desde **My IP**.
3. Conéctate: servidor `<endpoint>,1433`, usuario `admin_rds` y su contraseña, **Encrypt** activado.

Corre, en este orden:

1. `BD/01_crear_base.sql` (tablas e índices)
2. `BD/02_datos_ejemplo.sql` (catálogo y contacto: **cambia antes los precios y existencias por los tuyos**)
3. `BD/13_usuarios_por_microservicio.sql` con **5 contraseñas nuevas y distintas** (anótalas: van en el paso 7). Cierra el archivo **sin guardar**.

**No** corras `BD/10_usuario_app.sql` (un usuario con permiso en todo) ni `BD/12_usuarios_de_prueba.sql` (contraseñas públicas).

**El primer Administrador**, en tu Mac:

```bash
cd Backend/Login && ../../.venv/bin/python crear_administrador.py --sql
```

Escribe el usuario, el correo y una contraseña de 12 caracteres o más (no se ve al escribirla). Copia el `INSERT` que aparece y córrelo en la misma conexión del paso 3. Después, ese Administrador crea las demás cuentas del personal desde la página.

**Al terminar, ciérrala otra vez:** quita la regla de **My IP** del grupo `refaccionaria-bd` y regresa **Public access** a **Not publicly accessible**.

## 5. El servidor (EC2)

Busca **EC2** → **Launch instance**:

| Opción | Valor |
|---|---|
| Name | `refaccionaria` |
| AMI | **Ubuntu Server 24.04 LTS**, arquitectura **64-bit (Arm)** |
| Instance type | **t4g.small** (2 GB de memoria: 1 GB no alcanza para construir las imágenes) |
| Key pair | **Create new key pair** → `refaccionaria`, tipo RSA, formato `.pem`. Se descarga solo: guárdalo, no se puede volver a bajar |
| Network settings | **Select existing security group** → `refaccionaria-web` |
| Storage | 20 GiB **gp3** |

> Arm (`t4g`) es la misma arquitectura que tu Mac con Apple Silicon: las imágenes son las mismas que probaste en tu computadora, y cuesta menos que una Intel del mismo tamaño.

**Una dirección fija.** EC2 → **Elastic IPs** → **Allocate Elastic IP address** → selecciónala → **Actions → Associate** → la instancia `refaccionaria`. Anótala, por ejemplo `3.90.12.34`.

**Tu dominio.** Si no tienes uno, usa [sslip.io](https://sslip.io): con la IP `3.90.12.34` tu dirección es **`3-90-12-34.sslip.io`** (los puntos se cambian por guiones). Si compras un dominio, crea un registro **A** que apunte a la Elastic IP y usa ese.

## 6. Preparar el servidor

Desde tu Mac (cambia la IP por la tuya):

```bash
chmod 400 ~/Downloads/refaccionaria.pem
ssh -i ~/Downloads/refaccionaria.pem ubuntu@3.90.12.34
```

Ya dentro del servidor, instala Docker y Git, y agrega 2 GB de memoria de intercambio (swap) por si acaso:

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker ubuntu
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
exit
```

Vuelve a entrar con el mismo `ssh` (para que tome el permiso de Docker) y descarga el proyecto:

```bash
git clone https://github.com/Elvaldin/Refaccionaria.git
cd Refaccionaria
```

## 7. Las contraseñas (`.env` del servidor)

Genera **un `TOKEN_SECRETO` nuevo** (no uses el de tu Mac):

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Crea el `.env` de cada microservicio con `nano` (por ejemplo `nano Backend/Login/.env`; guarda con **Ctrl+O**, **Enter** y sal con **Ctrl+X**). Los 5 llevan esto, cambiando **solo** `BD_USER` y `BD_PASSWORD`:

```
BD_SERVER=<endpoint de RDS>,1433
BD_NAME=Refaccionaria
BD_USER=refaccionaria_login
BD_PASSWORD=<la contraseña de refaccionaria_login del paso 4>
TOKEN_SECRETO=<el mismo en los 5>
BD_CONFIAR_CERTIFICADO=no
```

| Archivo | `BD_USER` |
|---|---|
| `Backend/Login/.env` | `refaccionaria_login` |
| `Backend/Productos/.env` | `refaccionaria_productos` |
| `Backend/Promociones/.env` | `refaccionaria_promociones` |
| `Backend/Ordenes/.env` | `refaccionaria_ordenes` |
| `Backend/Soporte/.env` | `refaccionaria_soporte` |

Y el dominio, en `aws/.env`:

```bash
echo "DOMINIO=3-90-12-34.sslip.io" > aws/.env
chmod 600 Backend/*/.env aws/.env
```

`BD_CONFIAR_CERTIFICADO=no` hace que cada microservicio **revise** que la base sea de verdad tu RDS. `ENTORNO=produccion` y el conector (`ODBC Driver 18`) ya los pone `aws/docker-compose.yml`.

## 8. Arrancar

```bash
docker compose -f aws/docker-compose.yml up -d --build
```

La primera vez tarda unos minutos (construye las 6 imágenes). Caddy saca el certificado HTTPS solo en cuanto alguien entra por primera vez.

## 9. Comprobar que todo funciona

- Abre `https://3-90-12-34.sslip.io`: debe salir la tienda con el candado 🔒.
- `http://...` (sin la "s") debe mandarte solo a `https://`.
- Entra con el Administrador del paso 4 y revisa **Órdenes**, **Almacén** y **Mensajes**.
- `https://.../docs` debe dar **404** (en producción no se publica).
- Si algo falla, mira los registros:

```bash
docker compose -f aws/docker-compose.yml ps
docker compose -f aws/docker-compose.yml logs --tail 50 gateway
docker compose -f aws/docker-compose.yml logs --tail 50 login
```

Un error `certificate verify failed` en los microservicios quiere decir que no pudieron revisar el certificado de RDS: confirma que `BD_SERVER` es el **endpoint** (no una IP). Solo como último recurso, `BD_CONFIAR_CERTIFICADO=si` deja la conexión cifrada pero sin revisar el certificado.

## 10. Publicar una versión nueva

En tu Mac, guarda y sube los cambios a GitHub (`git push`). En el servidor:

```bash
cd ~/Refaccionaria && git pull && docker compose -f aws/docker-compose.yml up -d --build
```

Para regresar a la versión anterior: `git log --oneline`, luego `git checkout <commit>` y el mismo `up -d --build`.

**Respaldos:** RDS guarda uno automático cada día durante 7 días (paso 3). Prueba una vez **Restore to point in time** en una base nueva para saber que funciona (y bórrala después).

## 11. Apagar o borrar todo

| Qué | Cómo | ¿Sigue cobrando? |
|---|---|---|
| Pausar el servidor | EC2 → instancia → **Stop** | El disco y la Elastic IP sí (poco) |
| Pausar la base | RDS → **Actions → Stop temporarily** | El disco sí. **AWS la vuelve a prender sola a los 7 días** |
| Borrar todo | EC2 → **Terminate**; **Release** la Elastic IP; RDS → quita *Deletion protection* → **Delete** | No |

## Lo que queda pendiente

- **GitHub Pages:** la página publicada en `github.io` no puede usar la API (llama a `/api` de github.io). En AWS no hace falta, porque el Gateway entrega la página; si no la usas, desactívala en GitHub → *Settings* → *Pages*.
- **Una sola copia del Gateway:** el límite de intentos de login cuenta en memoria. Con un solo servidor está bien; con varios, cada uno contaría por su lado.

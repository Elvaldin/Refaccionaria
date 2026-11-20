# Publicar la Refaccionaria en AWS

Esta guía sube la tienda a Amazon Web Services (AWS) con **un servidor EC2** que corre los contenedores (`aws/docker-compose.yml`) y **Amazon RDS for SQL Server** para la base de datos. Es la forma en que quedó publicada en `https://3-148-60-126.sslip.io`.

> ⚠️ **Costo.** RDS y EC2 se cobran por cada hora que están prendidos, aunque nadie entre a la tienda: juntos, unos **30 a 45 USD al mes**. En el **plan Free** de AWS eso sale de los créditos (100 USD al abrir la cuenta) y no se cobra a la tarjeta, pero el plan **termina a los 6 meses o al acabarse los créditos, y AWS cierra la cuenta**. Crea una alerta de presupuesto (paso 1) y apaga o borra todo cuando no se use (paso 11).

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
- **La base de datos nunca se abre a Internet**: hasta para cargarla se entra desde el servidor (paso 7). La conexión va cifrada y los microservicios **revisan su certificado** (la imagen trae los certificados de Amazon RDS).
- **Cada microservicio** entra a SQL Server con **su propio usuario** (`BD/13_usuarios_por_microservicio.sql`), con permiso solo para lo que necesita.
- Las contraseñas viven en los `.env` **del servidor**: nunca en GitHub ni en las imágenes.

## Lo que impone el plan Free de AWS

| Límite | Qué hacer |
|---|---|
| Solo deja usar **una región**: la que AWS le asignó a tu cuenta (en esta cuenta, **US East (Ohio) `us-east-2`**). Si eliges otra, la consola avisa *"La región … no está disponible"* | Usa la región que diga ese aviso en **todos** los pasos |
| RDS guarda respaldos automáticos de **1 día como máximo** (con 7 da error: *"exceeds the maximum available to free tier customers"*) | Pon **1 día**. Haz respaldos manuales (*Snapshots*) antes de cambios grandes |
| Solo tamaños marcados **"Apto para la capa gratuita"** | `db.t3.micro` (RDS) y `t4g.small` (EC2) sí lo están |

## 1. Antes de empezar

1. **Región.** Arriba a la derecha de la consola elige la región de tu cuenta (paso anterior) y usa la misma en todos los pasos.
2. **Alerta de presupuesto.** Busca **Budgets** → **Crear presupuesto** → *Uso de una plantilla* → **Presupuesto de costos mensual** (por ejemplo, 10 USD) con tu correo. Cuenta el gasto **antes** de descontar créditos, así que avisa aunque estés en el plan Free.

## 2. Grupos de seguridad (el "firewall" de AWS)

Busca **EC2** → **Grupos de seguridad** → **Crear grupo de seguridad**. Crea dos:

| Nombre | Reglas de entrada |
|---|---|
| `refaccionaria-web` | **HTTP** (80) desde `0.0.0.0/0` (*Anywhere-IPv4*) · **HTTPS** (443) desde `0.0.0.0/0` · **SSH** (22) desde **Mi IP** |
| `refaccionaria-bd` | **MSSQL** (1433) desde el grupo **`refaccionaria-web`** (en *Origen* escribe `refaccionaria-web` y elígelo) |

Las reglas de salida se quedan como vienen. Si tu IP de casa cambia y ya no puedes entrar por SSH, edita la regla SSH de `refaccionaria-web` y vuelve a elegir **Mi IP**.

## 3. La base de datos (RDS)

Busca **RDS** → **Crear base de datos**:

| Opción | Valor |
|---|---|
| Tipo de motor | **Microsoft SQL Server** |
| Método | **Configuración completa** |
| Plantilla | **Capa gratuita** |
| Edición | **SQL Server Express** |
| Identificador | `refaccionaria-bd` |
| Nombre de usuario maestro | `adminrds` (solo letras y números: el guion bajo no se acepta) |
| Administración de credenciales | **Administrado en AWS Secrets Manager**: AWS inventa la contraseña y la guarda; nadie la escribe (~0.40 USD al mes) |
| Clase de instancia | **db.t3.micro** |
| Almacenamiento | 20 GiB; en *Configuración de almacenamiento adicional* **quita** *Habilitar escalado automático* (si no, puede crecer hasta 1000 GiB) |
| Acceso público | **No** |
| Grupo de seguridad | **Elegir existente** → `refaccionaria-bd` (quita `default`) |
| *Configuración adicional* → Zona horaria | **Central Standard Time (Mexico)** (no se puede cambiar después) |
| Retención de copias de seguridad | **1 día** (el máximo del plan Free) |
| Actualización automática de versiones secundarias | Activada (parches de seguridad) |
| Protección contra la eliminación | Activada |

Tarda unos 15 minutos. Después, en **Conectividad y seguridad**, copia el **punto de conexión** (algo como `refaccionaria-bd.xxxx.us-east-2.rds.amazonaws.com`).

## 4. El servidor (EC2)

Busca **EC2** → **Lanzar una instancia**:

| Opción | Valor |
|---|---|
| Nombre | `refaccionaria` |
| Imagen | **Ubuntu** (Server LTS; se probó con 26.04) · Arquitectura **64 bits (Arm)** |
| Tipo de instancia | **t4g.small** (2 GB: 1 GB no alcanza para construir las imágenes) |
| Par de claves | **Crear un nuevo par de claves** → `refaccionaria`, RSA, `.pem`. Se descarga solo: **guárdalo**, no se puede volver a bajar |
| Configuraciones de red → *Editar* | **Seleccionar un grupo de seguridad existente** → `refaccionaria-web` |
| Almacenamiento | 20 GiB **gp3** |

> Arm (`t4g`) es la misma arquitectura que una Mac con Apple Silicon: las imágenes son las mismas que pruebas en tu computadora, y cuesta menos que una Intel del mismo tamaño.

**Una dirección fija.** EC2 → **Direcciones IP elásticas** → **Asignar** → **Asociar esta dirección IP elástica** → la instancia `refaccionaria`. Por ejemplo `3.148.60.126`.

**Tu dominio.** Sin dominio propio, usa [sslip.io](https://sslip.io): con la IP `3.148.60.126` la dirección es **`3-148-60-126.sslip.io`** (puntos cambiados por guiones). Con un dominio propio, crea un registro **A** a la IP elástica.

## 5. Entrar al servidor

Desde la app **Terminal de tu Mac** (cambia la IP por la tuya):

```bash
mkdir -p ~/.ssh && cp ~/Downloads/refaccionaria.pem ~/.ssh/ && chmod 400 ~/.ssh/refaccionaria.pem
ssh -i ~/.ssh/refaccionaria.pem ubuntu@3.148.60.126
```

## 6. Preparar el servidor

Ya dentro: Docker, Git y 2 GB de memoria de intercambio (swap) por si acaso.

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
```

## 7. Cargar la base y crear los `.env` (sin abrir RDS a Internet)

`aws/cargar_base.sh` lo hace todo desde el servidor, que llega a RDS por la red privada de AWS:

- corre `BD/01_crear_base.sql`, `BD/02_datos_ejemplo.sql` y `BD/13_usuarios_por_microservicio.sql`;
- inventa las **5 contraseñas de los microservicios** y el **`TOKEN_SECRETO`** y las escribe directo en los `.env` del servidor (nadie las ve);
- crea `aws/.env` con tu dominio.

Antes, en **Secrets Manager** (RDS → `refaccionaria-bd` → *Conectividad y seguridad* → *Ver en Secrets Manager*) → **Recuperar el valor del secreto** → pestaña **Texto sin formato** → copia **todo** el texto (el script toma solo la contraseña).

Luego, **desde la app Terminal de tu Mac** (no desde el panel Terminal de Claude, que no pega texto en una contraseña oculta):

```bash
ssh -t -i ~/.ssh/refaccionaria.pem ubuntu@3.148.60.126 'cd ~/Refaccionaria && ./aws/cargar_base.sh <endpoint-de-RDS> 3-148-60-126.sslip.io'
```

Usuario: **Enter** (`adminrds`). Contraseña: **Cmd + V** y **Enter** (no se ve). Debe decir *"Contraseña recibida: N caracteres"*, cargar los 3 scripts y terminar con **✅**. Si dice *Login failed*, se pegó otra cosa: vuelve a copiar el secreto.

**No** corras `BD/10_usuario_app.sql` (un usuario con permiso en todo) ni `BD/12_usuarios_de_prueba.sql` (contraseñas públicas).

## 8. Arrancar

En el servidor:

```bash
cd ~/Refaccionaria && docker compose -f aws/docker-compose.yml up -d --build
```

La primera vez tarda unos minutos (construye las 6 imágenes). Caddy saca el certificado HTTPS en cuanto alguien entra por primera vez.

## 9. El primer Administrador

Desde la app **Terminal de tu Mac**:

```bash
ssh -t -i ~/.ssh/refaccionaria.pem ubuntu@3.148.60.126 'cd ~/Refaccionaria && docker compose -f aws/docker-compose.yml exec login python crear_administrador.py'
```

Usuario, correo y una contraseña de 12 caracteres o más (no se ve al escribirla). Ese Administrador crea las demás cuentas del personal desde la página (**Registrar usuario**).

## 10. Comprobar que todo funciona

- `https://3-148-60-126.sslip.io` muestra la tienda con el candado 🔒 (certificado de Let's Encrypt).
- `http://...` (sin la "s") manda solo a `https://`.
- Entra con el Administrador y revisa **Órdenes**, **Almacén** y **Mensajes**.
- `https://.../docs` da **404** (en producción no se publica).
- Desde tu Mac, los puertos **1433** (SQL Server) y **8080** (Gateway) de la IP **no** responden.
- Si algo falla, mira los registros en el servidor:

```bash
docker compose -f aws/docker-compose.yml ps
docker compose -f aws/docker-compose.yml logs --tail 50 gateway
docker compose -f aws/docker-compose.yml logs --tail 50 login
```

Un error `certificate verify failed` en los microservicios quiere decir que no pudieron revisar el certificado de RDS: confirma que `BD_SERVER` es el **punto de conexión** (no una IP). Solo como último recurso, `BD_CONFIAR_CERTIFICADO=si` deja la conexión cifrada pero sin revisar el certificado.

### Publicar una versión nueva

En tu Mac, `git push`. Luego:

```bash
ssh -i ~/.ssh/refaccionaria.pem ubuntu@3.148.60.126 'cd ~/Refaccionaria && git pull && docker compose -f aws/docker-compose.yml up -d --build'
```

Para regresar a la versión anterior: en el servidor, `git log --oneline`, `git checkout <commit>` y el mismo `up -d --build`.

## 11. Apagar o borrar todo

| Qué | Cómo | ¿Sigue gastando crédito? |
|---|---|---|
| Pausar el servidor | EC2 → instancia → **Detener** | El disco y la IP elástica sí (poco) |
| Pausar la base | RDS → **Acciones → Detener temporalmente** | El disco sí. **AWS la vuelve a prender sola a los 7 días** |
| Borrar todo | EC2 → **Terminar**; **Liberar** la IP elástica; RDS → **Modificar** → quita *Protección contra la eliminación* → **Eliminar** | No |

## Lo que queda pendiente

- **GitHub Pages:** la página publicada en `github.io` no puede usar la API (llama a `/api` de github.io). En AWS no hace falta, porque el Gateway entrega la página; si no la usas, desactívala en GitHub → *Settings* → *Pages*.
- **Una sola copia del Gateway:** el límite de intentos de login cuenta en memoria. Con un solo servidor está bien; con varios, cada uno contaría por su lado.
- **Respaldos:** con el plan Free solo hay 1 día de respaldos automáticos. Antes de algo importante, haz una instantánea manual en RDS (**Acciones → Tomar instantánea**).

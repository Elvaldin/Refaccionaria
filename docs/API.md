# API

Todas las rutas se llaman a través del **Gateway**: `http://127.0.0.1:8080`

La documentación interactiva, donde se puede probar cada ruta, está en http://127.0.0.1:8080/docs.

Los errores responden `{"detail": "mensaje"}`.

## Sesión con token

1. `POST /api/login` regresa un **token**.
2. Las rutas que necesitan saber **quién** hace la petición lo piden en el encabezado:

   ```
   Authorization: Bearer <token>
   ```

3. El microservicio saca del token el `id_login` y revisa el **rol** en la base de datos. No se le cree a ningún `id_login` que venga en la URL o en el cuerpo: si se manda, se ignora.

- El token está firmado con `TOKEN_SECRETO` (HMAC-SHA256), que comparten los 5 `.env`, y dura **8 horas**.
- **401** si falta el token, si es falso, si está alterado o si ya venció.
- **403** si el token es válido pero el rol no tiene permiso.
- En `/docs`, las rutas con token tienen un campo `authorization`: ahí se escribe `Bearer ` seguido del token.

En las tablas de abajo, 🔒 marca las rutas que piden token.

## Login · puerto 8000

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/login` | Revisa usuario y contraseña. Regresa el **token** y el **rol** |
| POST | `/api/usuarios` | Registrar usuario nuevo. El token solo hace falta para crear personal (ver abajo) |

```json
// POST /api/login
{ "username": "admin", "password": "Admin123" }

// 200
{ "message": "Login exitoso", "status": "success", "token": "eyJpZCI6IDIsIC4uLn0.Xk3...", "id_login": 2, "username": "admin", "rol": "Administrador" }

// 401
{ "detail": "Credenciales invalidas" }
```

`id_login`, `username` y `rol` se regresan para que la página los muestre; los permisos salen del token.

```json
// POST /api/usuarios: cualquiera se registra como Cliente (sin token)
{ "username": "juan", "email": "juan@correo.com", "password": "secreta123" }

// POST /api/usuarios: con el token del Administrador se puede dar otro rol
// Authorization: Bearer <token del admin>
{ "username": "bodega", "email": "bodega@correo.com", "password": "secreta123", "rol": "Almacenista" }

// 201
{ "id_login": 7, "username": "bodega", "email": "bodega@correo.com", "rol": "Almacenista" }
```

- Roles: `Administrador`, `Empleado`, `Almacenista`, `Cliente`.
- **403** si alguien sin token de Administrador intenta crear un usuario que no sea Cliente.
- **409** si el usuario o el correo ya existen. **400** si la contraseña tiene menos de 10 caracteres o el usuario menos de 3 letras.
- Para cambiar la contraseña de un usuario existente no hay ruta: se usa `Backend/Login/cambiar_contrasena.py` desde la terminal (pide 12 caracteres o más).
- El primer Administrador del servidor tampoco se crea por la API: se usa `Backend/Login/crear_administrador.py` (pide 12 caracteres o más).


## Productos · puerto 8001

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/categorias` | Lista de categorías |
| POST | `/api/categorias` 🔒 | Crear categoría `{ "nombre", "descripcion" }` (409 si el nombre ya existe) |
| DELETE | `/api/categorias/{id}` 🔒 | Borrar categoría (409 si tiene productos) |
| GET | `/api/productos` | Lista de productos. Filtros: `?categoria=1`, `?buscar=filtro` |
| GET | `/api/productos/{id}` | Un producto (404 si no existe) |
| POST | `/api/productos` 🔒 | Crear producto `{ "nombre", "descripcion", "precio", "stock", "id_categoria", "imagen" }`. `imagen` es opcional: una ruta `img/productos/foto.jpg` (jpg, png o webp) o una dirección `https://` (422 si es otra cosa) |
| PUT | `/api/productos/{id}` 🔒 | Editar producto. El `stock` que se mande se ignora: solo cambia con las órdenes |
| DELETE | `/api/productos/{id}` 🔒 | Borrar (409 si ya está en una orden, promoción o movimiento de inventario) |

- Las rutas que hacen cambios solo las puede usar el **Administrador** (**401** sin token, **403** para los demás roles). Ver la lista es libre.

## Promociones · puerto 8002

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/dashboard` | Promociones **vigentes hoy**, con sus productos y precio con descuento |
| GET | `/api/promociones` | Todas. `?vigentes=true` para solo las vigentes |
| GET | `/api/promociones/{id}` | Una promoción |
| POST | `/api/promociones` 🔒 | Crear `{ "nombre", "descuento", "fecha_inicio", "fecha_fin", "activa", "productos": [1, 2] }` |
| PUT | `/api/promociones/{id}` 🔒 | Editar. Si trae `"productos": [...]`, esos quedan como sus productos; si no, no se tocan |
| DELETE | `/api/promociones/{id}` 🔒 | Borrar (también quita sus productos) |
| POST | `/api/promociones/{id}/productos` 🔒 | Agregar producto `{ "id_producto": 1 }` (409 si ya estaba) |
| DELETE | `/api/promociones/{id}/productos/{id_producto}` 🔒 | Quitar producto |

- Igual que en Productos: los cambios solo los hace el **Administrador** (**401** sin token, **403** para los demás).

Las fechas van en formato `2026-10-01T00:00:00`. Una promoción nueva no puede empezar en un día que ya pasó (400); al editar una que ya empezó, su fecha de inicio se puede dejar igual pero no moverse a otro día pasado.

## Órdenes · puerto 8003

Todas las rutas de Órdenes piden token.

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/ordenes` 🔒 | Lista con su detalle y total. Un Cliente solo recibe las suyas. Filtros: `?tipo=Compra`, `?tipo=Venta`, `?estado=Cancelada` |
| GET | `/api/ordenes/{id}` 🔒 | Una orden con sus productos (403 si un Cliente pide una ajena) |
| POST | `/api/ordenes` 🔒 | Crear orden (queda **Pendiente**) a nombre de quien tiene la sesión |
| PATCH | `/api/ordenes/{id}/estado` 🔒 | Cambiar estado `{ "estado": "Completada" }` |
| GET | `/api/inventario/movimientos` 🔒 | Entradas y salidas de stock (un Cliente recibe 403). Filtro: `?id_producto=1` |

```json
// POST /api/ordenes
// Authorization: Bearer <token>
{
  "tipo": "Venta",
  "observaciones": "Cliente de mostrador",
  "productos": [
    { "id_producto": 1, "cantidad": 2 },
    { "id_producto": 3, "cantidad": 1, "precio_unitario": 120 }
  ]
}
```

- `tipo`: `Compra` (entra mercancía) o `Venta` (sale mercancía).
- Si no se manda `precio_unitario`, se usa el precio actual del producto. En una **Venta** ya lleva el descuento de su promoción vigente (si está en varias, el mayor); en una **Compra**, no.
- Al pasar a **Completada** se mueve el stock. Si una venta no tiene stock suficiente responde **409** con el detalle.
- Estados: `Pendiente → En Proceso → Completada`, o `Cancelada` desde los dos primeros.

Los permisos dependen del rol de quien tiene la sesión (**403** si no tiene permiso):

| | Administrador | Empleado | Almacenista | Cliente |
|---|---|---|---|---|
| Crear Venta | ✅ | ✅ | ❌ | ✅ siempre al precio de la tienda (con promoción) |
| Crear Compra | ✅ | ❌ | ✅ | ❌ |
| Avanzar Ventas (En Proceso / Completada) | ✅ | ✅ | ❌ | ❌ |
| Avanzar Compras (En Proceso / Completada) | ✅ | ❌ | ✅ | ❌ |
| Cancelar | ✅ | ❌ | ❌ | ❌ |
| Ver órdenes | todas | todas | todas | solo las suyas |
| Ver movimientos de inventario | ✅ | ✅ | ✅ | ❌ |

## Soporte · puerto 8004

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/soporte` | Datos de contacto de la tienda |
| GET | `/api/soporte/{id}` | Un contacto |
| POST | `/api/soporte` 🔒 | Crear `{ "correo", "telefono", "direccion", "horario" }`. Debe traer correo, teléfono o dirección. Solo Administrador |
| PUT | `/api/soporte/{id}` 🔒 | Editar. Solo Administrador |
| DELETE | `/api/soporte/{id}` 🔒 | Borrar. Solo Administrador |

### Chat de soporte (mismo microservicio, puerto 8004)

Todas las rutas del chat piden token.

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/conversaciones` 🔒 | Lista con el último mensaje. El Cliente recibe solo las suyas; el personal, todas |
| GET | `/api/conversaciones/{id}` 🔒 | Una conversación con todos sus mensajes |
| POST | `/api/conversaciones` 🔒 | Empezar una conversación (solo el Cliente) |
| POST | `/api/conversaciones/{id}/mensajes` 🔒 | Contestar `{ "texto": "..." }`. Regresa la conversación completa |
| PATCH | `/api/conversaciones/{id}/estado` 🔒 | Cerrar o reabrir `{ "estado": "Cerrada" }` (solo el personal) |
| DELETE | `/api/conversaciones/{id}` 🔒 | Eliminar con todos sus mensajes (solo el Administrador) |

```json
// POST /api/conversaciones
// Authorization: Bearer <token del cliente>
{ "asunto": "Garantía", "mensaje": "Mi batería ya no carga" }

// 201
{
  "id": 1, "id_login": 4, "cliente": "cliente", "asunto": "Garantía", "estado": "Abierta",
  "fecha": "2026-10-27T18:30:00", "esperando_respuesta": true,
  "ultimo_mensaje": { "id": 1, "id_login": 4, "autor": "cliente", "rol": "Cliente", "texto": "Mi batería ya no carga", "fecha": "2026-10-27T18:30:00" },
  "mensajes": [ { "id": 1, "id_login": 4, "autor": "cliente", "rol": "Cliente", "texto": "Mi batería ya no carga", "fecha": "2026-10-27T18:30:00" } ]
}
```

- En las respuestas, `id_login` dice de quién es la conversación o el mensaje (sale de la base de datos, no de la petición).
- `esperando_respuesta` es `true` cuando el último mensaje es del cliente, o sea, le toca contestar al personal.
- **403** si el rol no tiene permiso (por ejemplo, el Almacenista, o un Cliente que abre una conversación ajena). **409** si se escribe en una conversación cerrada. **400** si el mensaje está vacío.

## Gateway · puerto 8080

| Ruta | Descripción |
|---|---|
| `/` | La página web de la tienda (`Frontend/`) |
| `/gateway` | Lista de todas las APIs con su dirección completa y si cada microservicio está encendido (no existe con `ENTORNO=produccion`) |
| `/docs` | Swagger con un menú para elegir el microservicio |
| `/openapi/{servicio}.json` | Descripción OpenAPI de cada microservicio (`login`, `productos`, `promociones`, `ordenes`, `soporte`) |

La página y la API están en la misma dirección, así que el navegador no necesita CORS. Si otro sitio tiene que llamar a la API, se pone en `CORS_ORIGENES` (ver el README). Las respuestas de `/api` llevan `Cache-Control: no-store` y no dicen qué servidor hay detrás.

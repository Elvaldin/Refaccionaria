# API

Todas las rutas se llaman a través del **Gateway**: `http://127.0.0.1:8080`

La documentación interactiva, donde se puede probar cada ruta, está en http://127.0.0.1:8080/docs.

Los errores responden `{"detail": "mensaje"}`.

## Login · puerto 8000

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/login` | Revisa usuario y contraseña. Regresa el **rol** |
| POST | `/api/usuarios` | Registrar usuario nuevo |

```json
// POST /api/login
{ "username": "admin", "password": "Admin123" }

// 200
{ "message": "Login exitoso", "status": "success", "id_login": 2, "username": "admin", "rol": "Administrador" }

// 401
{ "detail": "Credenciales invalidas" }
```

```json
// POST /api/usuarios: cualquiera se registra como Cliente
{ "username": "juan", "email": "juan@correo.com", "password": "secreta1" }

// POST /api/usuarios: el Administrador (id_creador) puede dar otro rol
{ "username": "bodega", "email": "bodega@correo.com", "password": "secreta1", "rol": "Almacenista", "id_creador": 2 }

// 201
{ "id_login": 7, "username": "bodega", "email": "bodega@correo.com", "rol": "Almacenista" }
```

- Roles: `Administrador`, `Empleado`, `Almacenista`, `Cliente`.
- **403** si alguien que no es Administrador intenta crear un usuario que no sea Cliente.
- **409** si el usuario o el correo ya existen. **400** si la contraseña tiene menos de 6 caracteres o el usuario menos de 3 letras.


## Productos · puerto 8001

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/categorias` | Lista de categorías |
| POST | `/api/categorias?id_login=2` | Crear categoría `{ "nombre", "descripcion" }` (409 si el nombre ya existe) |
| DELETE | `/api/categorias/{id}?id_login=2` | Borrar categoría (409 si tiene productos) |
| GET | `/api/productos` | Lista de productos. Filtros: `?categoria=1`, `?buscar=filtro` |
| GET | `/api/productos/{id}` | Un producto (404 si no existe) |
| POST | `/api/productos?id_login=2` | Crear producto `{ "nombre", "descripcion", "precio", "stock", "id_categoria", "imagen" }`. `imagen` es opcional: una ruta `img/productos/foto.jpg` (jpg, png o webp) o una dirección `https://` (422 si es otra cosa) |
| PUT | `/api/productos/{id}?id_login=2` | Editar producto. El `stock` que se mande se ignora: solo cambia con las órdenes |
| DELETE | `/api/productos/{id}?id_login=2` | Borrar (409 si ya está en una orden, promoción o movimiento de inventario) |

- Las rutas que hacen cambios piden `?id_login=` y solo las puede usar el **Administrador** (**403** para los demás roles o si el usuario no existe, **422** si falta). Ver la lista es libre.

## Promociones · puerto 8002

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/dashboard` | Promociones **vigentes hoy**, con sus productos y precio con descuento |
| GET | `/api/promociones` | Todas. `?vigentes=true` para solo las vigentes |
| GET | `/api/promociones/{id}` | Una promoción |
| POST | `/api/promociones?id_login=2` | Crear `{ "nombre", "descuento", "fecha_inicio", "fecha_fin", "activa", "productos": [1, 2] }` |
| PUT | `/api/promociones/{id}?id_login=2` | Editar. Si trae `"productos": [...]`, esos quedan como sus productos; si no, no se tocan |
| DELETE | `/api/promociones/{id}?id_login=2` | Borrar (también quita sus productos) |
| POST | `/api/promociones/{id}/productos?id_login=2` | Agregar producto `{ "id_producto": 1 }` (409 si ya estaba) |
| DELETE | `/api/promociones/{id}/productos/{id_producto}?id_login=2` | Quitar producto |

- Igual que en Productos: los cambios solo los hace el **Administrador** (**403** para los demás).

Las fechas van en formato `2026-10-01T00:00:00`. Una promoción nueva no puede empezar en un día que ya pasó (400); al editar una que ya empezó, su fecha de inicio se puede dejar igual pero no moverse a otro día pasado.

## Órdenes · puerto 8003

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/ordenes` | Lista con su detalle y total. **Obligatorio** `?id_login=4` (quién consulta; un Cliente solo recibe las suyas). Filtros: `?tipo=Compra`, `?tipo=Venta`, `?estado=Cancelada` |
| GET | `/api/ordenes/{id}` | Una orden con sus productos. **Obligatorio** `?id_login=4` (quién consulta) |
| POST | `/api/ordenes` | Crear orden (queda **Pendiente**) |
| PATCH | `/api/ordenes/{id}/estado` | Cambiar estado `{ "estado": "Completada", "id_login": 2 }` |
| GET | `/api/inventario/movimientos` | Entradas y salidas de stock. **Obligatorio** `?id_login=2` (un Cliente recibe 403). Filtro: `?id_producto=1` |

```json
// POST /api/ordenes
{
  "id_login": 1,
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

- `id_login` dice **quién** hace la petición, y de su rol dependen los permisos (**403** si no tiene permiso):

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
| POST | `/api/soporte` | Crear `{ "correo", "telefono", "direccion", "horario" }`. Debe traer correo, teléfono o dirección. Solo Administrador: `?id_login=1` |
| PUT | `/api/soporte/{id}` | Editar. Solo Administrador: `?id_login=1` |
| DELETE | `/api/soporte/{id}` | Borrar. Solo Administrador: `?id_login=1` |

### Chat de soporte (mismo microservicio, puerto 8004)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/conversaciones?id_login=4` | Lista con el último mensaje. El Cliente recibe solo las suyas; el personal, todas |
| GET | `/api/conversaciones/{id}?id_login=4` | Una conversación con todos sus mensajes |
| POST | `/api/conversaciones` | Empezar una conversación (solo el Cliente) |
| POST | `/api/conversaciones/{id}/mensajes` | Contestar `{ "id_login": 2, "texto": "..." }`. Regresa la conversación completa |
| PATCH | `/api/conversaciones/{id}/estado` | Cerrar o reabrir `{ "id_login": 2, "estado": "Cerrada" }` (solo el personal) |
| DELETE | `/api/conversaciones/{id}?id_login=2` | Eliminar con todos sus mensajes (solo el Administrador) |

```json
// POST /api/conversaciones
{ "id_login": 4, "asunto": "Garantía", "mensaje": "Mi batería ya no carga" }

// 201
{
  "id": 1, "id_login": 4, "cliente": "cliente", "asunto": "Garantía", "estado": "Abierta",
  "fecha": "2026-10-27T18:30:00", "esperando_respuesta": true,
  "ultimo_mensaje": { "id": 1, "id_login": 4, "autor": "cliente", "rol": "Cliente", "texto": "Mi batería ya no carga", "fecha": "2026-10-27T18:30:00" },
  "mensajes": [ { "id": 1, "id_login": 4, "autor": "cliente", "rol": "Cliente", "texto": "Mi batería ya no carga", "fecha": "2026-10-27T18:30:00" } ]
}
```

- `esperando_respuesta` es `true` cuando el último mensaje es del cliente, o sea, le toca contestar al personal.
- **403** si el rol no tiene permiso (por ejemplo, el Almacenista, o un Cliente que abre una conversación ajena). **409** si se escribe en una conversación cerrada. **400** si el mensaje está vacío.

## Gateway · puerto 8080

| Ruta | Descripción |
|---|---|
| `/` | Lista de todas las APIs con su dirección completa y si cada microservicio está encendido |
| `/docs` | Swagger con un menú para elegir el microservicio |
| `/openapi/{servicio}.json` | Descripción OpenAPI de cada microservicio (`login`, `productos`, `promociones`, `ordenes`, `soporte`) |

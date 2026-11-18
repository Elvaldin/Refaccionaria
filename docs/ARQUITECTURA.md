# Arquitectura

## Vista general

```
┌──────────────────────────┐
│  Frontend (navegador)    │  index · producto · ordenes · contacto
└────────────┬─────────────┘
             │ HTTP  (http://127.0.0.1:8080/api/...)
┌────────────▼─────────────┐
│  Gateway en Go  :8080    │  Reenvía cada ruta al microservicio que le toca,
│                          │  agrega CORS, junta la documentación y avisa si
│                          │  un microservicio está apagado (error 502).
└──┬────┬────┬────┬────┬───┘
   │    │    │    │    │
 :8000 :8001 :8002 :8003 :8004     Microservicios en Python (FastAPI)
 Login Prod. Prom. Órd. Soporte
   │    │    │    │    │
┌──▼────▼────▼────▼────▼───┐
│  SQL Server              │  Base de datos "Refaccionaria"
└──────────────────────────┘
```

**¿Por qué microservicios?** Cada parte del negocio (login, productos, promociones, órdenes y soporte) es un programa independiente con su propio puerto. Si uno falla, los demás siguen funcionando, y cada uno se puede cambiar sin tocar a los otros.

**¿Por qué un Gateway?** La página web solo conoce **una dirección** (`:8080`). No necesita saber en qué puerto vive cada microservicio. Si uno cambia de puerto, solo se actualiza la tabla de `Backend-Go/gateway/servicios.go`.

## Arquitectura limpia en cada microservicio

Cada microservicio tiene 4 capas. **Las dependencias solo apuntan hacia adentro**: las capas de afuera conocen a las de adentro, nunca al revés.

```
        ┌───────────────────────────────────────┐
        │  API             (FastAPI, Pydantic)  │  ← rutas HTTP
        │  ┌─────────────────────────────────┐  │
        │  │ Infrastructure (pyodbc, bcrypt) │  │  ← base de datos, librerías
        │  │  ┌───────────────────────────┐  │  │
        │  │  │ Application               │  │  │  ← casos de uso + interfaces
        │  │  │  ┌─────────────────────┐  │  │  │
        │  │  │  │ Domain              │  │  │  │  ← entidades del negocio
        │  │  │  └─────────────────────┘  │  │  │
        │  │  └───────────────────────────┘  │  │
        │  └─────────────────────────────────┘  │
        └───────────────────────────────────────┘
```

| Capa | Carpeta | Qué contiene | Ejemplo (Órdenes) | Puede importar |
|---|---|---|---|---|
| **Dominio** | `Domain/` | Las entidades del negocio, sin librerías externas | `Orden`, `DetalleOrden`, `MovimientoInventario` | Nada (solo Python) |
| **Aplicación** | `Application/` | Casos de uso (reglas del negocio) e **interfaces** de lo que necesitan | `GestionarOrdenes`: transiciones de estado, revisar stock. Interfaz `OrdenRepository` | `Domain` |
| **Infraestructura** | `Infrastructure/` | Implementaciones concretas: SQL Server, bcrypt, `.env` | `SQLServerOrdenRepository` (SQL con transacciones) | `Domain`, `Application` |
| **API** | `API/` | Rutas HTTP, validación de entrada (Pydantic) y conversión de errores a códigos HTTP. Aquí se "arma" todo | `POST /api/ordenes`, `PATCH /api/ordenes/{id}/estado` | Todas |

### Inversión de dependencias

Los casos de uso no dependen de SQL Server. Dependen de una **interfaz** definida en `Application/`:

```python
# Application/orden_use_cases.py — dice QUÉ necesita
class OrdenRepository(ABC):
    @abstractmethod
    def find_by_id(self, id_orden: int) -> Optional[Orden]: ...

# Infrastructure/repository.py — dice CÓMO se hace con SQL Server
class SQLServerOrdenRepository(OrdenRepository):
    def find_by_id(self, id_orden): ...   # SELECT ... FROM ORDENES

# API/main.py — une las piezas
GestionarOrdenes(orden_repository=SQLServerOrdenRepository())
```

Si mañana se cambia SQL Server por otra base de datos, solo se escribe un nuevo repositorio en `Infrastructure/`. Los casos de uso y el dominio no cambian.

El Login hace lo mismo con las contraseñas: el caso de uso pide un `PasswordHasher` y la infraestructura le da `BcryptPasswordHasher`.

### Errores

Los casos de uso lanzan errores propios del negocio (`NoEncontradoError`, `DatosInvalidosError`, `ConflictoError`...). La capa **API** los traduce a códigos HTTP:

| Error del caso de uso | Código HTTP |
|---|---|
| No existe | 404 |
| Datos que no cumplen una regla | 400 |
| Formato inválido (Pydantic) | 422 |
| Conflicto: estado no permitido, sin stock, producto en uso | 409 |
| Credenciales incorrectas | 401 |
| Microservicio apagado (lo detecta el Gateway) | 502 |

## Reglas del negocio importantes

- **Órdenes:** `Pendiente → En Proceso → Completada`. Desde Pendiente o En Proceso también se puede `Cancelar`. Completada y Cancelada son finales.
- **Hora de las órdenes:** la fecha de las órdenes y de los movimientos de inventario sale de Python y no de SQL Server, por el reloj UTC de Docker.
- **El inventario solo se mueve al completar una orden.** Una Compra suma stock (Entrada) y una Venta lo resta (Salida). El stock, los movimientos y el estado se guardan **en una sola transacción**: si algo falla, no se guarda nada.
- **Una venta no puede dejar el stock negativo.** Se revisa en el caso de uso y también en el SQL (`AND Stock >= cantidad`).
- **Promociones vigentes:** activas y con la fecha de hoy entre `Fecha_inicio` y `Fecha_fin`. El precio con descuento se calcula en la entidad. Una **Venta** cobra ese precio con descuento (el microservicio de Órdenes lo lee de las tablas de promociones); una **Compra** al proveedor, el precio normal.
- **Catálogo:** solo el Administrador crea, edita o elimina productos, categorías y promociones. Cada microservicio lo revisa con `RevisarPermisos` (capa de Aplicación) antes de hacer el cambio. Al editar un producto el stock no cambia, para que siempre cuadre con los movimientos de inventario.
- **Carrito:** vive en el navegador (`localStorage`), no en la base de datos. Al hacer el pedido se crea una orden de Venta normal, y el precio lo pone el microservicio de Órdenes, no la página. Se vacía al cerrar sesión.
- **Contraseñas:** se guardan como hash bcrypt, nunca en texto.
- **Chat de soporte:** solo un Cliente empieza conversaciones; el Administrador y los Empleados contestan. En una conversación cerrada ya no se escribe. La hora de cada mensaje sale de Python y no de SQL Server, por el reloj UTC de Docker.

## Base de datos

```
LOGIN ─────────────< ORDENES ─────< DETALLEORDEN >───── PRODUCTOS >──── CATEGORIAS
                        │                                   │
                        └───────< MOVIMIENTOS_INVENTARIO >──┘
                                                            │
PROMOCION ─────< PROMOCIONPRODUCTO >────────────────────────┘

SOPORTE (datos de contacto de la tienda)

LOGIN ─────< CONVERSACION ─────< MENSAJE
  │                                 │
  └─────────────────────────────────┘   (cada mensaje sabe quién lo escribió)
```

`─<` significa "uno a muchos". Los scripts están en `BD/`.

## Frontend

HTML, CSS y JavaScript sin frameworks. `script.js` hace todas las peticiones con `fetch` al Gateway (`http://127.0.0.1:8080/api`) y cada página usa solo la parte que le toca. Los textos que vienen de la base de datos se escapan antes de ponerlos en el HTML.

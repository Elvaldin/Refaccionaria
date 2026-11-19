import sys
import os
from datetime import datetime
from typing import List, Literal, Optional
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Infrastructure.repository import SQLServerOrdenRepository
from Infrastructure.tokens import leer_token
from Domain.entities import Orden, DetalleOrden
from Application.orden_use_cases import (
    GestionarOrdenes, NoEncontradoError, DatosInvalidosError, ConflictoError, PermisoDenegadoError,
)

# redirect_slashes=False: /api/login/ (con diagonal al final) da 404 en vez de
# redirigir a una dirección http:// interna
app = FastAPI(title="Ordenes API", redirect_slashes=False)

TipoOrden = Literal["Compra", "Venta"]
EstadoOrden = Literal["Pendiente", "En Proceso", "Completada", "Cancelada"]

# Límites: lo que cabe en la base (DECIMAL(10,2) llega a 99,999,999.99) y lo
# razonable en una orden. Sin ellos, un número gigante tronaba la base (error 500)
class DetalleRequest(BaseModel):
    id_producto: int = Field(gt=0)
    cantidad: int = Field(gt=0, le=10000)
    precio_unitario: Optional[float] = Field(default=None, ge=0, le=99_999_999.99)

class OrdenRequest(BaseModel):
    tipo: TipoOrden
    observaciones: Optional[str] = Field(default=None, max_length=255)
    productos: List[DetalleRequest] = Field(min_length=1, max_length=100)

class CambiarEstadoRequest(BaseModel):
    estado: EstadoOrden

class DetalleResponse(BaseModel):
    id_producto: int
    producto: str
    cantidad: int
    precio_unitario: float
    subtotal: float

class OrdenResponse(BaseModel):
    id: int
    id_login: int
    tipo: str
    observaciones: Optional[str]
    estado: str
    fecha: datetime
    detalles: List[DetalleResponse]
    total: float

class MovimientoResponse(BaseModel):
    id: int
    id_producto: int
    producto: str
    id_orden: Optional[int]
    tipo: str
    cantidad: int
    observaciones: Optional[str]
    fecha: datetime

def usuario_actual(authorization: Optional[str] = Header(default=None)) -> int:
    """El id_login de quien hace la petición, sacado del token. Sin token válido: 401."""
    if authorization and authorization.startswith("Bearer "):
        id_login = leer_token(authorization[len("Bearer "):])
        if id_login is not None:
            return id_login
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Tu sesión venció o no es válida. Inicia sesión de nuevo.",
                        headers={"WWW-Authenticate": "Bearer"})

def use_case() -> GestionarOrdenes:
    return GestionarOrdenes(orden_repository=SQLServerOrdenRepository())

def to_response(orden: Orden) -> OrdenResponse:
    detalles = [
        DetalleResponse(id_producto=d.id_producto, producto=d.producto, cantidad=d.cantidad,
                        precio_unitario=d.precio_unitario, subtotal=d.subtotal)
        for d in orden.detalles
    ]
    return OrdenResponse(id=orden.id, id_login=orden.id_login, tipo=orden.tipo,
                         observaciones=orden.observaciones, estado=orden.estado,
                         fecha=orden.fecha, detalles=detalles, total=orden.total)

def manejar_error(e: Exception):
    if isinstance(e, NoEncontradoError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, DatosInvalidosError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if isinstance(e, ConflictoError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if isinstance(e, PermisoDenegadoError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    raise e

# ---------- Órdenes ----------

@app.get("/api/ordenes", response_model=List[OrdenResponse])
def listar_ordenes(tipo: Optional[TipoOrden] = None, estado: Optional[EstadoOrden] = None,
                   id_login: int = Depends(usuario_actual)):
    # id_login = quién consulta (sale del token). Si es Cliente, solo recibe sus propias órdenes
    try:
        return [to_response(o) for o in use_case().listar(id_login, tipo, estado)]
    except Exception as e:
        manejar_error(e)

@app.get("/api/ordenes/{id_orden}", response_model=OrdenResponse)
def obtener_orden(id_orden: int, id_login: int = Depends(usuario_actual)):
    try:
        return to_response(use_case().obtener(id_orden, id_login))
    except Exception as e:
        manejar_error(e)

@app.post("/api/ordenes", response_model=OrdenResponse, status_code=status.HTTP_201_CREATED)
def crear_orden(request: OrdenRequest, id_login: int = Depends(usuario_actual)):
    # La orden queda a nombre de quien tiene la sesión, no de lo que mande la página
    detalles = [DetalleOrden(**p.model_dump()) for p in request.productos]
    orden = Orden(id_login=id_login, tipo=request.tipo,
                  observaciones=request.observaciones, detalles=detalles)
    try:
        return to_response(use_case().crear(orden))
    except Exception as e:
        manejar_error(e)

@app.patch("/api/ordenes/{id_orden}/estado", response_model=OrdenResponse)
def cambiar_estado(id_orden: int, request: CambiarEstadoRequest, id_login: int = Depends(usuario_actual)):
    try:
        return to_response(use_case().cambiar_estado(id_orden, request.estado, id_login))
    except Exception as e:
        manejar_error(e)

# ---------- Inventario ----------

@app.get("/api/inventario/movimientos", response_model=List[MovimientoResponse])
def listar_movimientos(id_producto: Optional[int] = None, id_login: int = Depends(usuario_actual)):
    try:
        return [MovimientoResponse(**vars(m)) for m in use_case().movimientos(id_login, id_producto)]
    except Exception as e:
        manejar_error(e)
import sys
import os
from datetime import datetime
from typing import List, Optional
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Infrastructure.repository import SQLServerPromocionRepository, SQLServerUsuarioRepository
from Infrastructure.tokens import leer_token
from Domain.entities import Promocion
from Application.promocion_use_cases import GestionarPromociones, NoEncontradoError, DatosInvalidosError, RevisarPermisos, PermisoDenegadoError

app = FastAPI(title="Promociones API")


class PromocionRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=255)
    descuento: float = Field(ge=0, le=100)
    fecha_inicio: datetime
    fecha_fin: datetime
    activa: bool = True

    @field_validator("fecha_inicio", "fecha_fin")
    @classmethod
    def hora_de_la_tienda(cls, fecha: datetime) -> datetime:
        # Si la fecha viene con zona horaria (ej. "2026-11-20T00:00:00Z"), se pasa a la
        # hora de la tienda (TZ) y se le quita la zona, como todas las demás fechas.
        # Sin esto, comparar fechas con y sin zona truena (error 500)
        if fecha.tzinfo is not None:
            return fecha.astimezone().replace(tzinfo=None)
        return fecha


class CrearPromocionRequest(PromocionRequest):
    productos: List[int] = Field(default_factory=list)   # ids de los productos que entran a la promoción

class EditarPromocionRequest(PromocionRequest):
    productos: Optional[List[int]] = None   # Si viene, esos quedan como sus productos; si no, no se tocan

class AgregarProductoRequest(BaseModel):
    id_producto: int


class ProductoEnPromocionResponse(BaseModel):
    id: int
    nombre: str
    precio: float
    precio_con_descuento: float


class PromocionResponse(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str]
    descuento: float
    fecha_inicio: datetime
    fecha_fin: datetime
    activa: bool
    productos: List[ProductoEnPromocionResponse]


def use_case() -> GestionarPromociones:
    return GestionarPromociones(promocion_repository=SQLServerPromocionRepository())

def usuario_actual(authorization: Optional[str] = Header(default=None)) -> int:
    """El id_login de quien hace la petición, sacado del token. Sin token válido: 401."""
    if authorization and authorization.startswith("Bearer "):
        id_login = leer_token(authorization[len("Bearer "):])
        if id_login is not None:
            return id_login
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Tu sesión venció o no es válida. Inicia sesión de nuevo.",
                        headers={"WWW-Authenticate": "Bearer"})

def solo_administrador(id_login: int) -> None:
    # id_login = quién hace el cambio (la página lo manda como ?id_login=2)
    try:
        RevisarPermisos(usuario_repository=SQLServerUsuarioRepository()).solo_administrador(id_login)
    except PermisoDenegadoError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

def to_response(promocion: Promocion) -> PromocionResponse:
    datos = vars(promocion).copy()
    datos["productos"] = [ProductoEnPromocionResponse(**vars(p)) for p in promocion.productos]
    return PromocionResponse(**datos)


# ---------- Dashboard ----------

@app.get("/api/dashboard", response_model=List[PromocionResponse])
def dashboard():
    """Promociones activas y vigentes hoy, con sus productos y precio con descuento."""
    return [to_response(p) for p in use_case().listar(solo_vigentes=True)]


# ---------- Promociones ----------

@app.get("/api/promociones", response_model=List[PromocionResponse])
def listar_promociones(vigentes: bool = False):
    return [to_response(p) for p in use_case().listar(solo_vigentes=vigentes)]


@app.get("/api/promociones/{id_promocion}", response_model=PromocionResponse)
def obtener_promocion(id_promocion: int):
    try:
        return to_response(use_case().obtener(id_promocion))
    except NoEncontradoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@app.post("/api/promociones", response_model=PromocionResponse, status_code=status.HTTP_201_CREATED)
def crear_promocion(request: CrearPromocionRequest, id_login: int = Depends(usuario_actual)):
    solo_administrador(id_login)
    datos = request.model_dump(exclude={"productos"})
    try:
        return to_response(use_case().crear(Promocion(**datos), request.productos))
    except NoEncontradoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DatosInvalidosError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.put("/api/promociones/{id_promocion}", response_model=PromocionResponse)
def actualizar_promocion(id_promocion: int, request: EditarPromocionRequest, id_login: int = Depends(usuario_actual)):
    solo_administrador(id_login)
    try:
        promocion = Promocion(id_promocion=id_promocion, **request.model_dump(exclude={"productos"}))
        return to_response(use_case().actualizar(promocion, request.productos))
    except NoEncontradoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DatosInvalidosError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.delete("/api/promociones/{id_promocion}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_promocion(id_promocion: int, id_login: int = Depends(usuario_actual)):
    solo_administrador(id_login)
    try:
        use_case().eliminar(id_promocion)
    except NoEncontradoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ---------- Productos de una promoción ----------

@app.post("/api/promociones/{id_promocion}/productos", response_model=PromocionResponse)
def agregar_producto(id_promocion: int, request: AgregarProductoRequest, id_login: int = Depends(usuario_actual)):
    solo_administrador(id_login)
    try:
        return to_response(use_case().agregar_producto(id_promocion, request.id_producto))
    except NoEncontradoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DatosInvalidosError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@app.delete("/api/promociones/{id_promocion}/productos/{id_producto}", response_model=PromocionResponse)
def quitar_producto(id_promocion: int, id_producto: int, id_login: int = Depends(usuario_actual)):
    solo_administrador(id_login)
    try:
        return to_response(use_case().quitar_producto(id_promocion, id_producto))
    except NoEncontradoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
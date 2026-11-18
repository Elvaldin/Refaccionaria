import sys
import os
from typing import List, Optional
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Infrastructure.repository import SQLServerCategoriaRepository, SQLServerProductoRepository, SQLServerUsuarioRepository
from Infrastructure.tokens import leer_token
from Domain.entities import Producto
from Application.producto_use_cases import (
    GestionarCategorias, GestionarProductos, NoEncontradoError, ProductoEnUsoError,
    CategoriaEnUsoError, CategoriaRepetidaError, RevisarPermisos, PermisoDenegadoError,
)

app = FastAPI(title="Productos API")


class CategoriaRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=255)


class CategoriaResponse(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str]


class ProductoRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=255)
    precio: float = Field(ge=0)
    stock: int = Field(default=0, ge=0)
    id_categoria: int
    # Foto del producto: una ruta de la carpeta img/ de la página (img/productos/bujia.jpg)
    # o una dirección https://. Así nadie puede meter "javascript:" ni otra cosa rara
    imagen: Optional[str] = Field(default=None, max_length=255,
                                  pattern=r"^(img/[A-Za-z0-9_./-]+\.(jpg|jpeg|png|webp)|https://[^\s\"'<>]+)$")


class ProductoResponse(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str]
    precio: float
    stock: int
    id_categoria: int
    categoria: str
    imagen: Optional[str]


def categorias_use_case() -> GestionarCategorias:
    return GestionarCategorias(categoria_repository=SQLServerCategoriaRepository())


def productos_use_case() -> GestionarProductos:
    return GestionarProductos(
        producto_repository=SQLServerProductoRepository(),
        categoria_repository=SQLServerCategoriaRepository(),
    )

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


def to_response(producto: Producto) -> ProductoResponse:
    return ProductoResponse(**vars(producto))


# ---------- Categorías ----------

@app.get("/api/categorias", response_model=List[CategoriaResponse])
def listar_categorias():
    return [CategoriaResponse(**vars(c)) for c in categorias_use_case().listar()]


@app.post("/api/categorias", response_model=CategoriaResponse, status_code=status.HTTP_201_CREATED)
def crear_categoria(request: CategoriaRequest, id_login: int = Depends(usuario_actual)):
    solo_administrador(id_login)
    try:
        categoria = categorias_use_case().crear(request.nombre, request.descripcion)
    except CategoriaRepetidaError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return CategoriaResponse(**vars(categoria))


@app.delete("/api/categorias/{id_categoria}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_categoria(id_categoria: int, id_login: int = Depends(usuario_actual)):
    solo_administrador(id_login)
    try:
        categorias_use_case().eliminar(id_categoria)
    except NoEncontradoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CategoriaEnUsoError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


# ---------- Productos ----------

@app.get("/api/productos", response_model=List[ProductoResponse])
def listar_productos(categoria: Optional[int] = None, buscar: Optional[str] = None):
    return [to_response(p) for p in productos_use_case().listar(categoria, buscar)]


@app.get("/api/productos/{id_producto}", response_model=ProductoResponse)
def obtener_producto(id_producto: int):
    try:
        return to_response(productos_use_case().obtener(id_producto))
    except NoEncontradoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@app.post("/api/productos", response_model=ProductoResponse, status_code=status.HTTP_201_CREATED)
def crear_producto(request: ProductoRequest, id_login: int = Depends(usuario_actual)):
    solo_administrador(id_login)
    try:
        return to_response(productos_use_case().crear(Producto(**request.model_dump())))
    except NoEncontradoError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.put("/api/productos/{id_producto}", response_model=ProductoResponse)
def actualizar_producto(id_producto: int, request: ProductoRequest, id_login: int = Depends(usuario_actual)):
    # El stock que venga aquí se ignora: solo cambia con las órdenes
    solo_administrador(id_login)
    try:
        producto = Producto(id_producto=id_producto, **request.model_dump())
        return to_response(productos_use_case().actualizar(producto))
    except NoEncontradoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@app.delete("/api/productos/{id_producto}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_producto(id_producto: int, id_login: int = Depends(usuario_actual)):
    solo_administrador(id_login)
    try:
        productos_use_case().eliminar(id_producto)
    except NoEncontradoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ProductoEnUsoError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

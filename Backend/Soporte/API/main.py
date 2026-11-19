import os
import sys
from datetime import datetime
from typing import List, Literal, Optional
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Infrastructure.repository import SQLServerSoporteRepository, SQLServerConversacionRepository
from Infrastructure.tokens import leer_token
from Domain.entities import Soporte, Conversacion
from Application.soporte_use_cases import (
    GestionarSoporte, GestionarConversaciones, NoEncontradoError, DatosInvalidosError,
    PermisoDenegadoError, ConflictoError,
)

# redirect_slashes=False: /api/login/ (con diagonal al final) da 404 en vez de
# redirigir a una dirección http:// interna
app = FastAPI(title="Soporte API", redirect_slashes=False)

class SoporteRequest(BaseModel):
    correo: Optional[str] = Field(default=None, max_length=100, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    telefono: Optional[str] = Field(default=None, max_length=20, pattern=r"^[0-9+\-\s()]{7,20}$")
    direccion: Optional[str] = Field(default=None, max_length=255)
    horario: Optional[str] = Field(default=None, max_length=100)

class SoporteResponse(BaseModel):
    id: int
    correo: Optional[str]
    telefono: Optional[str]
    direccion: Optional[str]
    horario: Optional[str]

def usuario_actual(authorization: Optional[str] = Header(default=None)) -> int:
    """El id_login de quien hace la petición, sacado del token. Sin token válido: 401."""
    if authorization and authorization.startswith("Bearer "):
        id_login = leer_token(authorization[len("Bearer "):])
        if id_login is not None:
            return id_login
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Tu sesión venció o no es válida. Inicia sesión de nuevo.",
                        headers={"WWW-Authenticate": "Bearer"})

def use_case() -> GestionarSoporte:
    return GestionarSoporte(soporte_repository=SQLServerSoporteRepository(),
                            usuario_repository=SQLServerConversacionRepository())

@app.get("/api/soporte", response_model=List[SoporteResponse])
def listar_soporte():
    return [SoporteResponse(**vars(s)) for s in use_case().listar()]

@app.get("/api/soporte/{id_soporte}", response_model=SoporteResponse)
def obtener_soporte(id_soporte: int):
    try:
        return SoporteResponse(**vars(use_case().obtener(id_soporte)))
    except NoEncontradoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@app.post("/api/soporte", response_model=SoporteResponse, status_code=status.HTTP_201_CREATED)
def crear_soporte(request: SoporteRequest, id_login: int = Depends(usuario_actual)):
    # id_login = quién hace el cambio (solo el Administrador)
    try:
        return SoporteResponse(**vars(use_case().crear(Soporte(**request.model_dump()), id_login)))
    except Exception as e:
        manejar_error(e)

@app.put("/api/soporte/{id_soporte}", response_model=SoporteResponse)
def actualizar_soporte(id_soporte: int, request: SoporteRequest, id_login: int = Depends(usuario_actual)):
    try:
        soporte = Soporte(id_soporte=id_soporte, **request.model_dump())
        return SoporteResponse(**vars(use_case().actualizar(soporte, id_login)))
    except Exception as e:
        manejar_error(e)

@app.delete("/api/soporte/{id_soporte}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_soporte(id_soporte: int, id_login: int = Depends(usuario_actual)):
    try:
        use_case().eliminar(id_soporte, id_login)
    except Exception as e:
        manejar_error(e)

# ===== Chat de soporte =====
EstadoConversacion = Literal["Abierta", "Cerrada"]

class NuevaConversacionRequest(BaseModel):
    asunto: str = Field(min_length=1, max_length=100)
    mensaje: str = Field(min_length=1, max_length=1000)

class MensajeRequest(BaseModel):
    texto: str = Field(min_length=1, max_length=1000)

class EstadoConversacionRequest(BaseModel):
    estado: EstadoConversacion

class MensajeResponse(BaseModel):
    id: int
    id_login: int
    autor: str
    rol: str
    texto: str
    fecha: datetime

class ResumenConversacionResponse(BaseModel):
    id: int
    id_login: int
    cliente: str
    asunto: str
    estado: str
    fecha: datetime
    esperando_respuesta: bool
    ultimo_mensaje: Optional[MensajeResponse]

class ConversacionResponse(ResumenConversacionResponse):
    mensajes: List[MensajeResponse]

def chat() -> GestionarConversaciones:
    return GestionarConversaciones(conversacion_repository=SQLServerConversacionRepository())

def to_response(c: Conversacion, con_mensajes: bool = True):
    datos = dict(id=c.id, id_login=c.id_login, cliente=c.cliente, asunto=c.asunto, estado=c.estado,
                 fecha=c.fecha, esperando_respuesta=c.esperando_respuesta,
                 ultimo_mensaje=MensajeResponse(**vars(c.ultimo_mensaje)) if c.ultimo_mensaje else None)
    if not con_mensajes:
        return ResumenConversacionResponse(**datos)
    return ConversacionResponse(**datos, mensajes=[MensajeResponse(**vars(m)) for m in c.mensajes])

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

@app.get("/api/conversaciones", response_model=List[ResumenConversacionResponse])
def listar_conversaciones(id_login: int = Depends(usuario_actual)):
    # id_login = quién consulta (sale del token). El Cliente recibe solo las suyas; el personal, todas
    try:
        return [to_response(c, con_mensajes=False) for c in chat().listar(id_login)]
    except Exception as e:
        manejar_error(e)

@app.get("/api/conversaciones/{id_conversacion}", response_model=ConversacionResponse)
def obtener_conversacion(id_conversacion: int, id_login: int = Depends(usuario_actual)):
    try:
        return to_response(chat().obtener(id_conversacion, id_login))
    except Exception as e:
        manejar_error(e)

@app.post("/api/conversaciones", response_model=ConversacionResponse, status_code=status.HTTP_201_CREATED)
def crear_conversacion(request: NuevaConversacionRequest, id_login: int = Depends(usuario_actual)):
    try:
        return to_response(chat().crear(id_login, request.asunto, request.mensaje))
    except Exception as e:
        manejar_error(e)

@app.post("/api/conversaciones/{id_conversacion}/mensajes", response_model=ConversacionResponse,
          status_code=status.HTTP_201_CREATED)
def responder_conversacion(id_conversacion: int, request: MensajeRequest, id_login: int = Depends(usuario_actual)):
    try:
        return to_response(chat().responder(id_conversacion, id_login, request.texto))
    except Exception as e:
        manejar_error(e)

@app.patch("/api/conversaciones/{id_conversacion}/estado", response_model=ConversacionResponse)
def cambiar_estado_conversacion(id_conversacion: int, request: EstadoConversacionRequest,
                                id_login: int = Depends(usuario_actual)):
    # Solo el personal cierra (o vuelve a abrir) una conversación
    try:
        return to_response(chat().cambiar_estado(id_conversacion, request.estado, id_login))
    except Exception as e:
        manejar_error(e)

@app.delete("/api/conversaciones/{id_conversacion}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_conversacion(id_conversacion: int, id_login: int = Depends(usuario_actual)):
    # Solo el Administrador; se borran también todos los mensajes
    try:
        chat().eliminar(id_conversacion, id_login)
    except Exception as e:
        manejar_error(e)
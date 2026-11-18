"""API: rutas HTTP del microservicio de Login (FastAPI).

Aquí se "arma" todo: se crean los adaptadores de Infraestructura y se le
pasan a los casos de uso. Las rutas solo traducen HTTP ↔ caso de uso.
"""
import sys
import os
from typing import Literal, Optional
from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Infrastructure.repository import SQLServerUserRepository
from Infrastructure.auth_services import BcryptPasswordHasher
from Infrastructure.tokens import crear_token, leer_token
from Application.login_use_case import (
    LoginUser, RegisterUser, DatosInvalidosError, ConflictoError, PermisoDenegadoError,
)

app = FastAPI(title="Login API")

Rol = Literal["Administrador", "Empleado", "Almacenista", "Cliente"]

class LoginRequest(BaseModel):
    username: str
    password: str

class RegistroRequest(BaseModel):
    username: str = Field(max_length=50)
    email: str = Field(max_length=100, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(max_length=100)
    rol: Rol = "Cliente"

def id_de_token(authorization: Optional[str]) -> Optional[int]:
    """Saca el id_login del encabezado 'Authorization: Bearer <token>' o None si no hay o no sirve."""
    if authorization and authorization.startswith("Bearer "):
        return leer_token(authorization[len("Bearer "):])
    return None

@app.post("/api/login")
def login(request: LoginRequest):
    use_case = LoginUser(
        user_repository=SQLServerUserRepository(),
        password_hasher=BcryptPasswordHasher(),
    )

    user = use_case.execute(request.username, request.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas")
    # id_login lo usa la página para registrar quién crea cada orden; rol, para saber qué puede hacer
    return {
        "message": "Login exitoso",
        "status": "success",
        "token": crear_token(user.id),
        "id_login": user.id,
        "username": user.username,
        "rol": user.rol,
    }

@app.post("/api/usuarios", status_code=status.HTTP_201_CREATED)
def registrar(request: RegistroRequest, authorization: Optional[str] = Header(default=None)):
    # Quién crea la cuenta sale del token (solo importa si el rol no es Cliente)
    id_creador = id_de_token(authorization)
    use_case = RegisterUser(
        user_repository=SQLServerUserRepository(),
        password_hasher=BcryptPasswordHasher(),
    )
    try:
        user = use_case.execute(request.username, request.email, request.password,
                                request.rol, id_creador)
    except DatosInvalidosError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermisoDenegadoError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ConflictoError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return {"id_login": user.id, "username": user.username, "email": user.email, "rol": user.rol}
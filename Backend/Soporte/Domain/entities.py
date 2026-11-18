from datetime import datetime
from typing import List, Optional

class Soporte:
    def __init__(self, correo: Optional[str] = None, telefono: Optional[str] = None, direccion: Optional[str] = None, id_soporte: int = None,
                 horario: Optional[str] = None):
        self.id = id_soporte
        self.correo = correo
        self.telefono = telefono
        self.direccion = direccion
        self.horario = horario

class Mensaje:
    def __init__(self, id_conversacion: Optional[int], id_login: int, texto: str,
                 fecha: Optional[datetime] = None, autor: Optional[str] = None,
                 rol: Optional[str] = None, id_mensaje: int = None):
        self.id = id_mensaje
        self.id_conversacion = id_conversacion
        self.id_login = id_login      # quién lo escribió
        self.autor = autor            # su nombre de usuario
        self.rol = rol                # su rol: así la página sabe si contestó el personal
        self.texto = texto
        self.fecha = fecha

class Conversacion:
    def __init__(self, id_login: int, asunto: str, estado: str = "Abierta",
                 fecha: Optional[datetime] = None, cliente: Optional[str] = None,
                 mensajes: Optional[List[Mensaje]] = None, id_conversacion: int = None):
        self.id = id_conversacion
        self.id_login = id_login      # el cliente que la empezó
        self.cliente = cliente        # su nombre de usuario
        self.asunto = asunto
        self.estado = estado
        self.fecha = fecha
        self.mensajes = mensajes or []

    @property
    def ultimo_mensaje(self) -> Optional[Mensaje]:
        return self.mensajes[-1] if self.mensajes else None

    @property
    def esperando_respuesta(self) -> bool:
        # Si lo último lo escribió el cliente, le toca contestar al personal
        return self.ultimo_mensaje is not None and self.ultimo_mensaje.id_login == self.id_login
"""Dominio: el usuario del sistema y sus roles."""

# Roles que existen en la refaccionaria
ROL_ADMINISTRADOR = "Administrador"   # puede todo y crea usuarios de cualquier rol
ROL_EMPLEADO = "Empleado"             # hace ventas y las avanza; no compras ni cancelar
ROL_ALMACENISTA = "Almacenista"       # registra compras (mercancía que entra) y las avanza
ROL_CLIENTE = "Cliente"               # solo hace pedidos y ve sus propias órdenes

ROLES = [ROL_ADMINISTRADOR, ROL_EMPLEADO, ROL_ALMACENISTA, ROL_CLIENTE]


class User:
    def __init__(self, username: str, password_hash: str, id_user: int = None,
                 rol: str = ROL_CLIENTE, email: str = None):
        self.id = id_user
        self.username = username
        self.password_hash = password_hash
        self.rol = rol
        self.email = email

    @property
    def es_administrador(self) -> bool:
        return self.rol == ROL_ADMINISTRADOR

    @property
    def es_cliente(self) -> bool:
        return self.rol == ROL_CLIENTE
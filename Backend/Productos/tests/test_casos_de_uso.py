"""Pruebas de los casos de uso de Productos y Categorías, sin base de datos."""
import unittest

from Domain.entities import Categoria, Producto
from Application.producto_use_cases import (
    CategoriaRepository, ProductoRepository, GestionarCategorias, GestionarProductos, NoEncontradoError,
    CategoriaEnUsoError, CategoriaRepetidaError, UsuarioRepository, RevisarPermisos, PermisoDenegadoError
)

class CategoriasFalsas(CategoriaRepository):
    def __init__(self):
        self.datos = {1: Categoria(nombre="Frenos", id_categoria=1)}

    def find_all(self):
        return list(self.datos.values())

    def find_by_id(self, id_categoria):
        return self.datos.get(id_categoria)

    def save(self, categoria):
        if any(c.nombre == categoria.nombre for c in self.datos.values()):
            raise CategoriaRepetidaError(f"Ya existe la categoría '{categoria.nombre}'")
        categoria.id = max(self.datos) + 1
        self.datos[categoria.id] = categoria
        return categoria

    def contar_productos(self, id_categoria):
        # La categoría 1 (Frenos) tiene las Balatas de ProductosFalsos
        return 1 if id_categoria == 1 else 0

    def delete(self, id_categoria):
        return self.datos.pop(id_categoria, None) is not None

class ProductosFalsos(ProductoRepository):
    def __init__(self):
        self.datos = {1: Producto(nombre="Balatas", precio=650, stock=20, id_categoria=1, id_producto=1)}
        self.ultimo_filtro = None

    def find_all(self, id_categoria=None, buscar=None):
        self.ultimo_filtro = (id_categoria, buscar)
        return list(self.datos.values())

    def find_by_id(self, id_producto):
        return self.datos.get(id_producto)

    def save(self, producto):
        producto.id = max(self.datos) + 1
        self.datos[producto.id] = producto
        return producto

    def update(self, producto):
        if producto.id not in self.datos:
            return False
        self.datos[producto.id] = producto
        return True

    def delete(self, id_producto):
        return self.datos.pop(id_producto, None) is not None

class PruebasProductos(unittest.TestCase):
    def setUp(self):
        self.productos = ProductosFalsos()
        self.categorias = CategoriasFalsas()
        self.casos = GestionarProductos(producto_repository=self.productos, categoria_repository=self.categorias)

    def test_listar_pasa_los_filtros_al_repositorio(self):
        self.casos.listar(1, "bal")
        self.assertEqual(self.productos.ultimo_filtro, (1, "bal"))

    def test_obtener_un_producto_que_no_existe_lanza_error(self):
        with self.assertRaises(NoEncontradoError):
            self.casos.obtener(999)

    def test_crear_producto_con_categoria_valida(self):
        nuevo = self.casos.crear(Producto(nombre="Disco", precio=890, stock=10, id_categoria=1))
        self.assertEqual(nuevo.id, 2)

    def test_no_crea_producto_si_la_categoria_no_existe(self):
        with self.assertRaises(NoEncontradoError):
            self.casos.crear(Producto(nombre="X", precio=1, stock=1, id_categoria=999))
        self.assertEqual(len(self.productos.datos), 1)

    def test_actualizar_producto_que_no_existe_lanza_error(self):
        with self.assertRaises(NoEncontradoError):
            self.casos.actualizar(Producto(nombre="X", precio=1, stock=1, id_categoria=1, id_producto=999))

    def test_editar_producto_no_cambia_el_stock(self):
        editado = self.casos.actualizar(Producto(nombre="Balatas cerámicas", precio=700, stock=999,
                                                 id_categoria=1, id_producto=1))
        self.assertEqual((editado.nombre, editado.precio, editado.stock), ("Balatas cerámicas", 700, 20))

    def test_eliminar_producto_que_no_existe_lanza_error(self):
        with self.assertRaises(NoEncontradoError):
            self.casos.eliminar(999)

    def test_crear_categoria(self):
        categoria = GestionarCategorias(categoria_repository=self.categorias).crear("Filtros", None)
        self.assertEqual(categoria.id, 2)

    def test_no_se_repite_el_nombre_de_una_categoria(self):
        with self.assertRaises(CategoriaRepetidaError):
            GestionarCategorias(categoria_repository=self.categorias).crear(" Frenos ", None)

    def test_eliminar_categoria_vacia(self):
        casos = GestionarCategorias(categoria_repository=self.categorias)
        nueva = casos.crear("Filtros", None)
        casos.eliminar(nueva.id)
        self.assertNotIn(nueva.id, self.categorias.datos)

    def test_no_elimina_categoria_con_productos(self):
        with self.assertRaises(CategoriaEnUsoError) as error:
            GestionarCategorias(categoria_repository=self.categorias).eliminar(1)
        self.assertIn("tiene 1 producto:", str(error.exception))
        self.assertIn(1, self.categorias.datos)   # sigue ahí

    def test_eliminar_categoria_que_no_existe_lanza_error(self):
        with self.assertRaises(NoEncontradoError):
            GestionarCategorias(categoria_repository=self.categorias).eliminar(999)

class UsuariosFalsos(UsuarioRepository):
    ROLES = {1: "Administrador", 2: "Empleado", 3: "Almacenista", 4: "Cliente"}

    def rol_de_usuario(self, id_login):
        return self.ROLES.get(id_login)

class PruebasPermisos(unittest.TestCase):
    def setUp(self):
        self.permisos = RevisarPermisos(usuario_repository=UsuariosFalsos())

    def test_el_administrador_puede_hacer_cambios(self):
        self.permisos.solo_administrador(1)   # no lanza error

    def test_los_demas_roles_no_pueden(self):
        for id_login in (2, 3, 4):
            with self.assertRaises(PermisoDenegadoError):
                self.permisos.solo_administrador(id_login)

    def test_usuario_que_no_existe(self):
        with self.assertRaises(PermisoDenegadoError):
            self.permisos.solo_administrador(999)     

if __name__ == "__main__":
    unittest.main()

"""Prueba de punta a punta: Gateway (Go) → microservicios (Python) → SQL Server.

Necesita que el sistema esté corriendo (./iniciar.sh). Todo lo que crea lo
borra al final, así que no deja basura en la base de datos.

Cada usuario de prueba inicia sesión y usa su token (encabezado
"Authorization: Bearer <token>"), igual que la página.

    python pruebas/prueba_api.py
"""
import base64
import json
import unittest
import urllib.error
import urllib.request
from datetime import date, timedelta

GATEWAY = "http://127.0.0.1:8080"

# Usuarios de prueba (BD/02_datos_ejemplo.sql y BD/04_agregar_roles.sql)
USUARIOS = {"admin": "Admin123", "empleado": "Empleado123", "almacen": "Almacen123", "cliente": "Cliente123"}
_sesiones = {}


def pedir(metodo, ruta, cuerpo=None, token=None):
    """Hace la petición al Gateway (con el token, si se da) y regresa (código HTTP, JSON o texto)."""
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    encabezados = {"Content-Type": "application/json"}
    if token:
        encabezados["Authorization"] = "Bearer " + token
    peticion = urllib.request.Request(GATEWAY + ruta, data=datos, method=metodo, headers=encabezados)
    try:
        with urllib.request.urlopen(peticion, timeout=10) as respuesta:
            texto = respuesta.read().decode()
            codigo = respuesta.status
    except urllib.error.HTTPError as error:
        texto = error.read().decode()
        codigo = error.code
    try:
        return codigo, json.loads(texto) if texto else None
    except json.JSONDecodeError:
        return codigo, texto


def sesion(usuario):
    """Inicia sesión una sola vez por usuario y regresa lo que contesta el login (token, id_login, rol)."""
    if usuario not in _sesiones:
        codigo, datos = pedir("POST", "/api/login", {"username": usuario, "password": USUARIOS[usuario]})
        if codigo != 200:
            raise unittest.SkipTest(f"No se pudo entrar como {usuario}: corre BD/04_agregar_roles.sql")
        _sesiones[usuario] = datos
    return _sesiones[usuario]


def token(usuario="admin"):
    return sesion(usuario)["token"]


def setUpModule():
    try:
        urllib.request.urlopen(GATEWAY + "/", timeout=3)
    except Exception:
        raise unittest.SkipTest("El Gateway no responde en " + GATEWAY + ". Corre ./iniciar.sh primero.")


class PruebaGateway(unittest.TestCase):
    def test_los_cinco_microservicios_estan_encendidos(self):
        codigo, pagina = pedir("GET", "/")
        self.assertEqual(codigo, 200)
        self.assertEqual(pagina.count("✅ encendido"), 5, "Algún microservicio de Python está apagado")

    def test_ruta_que_no_existe(self):
        self.assertEqual(pedir("GET", "/api/no-existe")[0], 404)


class PruebaLogin(unittest.TestCase):
    def test_contrasena_incorrecta(self):
        self.assertEqual(pedir("POST", "/api/login", {"username": "admin", "password": "mala"}), (401, {"detail": "Credenciales invalidas"}))

    def test_faltan_datos(self):
        self.assertEqual(pedir("POST", "/api/login", {"username": "admin"})[0], 422)

    def test_el_login_regresa_un_token(self):
        datos = sesion("admin")
        self.assertEqual(datos["token"].count("."), 1)   # "carga.firma"


class PruebaTokens(unittest.TestCase):
    """El servidor ya no le cree al id_login que mande la página: solo al token."""

    def test_sin_token_o_con_token_falso_no_se_entra(self):
        self.assertEqual(pedir("GET", "/api/ordenes")[0], 401)
        self.assertEqual(pedir("GET", "/api/ordenes", token="no.sirve")[0], 401)
        self.assertEqual(pedir("GET", "/api/ordenes", token="basura")[0], 401)

    def test_el_id_login_de_la_url_ya_no_sirve(self):
        id_admin = sesion("admin")["id_login"]
        self.assertEqual(pedir("POST", f"/api/categorias?id_login={id_admin}", {"nombre": "X"})[0], 401)
        self.assertEqual(pedir("GET", f"/api/inventario/movimientos?id_login={id_admin}")[0], 401)

    def test_un_token_alterado_se_rechaza(self):
        # Se toma el token del cliente y se le cambia el id por el del admin: la firma ya no coincide
        carga, firma = token("cliente").split(".")
        falsa = base64.urlsafe_b64encode(json.dumps({"id": sesion("admin")["id_login"], "vence": 9999999999}).encode()).rstrip(b"=").decode()
        self.assertEqual(pedir("GET", "/api/inventario/movimientos", token=f"{falsa}.{firma}")[0], 401)


class PruebaProductos(unittest.TestCase):
    def test_listar_y_filtrar(self):
        codigo, categorias = pedir("GET", "/api/categorias")
        self.assertEqual(codigo, 200)
        self.assertTrue(categorias, "No hay categorías en la base de datos")
        codigo, productos = pedir("GET", f"/api/productos?categoria={categorias[0]['id']}")
        self.assertEqual(codigo, 200)
        self.assertTrue(all(p["id_categoria"] == categorias[0]["id"] for p in productos))

    def test_errores(self):
        self.assertEqual(pedir("GET", "/api/productos/999999")[0], 404)
        self.assertEqual(pedir("POST", "/api/productos", {"nombre": "X", "precio": -1, "id_categoria": 1}, token())[0], 422)
        self.assertEqual(pedir("POST", "/api/productos", {"nombre": "X", "precio": 5, "id_categoria": 999999}, token())[0], 400)

    def test_crear_editar_y_borrar(self):
        id_categoria = pedir("GET", "/api/categorias")[1][0]["id"]
        codigo, nuevo = pedir("POST", "/api/productos", {"nombre": "PRUEBA AUTOMATICA", "precio": 99.5, "stock": 3, "id_categoria": id_categoria}, token())
        self.assertEqual(codigo, 201)
        try:
            self.assertIsNone(nuevo["imagen"])
            codigo, editado = pedir("PUT", f"/api/productos/{nuevo['id']}", {"nombre": "PRUEBA AUTOMATICA 2", "precio": 120, "stock": 5, "id_categoria": id_categoria, "imagen": "img/productos/bujia.jpg"}, token())
            self.assertEqual((codigo, editado["precio"], editado["stock"], editado["imagen"]), (200, 120, 3, "img/productos/bujia.jpg"))
            # La foto solo puede ser una ruta de img/ o una dirección https://
            malo = {"nombre": "X", "precio": 1, "id_categoria": id_categoria, "imagen": "javascript:alert(1)"}
            self.assertEqual(pedir("PUT", f"/api/productos/{nuevo['id']}", malo, token())[0], 422)
            self.assertEqual(pedir("GET", f"/api/productos/{nuevo['id']}")[1]["nombre"], "PRUEBA AUTOMATICA 2")
        finally:
            self.assertEqual(pedir("DELETE", f"/api/productos/{nuevo['id']}", token=token())[0], 204)
        self.assertEqual(pedir("DELETE", f"/api/productos/{nuevo['id']}", token=token())[0], 404)


class PruebaCategorias(unittest.TestCase):
    def test_crear_y_eliminar_categoria(self):
        codigo, nueva = pedir("POST", "/api/categorias", {"nombre": "PRUEBA AUTOMATICA"}, token())
        self.assertEqual(codigo, 201)
        try:
            self.assertEqual(pedir("POST", "/api/categorias", {"nombre": "PRUEBA AUTOMATICA"}, token())[0], 409)   # repetida
        finally:
            self.assertEqual(pedir("DELETE", f"/api/categorias/{nueva['id']}", token=token())[0], 204)
        self.assertEqual(pedir("DELETE", f"/api/categorias/{nueva['id']}", token=token())[0], 404)

    def test_no_se_elimina_una_categoria_con_productos(self):
        id_categoria = pedir("GET", "/api/productos")[1][0]["id_categoria"]
        codigo, respuesta = pedir("DELETE", f"/api/categorias/{id_categoria}", token=token())
        self.assertEqual(codigo, 409)
        self.assertIn("producto", respuesta["detail"])   # "1 producto" o "2 productos"


class PruebaPromociones(unittest.TestCase):
    def test_promocion_vigente_aparece_en_el_dashboard_con_descuento(self):
        producto = pedir("GET", "/api/productos")[1][0]
        hoy = date.today()
        codigo, promo = pedir("POST", "/api/promociones", {
            "nombre": "PRUEBA AUTOMATICA", "descuento": 10,
            "fecha_inicio": f"{hoy}T00:00:00", "fecha_fin": f"{hoy + timedelta(days=2)}T23:59:59",
        }, token())
        self.assertEqual(codigo, 201)
        try:
            self.assertEqual(pedir("POST", f"/api/promociones/{promo['id']}/productos", {"id_producto": producto["id"]}, token())[0], 200)
            self.assertEqual(pedir("POST", f"/api/promociones/{promo['id']}/productos", {"id_producto": producto["id"]}, token())[0], 409)

            dashboard = pedir("GET", "/api/dashboard")[1]
            mia = next((p for p in dashboard if p["id"] == promo["id"]), None)
            self.assertIsNotNone(mia, "La promoción vigente no apareció en el dashboard")
            self.assertEqual(mia["productos"][0]["precio_con_descuento"], round(producto["precio"] * 0.9, 2))
        finally:
            self.assertEqual(pedir("DELETE", f"/api/promociones/{promo['id']}", token=token())[0], 204)

    def test_crear_con_productos_de_una_vez(self):
        ids = [p["id"] for p in pedir("GET", "/api/productos")[1][:2]]
        hoy = date.today()
        datos = {"nombre": "PRUEBA AUTOMATICA", "descuento": 20, "productos": ids,
                 "fecha_inicio": f"{hoy}T00:00:00", "fecha_fin": f"{hoy + timedelta(days=5)}T23:59:59"}
        codigo, promo = pedir("POST", "/api/promociones", datos, token())
        self.assertEqual(codigo, 201)
        try:
            self.assertEqual(sorted(p["id"] for p in promo["productos"]), sorted(ids))
        finally:
            self.assertEqual(pedir("DELETE", f"/api/promociones/{promo['id']}", token=token())[0], 204)

    def test_no_crea_promocion_vencida_ni_con_producto_que_no_existe(self):
        antes = len(pedir("GET", "/api/promociones")[1])
        ayer = date.today() - timedelta(days=1)
        vencida = {"nombre": "X", "descuento": 5, "fecha_inicio": f"{ayer - timedelta(days=5)}T00:00:00", "fecha_fin": f"{ayer}T23:59:59"}
        self.assertEqual(pedir("POST", "/api/promociones", vencida, token())[0], 400)
        hoy = date.today()
        sin_producto = {"nombre": "X", "descuento": 5, "productos": [999999],
                        "fecha_inicio": f"{hoy}T00:00:00", "fecha_fin": f"{hoy}T23:59:59"}
        self.assertEqual(pedir("POST", "/api/promociones", sin_producto, token())[0], 404)
        self.assertEqual(len(pedir("GET", "/api/promociones")[1]), antes)   # no se creó nada

    def test_fechas_al_reves(self):
        codigo, _ = pedir("POST", "/api/promociones", {"nombre": "X", "descuento": 5,
                                                      "fecha_inicio": "2026-12-01T00:00:00", "fecha_fin": "2026-10-01T00:00:00"}, token())
        ayer = date.today() - timedelta(days=1)
        empieza_ayer = {"nombre": "X", "descuento": 5, "fecha_inicio": f"{ayer}T00:00:00", "fecha_fin": f"{ayer + timedelta(days=5)}T23:59:59"}
        self.assertEqual(codigo, 400)
        self.assertEqual(pedir("POST", "/api/promociones", empieza_ayer, token())[0], 400)   # no empieza en un día pasado


class PruebaPermisosCatalogo(unittest.TestCase):
    """Solo el Administrador cambia productos, categorías y promociones."""

    def test_los_demas_roles_no_hacen_cambios(self):
        hoy = date.today()
        promo = {"nombre": "X", "descuento": 5, "fecha_inicio": f"{hoy}T00:00:00", "fecha_fin": f"{hoy}T23:59:59"}
        for usuario in ["empleado", "almacen", "cliente"]:
            self.assertEqual(pedir("POST", "/api/productos", {"nombre": "X", "precio": 1, "id_categoria": 1}, token(usuario))[0], 403)
            self.assertEqual(pedir("POST", "/api/categorias", {"nombre": "X"}, token(usuario))[0], 403)
            self.assertEqual(pedir("POST", "/api/promociones", promo, token(usuario))[0], 403)

    def test_sin_sesion_no_se_hacen_cambios(self):
        self.assertEqual(pedir("POST", "/api/categorias", {"nombre": "X"})[0], 401)
        self.assertEqual(pedir("POST", "/api/categorias?id_login=1", {"nombre": "X"})[0], 401)   # el truco de antes

    def test_editar_promocion_con_sus_productos(self):
        ids = [p["id"] for p in pedir("GET", "/api/productos")[1][:2]]
        hoy = date.today()
        datos = {"nombre": "PRUEBA AUTOMATICA", "descuento": 10, "productos": ids[:1],
                 "fecha_inicio": f"{hoy}T00:00:00", "fecha_fin": f"{hoy + timedelta(days=3)}T23:59:59"}
        codigo, promo = pedir("POST", "/api/promociones", datos, token())
        self.assertEqual(codigo, 201)
        try:
            datos.update(descuento=25, productos=ids[1:2])
            codigo, editada = pedir("PUT", f"/api/promociones/{promo['id']}", datos, token())
            self.assertEqual(codigo, 200)
            self.assertEqual((editada["descuento"], [p["id"] for p in editada["productos"]]), (25, ids[1:2]))
        finally:
            self.assertEqual(pedir("DELETE", f"/api/promociones/{promo['id']}", token=token())[0], 204)


class PruebaOrdenes(unittest.TestCase):
    def test_listar_y_filtrar(self):
        codigo, ventas = pedir("GET", "/api/ordenes?tipo=Venta", token=token())
        self.assertEqual(codigo, 200)
        self.assertTrue(all(o["tipo"] == "Venta" for o in ventas))
        for orden in ventas:
            self.assertAlmostEqual(orden["total"], sum(d["subtotal"] for d in orden["detalles"]), places=2)

    def test_errores(self):
        self.assertEqual(pedir("GET", "/api/ordenes/999999", token=token())[0], 404)
        self.assertEqual(pedir("GET", "/api/ordenes?tipo=Regalo", token=token())[0], 422)
        # Sin sesión no se ve nada
        self.assertEqual(pedir("GET", "/api/ordenes")[0], 401)
        self.assertEqual(pedir("GET", "/api/ordenes/1")[0], 401)
        self.assertEqual(pedir("GET", "/api/inventario/movimientos")[0], 401)
        self.assertEqual(pedir("POST", "/api/ordenes", {"tipo": "Venta", "productos": [{"id_producto": 1, "cantidad": 1}]})[0], 401)
        self.assertEqual(pedir("PATCH", "/api/ordenes/999999/estado", {"estado": "Completada"})[0], 401)
        # Con sesión, los datos se siguen revisando
        self.assertEqual(pedir("POST", "/api/ordenes", {"tipo": "Venta", "productos": []}, token())[0], 422)
        self.assertEqual(pedir("POST", "/api/ordenes", {"tipo": "Venta", "productos": [{"id_producto": 999999, "cantidad": 1}]}, token())[0], 404)
        repetido = {"tipo": "Venta", "productos": [{"id_producto": 1, "cantidad": 1}, {"id_producto": 1, "cantidad": 2}]}
        self.assertEqual(pedir("POST", "/api/ordenes", repetido, token())[0], 400)
        self.assertEqual(pedir("PATCH", "/api/ordenes/999999/estado", {"estado": "Completada"}, token())[0], 404)

    def test_movimientos_de_inventario(self):
        codigo, movimientos = pedir("GET", "/api/inventario/movimientos", token=token())
        self.assertEqual(codigo, 200)
        self.assertTrue(all(m["tipo"] in ("Entrada", "Salida") for m in movimientos))


class PruebaRoles(unittest.TestCase):
    """No crea órdenes ni usuarios: solo revisa que se nieguen las acciones sin permiso."""

    def test_el_login_regresa_el_rol(self):
        self.assertEqual(sesion("admin")["rol"], "Administrador")
        self.assertEqual(sesion("empleado")["rol"], "Empleado")
        self.assertEqual(sesion("almacen")["rol"], "Almacenista")
        self.assertEqual(sesion("cliente")["rol"], "Cliente")

    def test_empleado_no_puede_registrar_compras(self):
        compra = {"tipo": "Compra", "productos": [{"id_producto": 1, "cantidad": 1, "precio_unitario": 1}]}
        codigo, respuesta = pedir("POST", "/api/ordenes", compra, token("empleado"))
        self.assertEqual(codigo, 403)
        self.assertIn("Administrador", respuesta["detail"])

    def test_el_id_login_del_cuerpo_no_cambia_quien_eres(self):
        # Un empleado manda el id del admin dentro de la orden: se ignora y sigue siendo empleado
        compra = {"id_login": sesion("admin")["id_login"], "tipo": "Compra",
                  "productos": [{"id_producto": 1, "cantidad": 1, "precio_unitario": 1}]}
        self.assertEqual(pedir("POST", "/api/ordenes", compra, token("empleado"))[0], 403)

    def test_empleado_no_puede_cancelar(self):
        abiertas = [o for o in pedir("GET", "/api/ordenes", token=token())[1] if o["estado"] in ("Pendiente", "En Proceso")]
        if not abiertas:
            self.skipTest("No hay órdenes pendientes para intentar cancelar")
        orden = abiertas[0]
        codigo, _ = pedir("PATCH", f"/api/ordenes/{orden['id']}/estado", {"estado": "Cancelada"}, token("empleado"))
        self.assertEqual(codigo, 403)
        self.assertEqual(pedir("GET", f"/api/ordenes/{orden['id']}", token=token())[1]["estado"], orden["estado"])   # no cambió

    def test_almacenista_no_puede_registrar_ventas(self):
        venta = {"tipo": "Venta", "productos": [{"id_producto": 1, "cantidad": 1}]}
        self.assertEqual(pedir("POST", "/api/ordenes", venta, token("almacen"))[0], 403)

    def test_cliente_solo_ve_sus_ordenes(self):
        codigo, ordenes = pedir("GET", "/api/ordenes", token=token("cliente"))
        self.assertEqual(codigo, 200)
        self.assertTrue(all(o["id_login"] == sesion("cliente")["id_login"] for o in ordenes))

    def test_cliente_no_puede_ver_ordenes_de_otros_ni_el_inventario(self):
        self.assertEqual(pedir("GET", "/api/inventario/movimientos", token=token("cliente"))[0], 403)
        ajenas = [o for o in pedir("GET", "/api/ordenes", token=token())[1] if o["id_login"] != sesion("cliente")["id_login"]]
        if not ajenas:
            self.skipTest("No hay órdenes de otros usuarios")
        self.assertEqual(pedir("GET", f"/api/ordenes/{ajenas[0]['id']}", token=token("cliente"))[0], 403)

    def test_cliente_no_puede_comprar_ni_cambiar_estados(self):
        compra = {"tipo": "Compra", "productos": [{"id_producto": 1, "cantidad": 1, "precio_unitario": 1}]}
        self.assertEqual(pedir("POST", "/api/ordenes", compra, token("cliente"))[0], 403)
        abiertas = [o for o in pedir("GET", "/api/ordenes", token=token())[1] if o["estado"] in ("Pendiente", "En Proceso")]
        if not abiertas:
            self.skipTest("No hay órdenes pendientes para intentar avanzar")
        orden = abiertas[0]
        nuevo_estado = "En Proceso" if orden["estado"] == "Pendiente" else "Completada"
        codigo, _ = pedir("PATCH", f"/api/ordenes/{orden['id']}/estado", {"estado": nuevo_estado}, token("cliente"))
        self.assertEqual(codigo, 403)
        self.assertEqual(pedir("GET", f"/api/ordenes/{orden['id']}", token=token())[1]["estado"], orden["estado"])   # no cambió


class PruebaRegistro(unittest.TestCase):
    """Solo prueba los casos que se rechazan, para no dejar usuarios de prueba en la base."""

    def test_sin_ser_administrador_no_se_crea_personal(self):
        nuevo = {"username": "intruso", "email": "intruso@prueba.com", "password": "secreta123", "rol": "Administrador"}
        codigo, respuesta = pedir("POST", "/api/usuarios", nuevo)
        self.assertEqual(codigo, 403)
        self.assertIn("Administrador", respuesta["detail"])
        self.assertEqual(pedir("POST", "/api/usuarios", nuevo, token("empleado"))[0], 403)
        # El truco de antes: decir que lo crea el admin, sin su token
        self.assertEqual(pedir("POST", "/api/usuarios", {**nuevo, "id_creador": sesion("admin")["id_login"]})[0], 403)

    def test_usuario_repetido_y_datos_invalidos(self):
        self.assertEqual(pedir("POST", "/api/usuarios", {"username": "admin", "email": "otro@prueba.com", "password": "secreta123"})[0], 409)
        self.assertEqual(pedir("POST", "/api/usuarios", {"username": "nuevo", "email": "no-es-correo", "password": "secreta123"})[0], 422)
        self.assertEqual(pedir("POST", "/api/usuarios", {"username": "nuevo", "email": "n@prueba.com", "password": "123"})[0], 400)
        self.assertEqual(pedir("POST", "/api/usuarios", {"username": "nuevo", "email": "n@prueba.com", "password": "secreta123", "rol": "Jefe"})[0], 422)


class PruebaSoporte(unittest.TestCase):
    def test_crear_editar_y_borrar_con_horario(self):
        codigo, nuevo = pedir("POST", "/api/soporte", {"correo": "prueba@automatica.com", "horario": "Lunes a viernes"}, token())
        self.assertEqual(codigo, 201)
        try:
            self.assertEqual(nuevo["horario"], "Lunes a viernes")
            codigo, editado = pedir("PUT", f"/api/soporte/{nuevo['id']}", {"telefono": "55 0000 0000", "horario": "Sábados"}, token())
            self.assertEqual((codigo, editado["telefono"], editado["horario"]), (200, "55 0000 0000", "Sábados"))
        finally:
            self.assertEqual(pedir("DELETE", f"/api/soporte/{nuevo['id']}", token=token())[0], 204)

    def test_validaciones(self):
        self.assertEqual(pedir("POST", "/api/soporte", {}, token())[0], 400)
        self.assertEqual(pedir("POST", "/api/soporte", {"correo": "no-es-correo"}, token())[0], 422)
        self.assertEqual(pedir("POST", "/api/soporte", {"correo": "a@b.com"})[0], 401)   # sin sesión
        self.assertEqual(pedir("GET", "/api/soporte/999999")[0], 404)


class PruebaChat(unittest.TestCase):
    """Chat de soporte: el cliente escribe y el personal contesta. Al final se borra la conversación."""

    def test_conversacion_completa(self):
        codigo, conversacion = pedir("POST", "/api/conversaciones",
                                     {"asunto": "PRUEBA AUTOMATICA", "mensaje": "¿Tienen balatas?"}, token("cliente"))
        self.assertEqual(codigo, 201)
        ruta = f"/api/conversaciones/{conversacion['id']}"
        try:
            self.assertTrue(conversacion["esperando_respuesta"])
            self.assertEqual(conversacion["id_login"], sesion("cliente")["id_login"])   # quedó a nombre del cliente
            # El empleado la ve en su lista y contesta
            self.assertIn(conversacion["id"], [c["id"] for c in pedir("GET", "/api/conversaciones", token=token("empleado"))[1]])
            codigo, conversacion = pedir("POST", ruta + "/mensajes", {"texto": "Sí, hay 20"}, token("empleado"))
            self.assertEqual(codigo, 201)
            self.assertEqual([m["rol"] for m in conversacion["mensajes"]], ["Cliente", "Empleado"])
            self.assertFalse(conversacion["esperando_respuesta"])
            # El almacenista no atiende el chat y el cliente no puede cerrarla
            self.assertEqual(pedir("POST", ruta + "/mensajes", {"texto": "Hola"}, token("almacen"))[0], 403)
            self.assertEqual(pedir("PATCH", ruta + "/estado", {"estado": "Cerrada"}, token("cliente"))[0], 403)
            # El administrador la cierra y ya nadie escribe
            self.assertEqual(pedir("PATCH", ruta + "/estado", {"estado": "Cerrada"}, token())[1]["estado"], "Cerrada")
            self.assertEqual(pedir("POST", ruta + "/mensajes", {"texto": "¿Sigues ahí?"}, token("cliente"))[0], 409)
            self.assertEqual(pedir("GET", ruta, token=token("cliente"))[1]["mensajes"][-1]["texto"], "Sí, hay 20")
        finally:
            self.assertEqual(pedir("DELETE", ruta, token=token("empleado"))[0], 403)   # solo el Administrador
            self.assertEqual(pedir("DELETE", ruta, token=token())[0], 204)
        self.assertEqual(pedir("GET", ruta, token=token())[0], 404)

    def test_errores(self):
        self.assertEqual(pedir("POST", "/api/conversaciones", {"asunto": "X", "mensaje": "Hola"}, token())[0], 403)   # el admin no abre chats
        self.assertEqual(pedir("POST", "/api/conversaciones", {"asunto": "X", "mensaje": ""}, token("cliente"))[0], 422)
        self.assertEqual(pedir("POST", "/api/conversaciones", {"asunto": "X", "mensaje": "   "}, token("cliente"))[0], 400)
        self.assertEqual(pedir("GET", "/api/conversaciones")[0], 401)   # sin sesión
        self.assertEqual(pedir("GET", "/api/conversaciones/999999", token=token())[0], 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)

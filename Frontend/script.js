// ===== Conexión con el Gateway en Go =====
// La página le pide los datos al Gateway (Go, puerto 8080)
// y el Gateway se los pide a los microservicios de Python.
// Publicada (o abierta desde el Gateway) usa "/api" de la misma dirección.
// Abierta como archivo (doble clic en index.html) sigue usando el Gateway de tu computadora.
const API = location.protocol === "file:" ? "http://127.0.0.1:8080/api" : "/api";
const SIN_CONEXION = "Revisa que esté corriendo iniciar.sh (los microservicios de Python y el Gateway en Go).";

// Aquí se guardan los datos que llegan de la base de datos
let categorias = [];
let productos = [];
let promociones = [];

// pedirAPI hace la petición y regresa el JSON. Si algo sale mal, lanza un error
// con el mensaje "detail" que mandó Python (o uno de "no hay conexión").
async function pedirAPI(ruta, opciones = {}) {
    // Con sesión iniciada, cada petición lleva el token: así el servidor sabe quién eres
    const encabezados = { "Content-Type": "application/json" };
    const token = leerToken();
    if (token) encabezados["Authorization"] = "Bearer " + token;

    let respuesta;
    try {
        respuesta = await fetch(API + ruta, { ...opciones, headers: encabezados });
    } catch (e) {
        throw new Error(SIN_CONEXION);
    }
    // Si el servidor truena (error 500 en texto, no JSON), no se rompe la lectura
    let datos = null;
    if (respuesta.status !== 204) {
        try { datos = await respuesta.json(); } catch (e) { datos = null; }
    }
    if (!respuesta.ok) {
        // Token vencido o no válido: se cierra la sesión para que vuelva a entrar
        if (respuesta.status === 401 && token) {
            guardarUsuario(null);
            pintarSesion();   // el botón vuelve a decir "Entrar"
        }
        // FastAPI manda "detail" como texto, o como lista cuando falla la validación de datos
        const detalle = datos && datos.detail;
        // (los textos de esa lista vienen en inglés: se cambia por un aviso en español)
        const mensaje = Array.isArray(detalle) ? "Hay datos que no son válidos. Revisa lo que escribiste." : detalle;
        const error = new Error(mensaje || "Error " + respuesta.status);
        error.estado = respuesta.status;
        throw error;
    }
    return datos;
}
// Muestra un cuadro de error dentro de un contenedor
function mostrarError(contenedor, mensaje) {
    contenedor.innerHTML = `<div class="vacio"><h2>No se pudieron cargar los datos</h2><p>${escapar(mensaje)}</p></div>`;
}

// ===== Funciones de ayuda =====
const formatoPrecio = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" });

function dinero(cantidad) {
    return formatoPrecio.format(cantidad);
}

// Los textos que vienen de la base de datos se "escapan" antes de meterlos al HTML
// (así un nombre con < o > no rompe la página). Las comillas también se cambian,
// porque el texto a veces va dentro de un atributo: aria-label="...", href="..."
function escapar(texto) {
    const div = document.createElement("div");
    div.textContent = texto ?? "";
    return div.innerHTML.replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// La promoción vigente en la que está un producto (o undefined).
// Si está en varias, la de mayor descuento: es la que cobra el microservicio de Órdenes
function promocionDe(idProducto) {
    return promociones
        .filter(promo => promo.productos.some(p => p.id === idProducto))
        .sort((a, b) => b.descuento - a.descuento)[0];
}

function conDescuento(precio, descuento) {
    return Math.round(precio * (1 - descuento / 100) * 100) / 100;
}

function fechaCorta(texto) {
    // "2026-10-31T23:59:59" → "31 oct"
    return new Date(texto.slice(0, 10) + "T00:00:00").toLocaleDateString("es-MX", { day: "numeric", month: "short" });
}

// "12 en existencia", "Últimas 3" o "Agotado", con su color
function existenciaDe(stock) {
    if(stock === 0) return `<span class="existencia agotado">Agotado</span>`;
    if(stock <= 8) return `<span class="existencia pocas">Últimas ${stock}</span>`;
    return `<span class="existencia hay">${stock} en existencia</span>`;
}

function codigo(id) {
    // 7 → "REF-007"
    return "REF-" + String(id).padStart(3, "0");
}

function sinAcentos(texto) {
    // Así "bujia" también encuentra "Bujía"
    return texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

// Marca un campo en rojo con su mensaje, o lo limpia si no hay mensaje
function marcarError(campo, mensaje) {
    campo.closest(".campo").classList.toggle("invalido", mensaje !== "");
    document.getElementById("error-" + campo.id).textContent = mensaje;
    return mensaje === "";
}

// ===== Sesión =====
// Se guarda en el navegador para que siga abierta al cambiar de página
function leerUsuario() {
    try { return localStorage.getItem("usuario"); } catch (e) { return null; }
}

// El id del usuario (id_login) se usa para registrar quién crea cada orden
function leerIdLogin() {
    try { return Number(localStorage.getItem("id_login")) || null; } catch (e) { return null; }
}

// El token que dio el servidor al iniciar sesión: con él sabe quién eres de verdad
function leerToken() {
    try { return localStorage.getItem("token"); } catch (e) { return null; }
}

// El rol decide qué puede hacer: "Administrador", "Empleado", "Almacenista" o "Cliente"
const ROLES = ["Administrador", "Empleado", "Almacenista", "Cliente"];

// Las mismas reglas que el microservicio de Órdenes (allá se revisan de verdad;
// aquí solo sirven para no mostrar botones que el usuario no puede usar)
const PUEDEN_CREAR = { Venta: ["Administrador", "Empleado", "Cliente"], Compra: ["Administrador", "Almacenista"] };
const PUEDEN_AVANZAR = { Venta: ["Administrador", "Empleado"], Compra: ["Administrador", "Almacenista"] };
// Quién puede poner un precio distinto al de la tienda (en una venta, solo el Administrador)
const PUEDEN_CAMBIAR_PRECIO = { Venta: ["Administrador"], Compra: ["Administrador", "Almacenista"] };

function leerRol() {
    try { return localStorage.getItem("rol"); } catch (e) { return null; }
}

function esAdministrador() {
    return leerRol() === "Administrador";
}

function esCliente() {
    return leerRol() === "Cliente";
}

// Quién puede entrar a la página del Almacén (el stock de la tienda)
const PUEDEN_VER_ALMACEN = ["Administrador", "Almacenista"];

function veAlmacen() {
    return PUEDEN_VER_ALMACEN.includes(leerRol());
}

function puedeCrear(tipo) {
    return PUEDEN_CREAR[tipo].includes(leerRol());
}

function puedeAvanzar(tipo) {
    return PUEDEN_AVANZAR[tipo].includes(leerRol());
}

// Dirección de la ventana de inicio de sesión. Lleva la página actual en "volver"
// para regresar aquí después de entrar (ej. al carrito)
function enlaceLogin() {
    const pagina = location.pathname.split("/").pop() + location.search;
    return "index.html?volver=" + encodeURIComponent(pagina) + "#login";
}

// Después de entrar: si llegaste desde otra página (index.html?volver=carrito.html), regresas a ella.
// Solo se aceptan páginas de este sitio, como "carrito.html" o "detalle.html?id=3"
function volverDespuesDeEntrar() {
    const volver = new URLSearchParams(location.search).get("volver");
    if (volver && /^[a-z]+\.html(\?[\w=&%-]*)?$/.test(volver)) location.href = volver;
}

// Abre la ventana de inicio de sesión limpia: sin lo que se escribió ni los errores de la vez anterior
function abrirLogin() {
    const dialogo = document.getElementById("dialogo-login");
    document.getElementById("form-login").reset();
    ["usuario", "contrasena"].forEach(id => marcarError(document.getElementById(id), ""));
    if (!dialogo.open) dialogo.showModal();
}

function guardarUsuario(nombre, idLogin, rol, token) {
    try {
        if (nombre) {
            localStorage.setItem("usuario", nombre);
            localStorage.setItem("id_login", idLogin);
            localStorage.setItem("rol", rol);
            localStorage.setItem("token", token);
        } else {
            localStorage.removeItem("usuario");
            localStorage.removeItem("id_login");
            localStorage.removeItem("rol");
            localStorage.removeItem("token");
        }
    } catch (e) { }
}

// ===== Menú hamburguesa =====
const panel = document.getElementById("panel");
const botonMenu = document.getElementById("boton-menu");
const fondoOscuro = document.getElementById("fondo-oscuro");

function abrirMenu() {
    panel.classList.add("abierto");
    fondoOscuro.classList.add("visible");
    botonMenu.setAttribute("aria-expanded", "true");
    document.getElementById("cerrar-menu").focus();
}

function cerrarMenu() {
    if (!panel.classList.contains("abierto")) return;
    panel.classList.remove("abierto");
    fondoOscuro.classList.remove("visible");
    botonMenu.setAttribute("aria-expanded", "false");
    botonMenu.focus();
}

botonMenu.addEventListener("click", abrirMenu);
document.getElementById("cerrar-menu").addEventListener("click", cerrarMenu);
fondoOscuro.addEventListener("click", cerrarMenu);
document.addEventListener("keydown", e => { if (e.key === "Escape") cerrarMenu(); });
panel.querySelectorAll("a").forEach(enlace => enlace.addEventListener("click", cerrarMenu));

// ===== Botones de sesión (encabezado y menú) =====
const botonesSesion = document.querySelectorAll(".accion-sesion");

function pintarSesion() {
    // Una sesión vieja (sin rol, o con un rol que ya no existe como "Vendedor") se cierra
    if (leerUsuario() && !ROLES.includes(leerRol())) guardarUsuario(null);

    const usuario = leerUsuario();
    const textoUsuario = document.getElementById("panel-usuario");
    textoUsuario.textContent = usuario ? "Hola, " : "No has iniciado sesión";
    if (usuario) {
        const nombre = document.createElement("strong");
        nombre.textContent = usuario;
        textoUsuario.append(nombre, " · " + leerRol());
    }
    botonesSesion.forEach(boton => {
        const esChico = boton.classList.contains("boton-chico");
        if (esChico) boton.textContent = usuario ? "Salir" : "Entrar";
        else {
            boton.textContent = usuario ? "Cerrar sesión" : "Iniciar sesión";
            boton.classList.toggle("boton-borde", Boolean(usuario));
        }
    });

    // El Administrador ve en el menú la opción para registrar usuarios con cualquier rol
    const enlaceRegistro = document.getElementById("enlace-registro");
    if (esAdministrador() && !enlaceRegistro) {
        const li = document.createElement("li");
        li.innerHTML = `<a href="index.html#registro" id="enlace-registro">Registrar usuario</a>`;
        li.querySelector("a").addEventListener("click", cerrarMenu);
        document.querySelector(".panel-enlaces").append(li);
    } else if (!esAdministrador() && enlaceRegistro) {
        enlaceRegistro.parentElement.remove();
    }

    // El Almacenista y el Administrador ven en el menú la página del Almacén (el stock), debajo de Órdenes
    const enlaceAlmacen = document.getElementById("enlace-almacen");
    if (veAlmacen() && !enlaceAlmacen) {
        const li = document.createElement("li");
        const enAlmacen = location.pathname.endsWith("almacen.html");
        li.innerHTML = `<a href="almacen.html" id="enlace-almacen" ${enAlmacen ? 'aria-current="page"' : ""}>Almacén</a>`;
        li.querySelector("a").addEventListener("click", cerrarMenu);
        const ordenes = document.querySelector('.panel-enlaces a[href="ordenes.html"]');
        ordenes.parentElement.after(li);
    } else if (!veAlmacen() && enlaceAlmacen) {
        enlaceAlmacen.parentElement.remove();
    }

    // Aviso para las páginas que cambian según quién inició sesión (ej. la portada)
    window.dispatchEvent(new Event("sesioncambiada"));
}

botonesSesion.forEach(boton => boton.addEventListener("click", () => {
    if (leerUsuario()) {
        guardarUsuario(null);
        guardarCarrito([]);   // en una computadora compartida, el siguiente no ve tu carrito
        guardarNotas("");     // ni sus notas
        pintarSesion();
        return;
    }
    const dialogo = document.getElementById("dialogo-login");
    if (dialogo) {
        cerrarMenu();
        abrirLogin();
    } else {
        // La ventana de inicio de sesión solo está en index.html
        location.href = enlaceLogin();
    }
}));

pintarSesion();

// ===== Carrito: se guarda en el navegador, igual que la sesión =====
// Es para el Cliente (o quien todavía no inicia sesión); el personal registra ventas desde Órdenes
const botonCarrito = document.getElementById("boton-carrito");

function usaCarrito() {
    return !leerUsuario() || esCliente();
}

// [{ id_producto: 1, cantidad: 2 }, ...]
function leerCarrito() {
    try { return JSON.parse(localStorage.getItem("carrito")) || []; } catch (e) { return []; }
}

function guardarCarrito(carrito) {
    try { localStorage.setItem("carrito", JSON.stringify(carrito)); } catch (e) { }
    pintarCarrito();
}

function cantidadEnCarrito(idProducto) {
    const renglon = leerCarrito().find(r => r.id_producto === idProducto);
    return renglon ? renglon.cantidad : 0;
}

// Suma piezas sin pasar de las que hay en existencia. Regresa false si ya no cabe ninguna
function agregarAlCarrito(producto, cantidad = 1) {
    const carrito = leerCarrito();
    let renglon = carrito.find(r => r.id_producto === producto.id);
    if (!renglon) {
        renglon = { id_producto: producto.id, cantidad: 0 };
        carrito.push(renglon);
    }
    const nueva = Math.min(renglon.cantidad + cantidad, producto.stock);
    if (nueva === renglon.cantidad) return false;
    renglon.cantidad = nueva;
    guardarCarrito(carrito);
    if (botonCarrito && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
        botonCarrito.animate([{ transform: "scale(1.2)" }, { transform: "scale(1)" }], { duration: 250, easing: "ease-out" });
    }
    return true;
}

// Las notas del carrito también se guardan en el navegador: así no se pierden
// si sales a iniciar sesión y regresas al carrito
function leerNotas() {
    try { return localStorage.getItem("carrito-notas") || ""; } catch (e) { return ""; }
}

function guardarNotas(texto) {
    try {
        if (texto) localStorage.setItem("carrito-notas", texto);
        else localStorage.removeItem("carrito-notas");
    } catch (e) { }
}

// El ícono del encabezado con el número de piezas
function pintarCarrito() {
    if (!botonCarrito) return;
    const piezas = leerCarrito().reduce((suma, r) => suma + r.cantidad, 0);
    const cuenta = botonCarrito.querySelector(".carrito-cuenta");
    botonCarrito.hidden = !usaCarrito();
    cuenta.textContent = piezas;
    cuenta.hidden = piezas === 0;
    botonCarrito.setAttribute("aria-label", `Carrito: ${piezas} ${piezas === 1 ? "pieza" : "piezas"}`);
}

// Botón "Agregar al carrito" de las tarjetas (catálogo y "Más de esta categoría")
function escucharAgregar(lista, buscarProducto) {
    lista.addEventListener("click", e => {
        const boton = e.target.closest("[data-agregar]");
        if (!boton) return;
        const agregado = agregarAlCarrito(buscarProducto(Number(boton.dataset.agregar)));
        const texto = boton.textContent;
        boton.textContent = agregado ? "✓ Agregado" : "Ya no hay más piezas";
        boton.disabled = true;
        setTimeout(() => {
            boton.textContent = texto;
            boton.disabled = false;
        }, 1200);
    });
}

window.addEventListener("sesioncambiada", pintarCarrito);
window.addEventListener("storage", e => { if (e.key === "carrito") pintarCarrito(); });   // si lo cambias en otra pestaña
pintarCarrito();

// ===== Inicio de sesión (index.html) → POST /api/login =====
const dialogoLogin = document.getElementById("dialogo-login");

if (dialogoLogin) {
    const formLogin = document.getElementById("form-login");
    const usuario = document.getElementById("usuario");
    const contrasena = document.getElementById("contrasena");
    const botonEntrar = formLogin.querySelector('button[type="submit"]');

    document.getElementById("cancelar-login").addEventListener("click", () => dialogoLogin.close());

    formLogin.addEventListener("submit", async e => {
        e.preventDefault();
        const usuarioOk = marcarError(usuario, usuario.value.trim() ? "" : "Escribe tu usuario");
        const contrasenaOk = marcarError(contrasena, contrasena.value ? "" : "Escribe tu contraseña");
        if (!usuarioOk || !contrasenaOk) return;

        botonEntrar.disabled = true;
        botonEntrar.textContent = "Entrando…";
        try {
            // Ahora sí se revisa la contraseña de verdad, en el microservicio de Login
            const sesion = await pedirAPI("/login", {
                method: "POST",
                body: JSON.stringify({ username: usuario.value.trim(), password: contrasena.value }),
            });
            guardarUsuario(sesion.username, sesion.id_login, sesion.rol, sesion.token);
            formLogin.reset();
            dialogoLogin.close();
            pintarSesion();
            volverDespuesDeEntrar();
        } catch (error) {
            marcarError(contrasena, error.estado === 401 ? "Usuario o contraseña incorrectos" : error.message);
        } finally {
            botonEntrar.disabled = false;
            botonEntrar.textContent = "Entrar";
        }
    });

    if (location.hash === "#login" && !leerUsuario()) abrirLogin();
}

// ===== Registrar usuario (index.html) → POST /api/usuarios =====
// Cualquiera crea su cuenta como Cliente. El Administrador además elige el rol.
const dialogoRegistro = document.getElementById("dialogo-registro");

if (dialogoRegistro) {
    const formRegistro = document.getElementById("form-registro");
    const regUsuario = document.getElementById("reg-usuario");
    const regCorreo = document.getElementById("reg-correo");
    const regContrasena = document.getElementById("reg-contrasena");
    const regConfirmar = document.getElementById("reg-confirmar");
    const regRol = document.getElementById("reg-rol");
    const avisoRegistro = document.getElementById("registro-exito");
    const botonRegistrar = document.getElementById("guardar-registro");
    const campos = [regUsuario, regCorreo, regContrasena, regConfirmar, regRol];

    function abrirRegistro() {
        const admin = esAdministrador();
        formRegistro.reset();
        campos.forEach(campo => marcarError(campo, ""));
        avisoRegistro.hidden = true;
        document.getElementById("campo-rol").hidden = !admin;
        document.getElementById("volver-login").hidden = admin;
        document.getElementById("registro-titulo").textContent = admin ? "Registrar usuario" : "Crear cuenta";
        document.getElementById("registro-texto").textContent = admin
            ? "Como Administrador registras al personal de la tienda. Los clientes crean su propia cuenta."
            : "Regístrate para hacer pedidos.";
        botonRegistrar.textContent = admin ? "Registrar" : "Crear cuenta";
        if (dialogoLogin.open) dialogoLogin.close();
        cerrarMenu();
        if (!dialogoRegistro.open) dialogoRegistro.showModal();
    }

    document.getElementById("ir-registro").addEventListener("click", abrirRegistro);
    document.getElementById("cancelar-registro").addEventListener("click", () => dialogoRegistro.close());
    document.getElementById("ir-login").addEventListener("click", () => {
        dialogoRegistro.close();
        abrirLogin();
    });

    formRegistro.addEventListener("submit", async e => {
        e.preventDefault();
        avisoRegistro.hidden = true;
        const nombre = regUsuario.value.trim();
        const correo = regCorreo.value.trim();
        const revisiones = [
            marcarError(regUsuario, nombre.length < 3 || nombre.includes(" ") ? "Mínimo 3 letras y sin espacios" : ""),
            marcarError(regCorreo, /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(correo) ? "" : "Escribe un correo válido"),
            marcarError(regContrasena, regContrasena.value.length < 10 ? "Mínimo 10 caracteres" : ""),
            marcarError(regConfirmar, regConfirmar.value !== regContrasena.value ? "Las contraseñas no coinciden" : ""),
        ];
        if (revisiones.includes(false)) return;

        const admin = esAdministrador();
        botonRegistrar.disabled = true;
        try {
            const nuevo = await pedirAPI("/usuarios", {
                method: "POST",
                body: JSON.stringify({
                    username: nombre,
                    email: correo,
                    password: regContrasena.value,
                    rol: admin ? regRol.value : "Cliente",
                }),
            });
            if (admin) {
                // El Administrador sigue con su sesión y puede registrar a otro
                avisoRegistro.textContent = `Listo: se creó "${nuevo.username}" con el rol ${nuevo.rol}.`;
                avisoRegistro.hidden = false;
                formRegistro.reset();
            } else {
                // El cliente nuevo entra directo con su cuenta
                const sesion = await pedirAPI("/login", {
                    method: "POST",
                    body: JSON.stringify({ username: nombre, password: regContrasena.value }),
                });
                guardarUsuario(sesion.username, sesion.id_login, sesion.rol, sesion.token);
                dialogoRegistro.close();
                pintarSesion();
                volverDespuesDeEntrar();
            }
        } catch (error) {
            // Cada error se muestra debajo del campo que lo causó
            const texto = error.message.toLowerCase();
            const campo = texto.includes("correo") ? regCorreo
                : texto.includes("contraseña") ? regContrasena
                : texto.includes("rol") && admin ? regRol
                : texto.includes("usuario") ? regUsuario
                : regConfirmar;
            marcarError(campo, error.message);
        } finally {
            botonRegistrar.disabled = false;
        }
    });

    if (location.hash === "#registro") abrirRegistro();
    window.addEventListener("hashchange", () => { if (location.hash === "#registro") abrirRegistro(); });
    // Si la dirección ya termina en "#registro" (la ventana ya se abrió antes), el enlace
    // "Registrar usuario" del menú no la cambia y no hay "hashchange": se abre aquí directo
    document.addEventListener("click", e => {
        if (e.target.closest("#enlace-registro") && location.hash === "#registro") {
            e.preventDefault();
            abrirRegistro();
        }
    });
}

// ===== Portada (index.html): datos rápidos, promociones y categorías =====
const listaPromociones = document.getElementById("lista-promociones");
let promocionesPortada = [];   // las que se ven en la portada (el Administrador ve también las futuras)

if (listaPromociones) {
    iniciarPortada();
    iniciarAdministracionPortada();
    // Al entrar o salir se vuelve a dibujar: el Administrador ve los botones para agregar y eliminar
    window.addEventListener("sesioncambiada", iniciarPortada);
}

async function iniciarPortada() {
    const datosRapidos = document.getElementById("datos-rapidos");
    const listaCategorias = document.getElementById("lista-categorias");
    const admin = esAdministrador();
    document.getElementById("boton-nueva-promo").hidden = !admin;
    document.getElementById("boton-nueva-categoria").hidden = !admin;
    listaPromociones.innerHTML = `<p class="contador">Cargando promociones…</p>`;

    let todas = null;
    try {
        // Las peticiones van al mismo tiempo
        [categorias, productos, promociones, todas] = await Promise.all([
            pedirAPI("/categorias"),
            pedirAPI("/productos"),
            pedirAPI("/dashboard"),                      // solo las promociones vigentes hoy
            admin ? pedirAPI("/promociones") : null,     // el Administrador también ve las que no han empezado
        ]);
    } catch (error) {
        mostrarError(listaPromociones, error.message);
        listaCategorias.innerHTML = "";
        datosRapidos.innerHTML = "";
        return;
    }
    promocionesPortada = todas || promociones;

    datosRapidos.innerHTML = `
        <span><strong>${productos.length}</strong> ${productos.length === 1 ? "producto" : "productos"}</span>
        <span><strong>${categorias.length}</strong> ${categorias.length === 1 ? "categoría" : "categorías"}</span>
        <span><strong>${promociones.length}</strong> ${promociones.length === 1 ? "promoción activa" : "promociones activas"}</span>
    `;

    if (promocionesPortada.length === 0) {
        listaPromociones.innerHTML = admin
            ? `<div class="vacio"><h2>No hay promociones</h2><p>Crea una con “+ Nueva promoción”.</p></div>`
            : `<div class="vacio"><h2>No hay promociones este mes</h2><p>Vuelve pronto.</p></div>`;
    } else {
        // --i es el número de tarjeta: el CSS lo usa para que entren una por una
        listaPromociones.innerHTML = promocionesPortada.map((promo, i) => {
            const vigente = promociones.some(v => v.id === promo.id);
            const vigencia = vigente ? `Hasta el ${fechaCorta(promo.fecha_fin)}`
                : promo.activa ? `Empieza el ${fechaCorta(promo.fecha_inicio)}` : "Pausada";
            return `
            <article class="promo">
                <span class="promo-descuento">-${promo.descuento}%</span>
                <h3>${escapar(promo.nombre)}</h3>
                ${promo.descripcion ? `<p>${escapar(promo.descripcion)}</p>` : ""}
                <span class="promo-vigencia">${vigencia}</span>
                <ul>
                    ${promo.productos.map(p => `<li>
                        <span>${escapar(p.nombre)}</span>
                        <span class="precio-promo"><s>${dinero(p.precio)}</s>${dinero(p.precio_con_descuento)}</span>
                    </li>`).join("")}
                </ul>
                ${admin ? `<div class="promo-acciones">
                    <button class="boton boton-chico boton-editar-promo" data-editar-promo="${promo.id}">Editar</button>
                    <button class="boton boton-chico boton-borrar-promo" data-borrar-promo="${promo.id}">Eliminar promoción</button>
                </div>` : ""}
            </article>`;
        }).join("");
        // Cada promoción aparece un poquito después que la anterior (--i en estilo.css).
        // Se pone desde aquí y no con style="..." en el HTML, que la CSP del Gateway no deja pasar
        listaPromociones.querySelectorAll(".promo").forEach((promo, i) => promo.style.setProperty("--i", i));
    }

    listaCategorias.innerHTML = categorias.map(c => {
        const total = productos.filter(p => p.id_categoria === c.id).length;
        return `<div class="categoria-caja">
            <a class="categoria" href="producto.html?categoria=${c.id}">
                <span><strong>${escapar(c.nombre)}</strong><small>${total} ${total === 1 ? "producto" : "productos"}</small></span>
            </a>
            ${admin ? `<button type="button" class="borrar-categoria" data-borrar-categoria="${c.id}" aria-label="Eliminar la categoría ${escapar(c.nombre)}">✕</button>` : ""}
        </div>`;
    }).join("");
}

// ===== Agregar, editar y eliminar promociones y categorías (index.html, solo el Administrador) =====
function iniciarAdministracionPortada() {
    const dialogoPromo = document.getElementById("dialogo-promocion");
    const formPromo = document.getElementById("form-promocion");
    const promoNombre = document.getElementById("promo-nombre");
    const promoDescripcion = document.getElementById("promo-descripcion");
    const promoDescuento = document.getElementById("promo-descuento");
    const promoInicio = document.getElementById("promo-inicio");
    const promoFin = document.getElementById("promo-fin");
    const promoProductos = document.getElementById("promo-productos");
    const botonGuardarPromo = document.getElementById("guardar-promocion");
    const promoTitulo = document.getElementById("promo-titulo");
    const dialogoCategoria = document.getElementById("dialogo-categoria");
    const formCategoria = document.getElementById("form-categoria");
    const catNombre = document.getElementById("cat-nombre");
    const catDescripcion = document.getElementById("cat-descripcion");
    const botonGuardarCategoria = document.getElementById("guardar-categoria");

    // La fecha de hoy como "2026-10-27" (en hora local, no en UTC)
    const hoy = () => new Date().toLocaleDateString("en-CA");

    document.querySelectorAll("[data-cerrar]").forEach(boton =>
        boton.addEventListener("click", () => boton.closest("dialog").close()));

    let promoEditando = null;   // null = promoción nueva; si no, la promoción que se está editando
    let inicioOriginal = null;  // fecha de inicio de la promoción que se edita ("2026-10-01")

    // "Termina" no puede ser antes de "Empieza" ni antes de hoy
    function ajustarMinimoFin() {
        promoFin.min = promoInicio.value > hoy() ? promoInicio.value : hoy();
    }
    promoInicio.addEventListener("change", ajustarMinimoFin);

    // ----- Nueva promoción o editar una (es la misma ventana) -----
    function abrirPromocion(promo) {
        promoEditando = promo;
        formPromo.reset();
        [promoNombre, promoDescuento, promoInicio, promoFin, promoProductos].forEach(campo => marcarError(campo, ""));
        promoTitulo.textContent = promo ? "Editar promoción" : "Nueva promoción";
        const enLaPromo = promo ? promo.productos.map(p => p.id) : [];
        promoProductos.innerHTML = productos.map(p => `
            <label class="casilla">
                <input type="checkbox" value="${p.id}" ${enLaPromo.includes(p.id) ? "checked" : ""}> ${escapar(p.nombre)} <small>${dinero(p.precio)}</small>
            </label>`).join("");
        if (promo) {
            promoNombre.value = promo.nombre;
            promoDescripcion.value = promo.descripcion || "";
            promoDescuento.value = promo.descuento;
            promoInicio.value = promo.fecha_inicio.slice(0, 10);   // "2026-10-01T00:00:00" → "2026-10-01"
            promoFin.value = promo.fecha_fin.slice(0, 10);
        } else {
            promoInicio.value = hoy();
        }
        // No se puede elegir un día que ya pasó. Si la promoción que se edita ya empezó,
        // se puede dejar su fecha de inicio como está, pero no moverla a otro día pasado
        inicioOriginal = promo ? promo.fecha_inicio.slice(0, 10) : null;
        promoInicio.min = inicioOriginal && inicioOriginal < hoy() ? inicioOriginal : hoy();
        ajustarMinimoFin();
        dialogoPromo.showModal();
    }

    document.getElementById("boton-nueva-promo").addEventListener("click", () => abrirPromocion(null));

    formPromo.addEventListener("submit", async e => {
        e.preventDefault();
        const marcados = [...promoProductos.querySelectorAll("input:checked")].map(casilla => Number(casilla.value));
        const descuento = Number(promoDescuento.value);
        const inicio = promoInicio.value;
        const fin = promoFin.value;
        const revisiones = [
            marcarError(promoNombre, promoNombre.value.trim() ? "" : "Escribe el nombre de la promoción"),
            marcarError(promoDescuento, descuento >= 1 && descuento <= 100 ? "" : "Del 1 al 100"),
            marcarError(promoInicio, !inicio ? "Elige cuándo empieza"
                : inicio < hoy() && inicio !== inicioOriginal ? "No puede empezar en un día que ya pasó" : ""),
            marcarError(promoFin, !fin ? "Elige cuándo termina"
                : fin < inicio ? "Debe terminar después de empezar"
                : fin < hoy() ? "Esa fecha ya pasó" : ""),
            marcarError(promoProductos, marcados.length > 0 ? "" : "Elige al menos un producto"),
        ];
        if (revisiones.includes(false)) return;

        const datos = {
            nombre: promoNombre.value.trim(),
            descripcion: promoDescripcion.value.trim() || null,
            descuento: descuento,
            fecha_inicio: inicio + "T00:00:00",   // desde el primer segundo del día
            fecha_fin: fin + "T23:59:59",         // hasta el último segundo del día
            productos: marcados,
        };
        botonGuardarPromo.disabled = true;
        try {
            if (promoEditando) {
                datos.activa = promoEditando.activa;   // se queda como estaba
                await pedirAPI(`/promociones/${promoEditando.id}` , { method: "PUT", body: JSON.stringify(datos) });
            } else {
                await pedirAPI("/promociones" , { method: "POST", body: JSON.stringify(datos) });
            }
            dialogoPromo.close();
            iniciarPortada();
        } catch (error) {
            marcarError(promoProductos, error.message);
        } finally {
            botonGuardarPromo.disabled = false;
        }
    });

    // ----- Editar o eliminar una promoción (botones de cada tarjeta) -----
    listaPromociones.addEventListener("click", async e => {
        const editar = e.target.closest("[data-editar-promo]");
        if (editar) {
            abrirPromocion(promocionesPortada.find(p => p.id === Number(editar.dataset.editarPromo)));
            return;
        }
        const boton = e.target.closest("[data-borrar-promo]");
        if (!boton) return;
        const promo = promocionesPortada.find(p => p.id === Number(boton.dataset.borrarPromo));
        if (!confirm(`¿Eliminar la promoción "${promo.nombre}"? Sus productos regresan a su precio normal.`)) return;
        boton.disabled = true;
        try {
            await pedirAPI("/promociones/" + promo.id , { method: "DELETE" });
            iniciarPortada();
        } catch (error) {
            alert(error.message);
            boton.disabled = false;
        }
    });

    // ----- Nueva categoría -----
    document.getElementById("boton-nueva-categoria").addEventListener("click", () => {
        formCategoria.reset();
        marcarError(catNombre, "");
        dialogoCategoria.showModal();
    });

    formCategoria.addEventListener("submit", async e => {
        e.preventDefault();
        if (!marcarError(catNombre, catNombre.value.trim() ? "" : "Escribe el nombre de la categoría")) return;
        botonGuardarCategoria.disabled = true;
        try {
            await pedirAPI("/categorias" , {
                method: "POST",
                body: JSON.stringify({ nombre: catNombre.value.trim(), descripcion: catDescripcion.value.trim() || null }),
            });
            dialogoCategoria.close();
            iniciarPortada();
        } catch (error) {
            marcarError(catNombre, error.message);   // ej. "Ya existe la categoría 'Frenos'"
        } finally {
            botonGuardarCategoria.disabled = false;
        }
    });

    // ----- Eliminar categoría -----
    document.getElementById("lista-categorias").addEventListener("click", async e => {
        const boton = e.target.closest("[data-borrar-categoria]");
        if (!boton) return;
        const categoria = categorias.find(c => c.id === Number(boton.dataset.borrarCategoria));
        if (!confirm(`¿Eliminar la categoría "${categoria.nombre}"?`)) return;
        boton.disabled = true;
        try {
            await pedirAPI("/categorias/" + categoria.id  , { method: "DELETE" });
            iniciarPortada();
        } catch (error) {
            alert(error.message);   // ej. "La categoría 'Frenos' tiene 2 productos: ..."
            boton.disabled = false;
        }
    });
}

// La foto del producto, o un ícono de engrane si todavía no tiene
function fotoProducto(p) {
    if (p.imagen) {
        return `<img src="${escapar(p.imagen)}" alt="${escapar(p.nombre)}" loading="lazy" decoding="async">`;
    }
    return `<span class="sin-foto" role="img" aria-label="${escapar(p.nombre)}: todavía sin foto">
        <svg viewBox="0 0 24 24" width="40" height="40" aria-hidden="true"><path fill="currentColor" d="M19.4 13a7.5 7.5 0 0 0 0-2l2.1-1.6-2-3.5-2.5 1a7.4 7.4 0 0 0-1.7-1L15 3.3h-4l-.4 2.6a7.4 7.4 0 0 0-1.7 1l-2.5-1-2 3.5L6.6 11a7.5 7.5 0 0 0 0 2l-2.1 1.6 2 3.5 2.5-1a7.4 7.4 0 0 0 1.7 1l.4 2.6h4l.4-2.6a7.4 7.4 0 0 0 1.7-1l2.5 1 2-3.5zM12 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z"/></svg>
        <small>Sin foto</small></span>`;
}

// Ruta de la carpeta img/ o dirección https:// (lo mismo que acepta el microservicio de Productos)
const FORMATO_IMAGEN = /^(img\/[A-Za-z0-9_.\/-]+\.(jpg|jpeg|png|webp)|https:\/\/[^\s"'<>]+)$/;

// ===== Catálogo (producto.html) =====
function tarjetaProducto(p) {
    const promo = promocionDe(p.id);
    const precio = promo
        ? `<span class="precio"><s>${dinero(p.precio)}</s>${dinero(conDescuento(p.precio, promo.descuento))}</span>`
        : `<span class="precio">${dinero(p.precio)}</span>`;

    return `
        <article class="producto">
            ${promo ? `<span class="insignia-promo">-${promo.descuento}%</span>` : ""}
            <a class="producto-foto" href="detalle.html?id=${p.id}" tabindex="-1" aria-hidden="true">${fotoProducto(p)}</a>
            <div class="producto-arriba">
                <span>${codigo(p.id)}</span>
                <span>${escapar(p.categoria)}</span>
            </div>
            <h3><a class="enlace-producto" href="detalle.html?id=${p.id}">${escapar(p.nombre)}</a></h3>
            <p>${escapar(p.descripcion)}</p>
            <div class="producto-abajo">${precio}${existenciaDe(p.stock)}</div>
            ${esAdministrador() && document.getElementById("dialogo-producto") ? `<button class="boton boton-borde boton-chico boton-editar-producto" data-editar-producto="${p.id}">Editar</button>` : ""}
            ${usaCarrito() && p.stock > 0 ? `<button class="boton boton-chico boton-agregar" data-agregar="${p.id}">Agregar al carrito</button>` : ""}
        </article>
    `;
}
const listaProductos = document.getElementById("lista-productos");

if (listaProductos) {
    iniciarCatalogo();
}

async function iniciarCatalogo() {
    const buscar = document.getElementById("filtro-buscar");
    const disponibles = document.getElementById("filtro-disponibles");
    const chips = document.getElementById("chips-categorias");
    const contador = document.getElementById("contador");
    contador.textContent = "Cargando productos…";

    try {
        [categorias, productos, promociones] = await Promise.all([
            pedirAPI("/categorias"),
            pedirAPI("/productos"),
            pedirAPI("/dashboard"),   // para mostrar el precio con descuento
        ]);
    } catch (error) {
        contador.textContent = "";
        mostrarError(listaProductos, error.message);
        return;
    }

    // Si llegas desde el buscador o una categoría de index.html, se aplica el filtro
    const parametros = new URLSearchParams(location.search);
    buscar.value = parametros.get("buscar") || "";
    let categoriaElegida = Number(parametros.get("categoria")) || 0;   // 0 = todas

    chips.innerHTML = [{ id: 0, nombre: "Todas" }, ...categorias]
        .map(c => `<button class="chip" data-categoria="${c.id}" aria-pressed="${c.id === categoriaElegida}">${escapar(c.nombre)}</button>`)
        .join("");

    chips.addEventListener("click", e => {
        const chip = e.target.closest(".chip");
        if (!chip) return;
        categoriaElegida = Number(chip.dataset.categoria);
        chips.querySelectorAll(".chip").forEach(c => c.setAttribute("aria-pressed", c === chip));
        filtrar();
    });

    // Sin animación aquí a propósito: se vuelve a dibujar con cada letra que escribes
    function filtrar() {
        const texto = sinAcentos(buscar.value.trim());
        const resultado = productos.filter(p =>
            sinAcentos(p.nombre).includes(texto) &&
            (categoriaElegida === 0 || p.id_categoria === categoriaElegida) &&
            (!disponibles.checked || p.stock > 0)
        );
        listaProductos.innerHTML = resultado.map(tarjetaProducto).join("");
        contador.textContent = `${resultado.length} de ${productos.length} productos`;
        document.getElementById("sin-resultados").hidden = resultado.length > 0;
    }

    document.getElementById("limpiar-filtros").addEventListener("click", () => {
        buscar.value = "";
        disponibles.checked = false;
        chips.querySelector('[data-categoria="0"]').click();
    });

    buscar.addEventListener("input", filtrar);
    disponibles.addEventListener("change", filtrar);
    filtrar();

    // Al entrar o salir se vuelve a dibujar: el Administrador ve los botones para agregar y editar
    window.addEventListener("sesioncambiada", () => {
        document.getElementById("boton-nuevo-producto").hidden = !esAdministrador();
        filtrar();
    });
    document.getElementById("boton-nuevo-producto").hidden = !esAdministrador();

    // Después de guardar o eliminar se vuelve a pedir la lista y se respetan los filtros
    async function recargar() {
        try {
            productos = await pedirAPI("/productos");
        } catch (error) {
            mostrarError(listaProductos, error.message);
            return;
        }
        filtrar();
    }
    iniciarAdministracionCatalogo(recargar);
    escucharAgregar(listaProductos, id => productos.find(p => p.id === id));
}

// ===== Agregar, editar y eliminar productos (producto.html, solo el Administrador) =====
function iniciarAdministracionCatalogo(recargar) {
    const dialogo = document.getElementById("dialogo-producto");
    const form = document.getElementById("form-producto");
    const titulo = document.getElementById("producto-titulo");
    const nombre = document.getElementById("prod-nombre");
    const descripcion = document.getElementById("prod-descripcion");
    const precio = document.getElementById("prod-precio");
    const stock = document.getElementById("prod-stock");
    const categoria = document.getElementById("prod-categoria");
    const imagen = document.getElementById("prod-imagen");
    const notaStock = document.getElementById("nota-stock");
    const botonGuardar = document.getElementById("guardar-producto");
    const botonEliminar = document.getElementById("eliminar-producto");
    const errorProducto = document.getElementById("producto-error");
    let editando = null;   // null = producto nuevo; si no, el producto que se está editando

    document.querySelectorAll("[data-cerrar]").forEach(boton =>
        boton.addEventListener("click", () => boton.closest("dialog").close()));

    function abrir(producto) {
        editando = producto;
        form.reset();
        [nombre, precio, stock, categoria, imagen].forEach(campo => marcarError(campo, ""));
        errorProducto.textContent = "";
        titulo.textContent = producto ? "Editar producto" : "Nuevo producto";
        categoria.innerHTML = `<option value="">Elige una categoría</option>` +
            categorias.map(c => `<option value="${c.id}">${escapar(c.nombre)}</option>`).join("");
        // La existencia solo se escribe al crear; después cambia con las órdenes
        stock.disabled = producto !== null;
        notaStock.hidden = producto === null;
        botonEliminar.hidden = producto === null;
        if (producto) {
            nombre.value = producto.nombre;
            descripcion.value = producto.descripcion || "";
            precio.value = producto.precio;
            stock.value = producto.stock;
            categoria.value = producto.id_categoria;
            imagen.value = producto.imagen || "";
        } else {
            stock.value = 0;
        }
        dialogo.showModal();
    }

    document.getElementById("boton-nuevo-producto").addEventListener("click", () => abrir(null));

    document.getElementById("lista-productos").addEventListener("click", e => {
        const boton = e.target.closest("[data-editar-producto]");
        if (boton) abrir(productos.find(p => p.id === Number(boton.dataset.editarProducto)));
    });

    form.addEventListener("submit", async e => {
        e.preventDefault();
        const revisiones = [
            marcarError(nombre, nombre.value.trim() ? "" : "Escribe el nombre del producto"),
            marcarError(precio, precio.value !== "" && Number(precio.value) >= 0 ? "" : "Escribe un precio válido"),
            marcarError(stock, Number.isInteger(Number(stock.value)) && Number(stock.value) >= 0 ? "" : "Escribe un número entero"),
            marcarError(categoria, categoria.value ? "" : "Elige una categoría"),
            marcarError(imagen, !imagen.value.trim() || FORMATO_IMAGEN.test(imagen.value.trim()) ? ""
                : "Escribe una ruta como img/productos/foto.jpg o una dirección https://"),
        ];
        if (revisiones.includes(false)) return;

        const datos = {
            nombre: nombre.value.trim(),
            descripcion: descripcion.value.trim() || null,
            precio: Number(precio.value),
            stock: Number(stock.value),
            id_categoria: Number(categoria.value),
            imagen: imagen.value.trim() || null,
        };
        botonGuardar.disabled = true;
        try {
            if (editando) {
                await pedirAPI(`/productos/${editando.id}`, { method: "PUT", body: JSON.stringify(datos) });
            } else {
                await pedirAPI("/productos", { method: "POST", body: JSON.stringify(datos) });
            }
            dialogo.close();
            recargar();
        } catch (error) {
            errorProducto.textContent = error.message;
        } finally {
            botonGuardar.disabled = false;
        }
    });

    botonEliminar.addEventListener("click", async () => {
        if (!confirm(`¿Eliminar el producto "${editando.nombre}"?`)) return;
        botonEliminar.disabled = true;
        try {
            await pedirAPI(`/productos/${editando.id}`, { method: "DELETE" });
            dialogo.close();
            recargar();
        } catch (error) {
            errorProducto.textContent = error.message;   // ej. si ya está en una orden no se puede borrar
        } finally {
            botonEliminar.disabled = false;
        }
    });
}

// ===== Detalle de un producto (detalle.html?id=3) → GET /api/productos/{id} =====
const detalleProducto = document.getElementById("detalle-producto");

if (detalleProducto) {
    iniciarDetalle();
}

async function iniciarDetalle() {
    const id = Number(new URLSearchParams(location.search).get("id"));
    let producto;
    try {
        [producto, promociones] = await Promise.all([
            pedirAPI("/productos/" + (Number.isInteger(id) ? id : 0)),   // "?id=abc" se trata como producto que no existe
            pedirAPI("/dashboard"),   // para saber si tiene descuento
        ]);
    } catch (error) {
        if (error.estado === 404) {
            detalleProducto.innerHTML = `<div class="vacio"><h2>No encontramos ese producto</h2><p>Puede que lo hayan quitado del catálogo.</p><a class="boton boton-borde" href="producto.html">Ver todos los productos</a></div>`;
        } else {
            mostrarError(detalleProducto, error.message);
        }
        return;
    }

    document.title = "Refaccionaria | " + producto.nombre;
    document.getElementById("migas-categoria").innerHTML =
        `/ <a href="producto.html?categoria=${producto.id_categoria}">${escapar(producto.categoria)}</a>`;

    function dibujar() {
        const promo = promocionDe(producto.id);
        const precioFinal = promo ? conDescuento(producto.precio, promo.descuento) : producto.precio;
        detalleProducto.innerHTML = `
            <article class="detalle">
                <div>
                    <div class="detalle-foto">${fotoProducto(producto)}</div>
                    <span class="etiqueta-seccion">${codigo(producto.id)} · ${escapar(producto.categoria)}</span>
                    <h1>${escapar(producto.nombre)}</h1>
                    <p class="detalle-descripcion">${producto.descripcion ? escapar(producto.descripcion) : "Este producto todavía no tiene descripción."}</p>
                </div>
                <aside class="detalle-compra" aria-label="Precio y existencia">
                    ${promo ? `<p class="detalle-promo"><span class="detalle-descuento">-${promo.descuento}%</span> ${escapar(promo.nombre)} · hasta el ${fechaCorta(promo.fecha_fin)}</p>` : ""}
                    <p class="detalle-precio">${promo ? `<s>${dinero(producto.precio)}</s>` : ""}${dinero(precioFinal)}</p>
                    ${promo ? `<p class="detalle-ahorro">Ahorras ${dinero(producto.precio - precioFinal)} por pieza</p>` : ""}
                    ${existenciaDe(producto.stock)}
                    <div class="detalle-acciones">${accionesDetalle(producto)}</div>
                </aside>
            </article>`;
    }

    // Lo que puede hacer cada quien (el microservicio de Órdenes lo vuelve a revisar)
    function accionesDetalle(p) {
        if (usaCarrito() || puedeCrear("Venta")) {
            if (p.stock === 0) return `<p class="nota-campo">Por ahora no hay piezas. Vuelve pronto.</p>`;
            return `<form id="form-pedir" novalidate>
                    <div class="campo">
                        <label for="pedir-cantidad">Cantidad</label>
                        <input type="number" id="pedir-cantidad" min="1" max="${p.stock}" step="1" value="1" inputmode="numeric">
                        <span class="mensaje-error" id="error-pedir-cantidad"></span>
                    </div>
                    <button class="boton" type="submit">${usaCarrito() ? "Agregar al carrito" : "Registrar venta"}</button>
                    <p class="nota-campo" id="aviso-carrito" role="status"></p>
                </form>`;
        }
        if (puedeCrear("Compra")) {
            // El Almacenista no vende, pero sí surte la mercancía
            return `<a class="boton boton-borde" href="ordenes.html?pedir=${p.id}&tipo=Compra">Registrar compra (surtir)</a>`;
        }
        return "";
    }

    // El cliente lo agrega al carrito; el personal va a Órdenes con la venta ya llenada
    detalleProducto.addEventListener("submit", e => {
        e.preventDefault();
        const campo = document.getElementById("pedir-cantidad");
        const cantidad = Number(campo.value);
        const yaTienes = usaCarrito() ? cantidadEnCarrito(producto.id) : 0;
        let problema = "";
        if (!Number.isInteger(cantidad) || cantidad < 1) problema = "Escribe un número entero de 1 o más";
        else if (cantidad + yaTienes > producto.stock) {
            problema = yaTienes
                ? `Ya tienes ${yaTienes} en el carrito y solo hay ${producto.stock}`
                : `Solo hay ${producto.stock} en existencia`;
        }
        if (!marcarError(campo, problema)) {
            document.getElementById("aviso-carrito").textContent = "";   // se quita el "✓ Agregaste..." de antes
            return;
        }

        if (usaCarrito()) {
            agregarAlCarrito(producto, cantidad);
            document.getElementById("aviso-carrito").innerHTML =
                `✓ Agregaste ${cantidad} al carrito. <a href="carrito.html">Ver carrito</a>`;
            return;
        }
        location.href = `ordenes.html?pedir=${producto.id}&cantidad=${cantidad}`;
    });

    window.addEventListener("sesioncambiada", dibujar);
    dibujar();

    // Otros productos de la misma categoría (si falla, simplemente no se muestran)
    const listaRelacionados = document.getElementById("lista-relacionados");
    let relacionados = [];
    try {
        relacionados = (await pedirAPI("/productos?categoria=" + producto.id_categoria))
            .filter(p => p.id !== producto.id)
            .slice(0, 4);
    } catch (error) { }
    const pintarRelacionados = () => listaRelacionados.innerHTML = relacionados.map(tarjetaProducto).join("");
    pintarRelacionados();
    document.getElementById("seccion-relacionados").hidden = relacionados.length === 0;
    window.addEventListener("sesioncambiada", pintarRelacionados);
    escucharAgregar(listaRelacionados, id => relacionados.find(p => p.id === id));
}

// ===== Página del carrito (carrito.html) → POST /api/ordenes =====
const paginaCarrito = document.getElementById("pagina-carrito");

if (paginaCarrito) {
    iniciarCarrito();
}

async function iniciarCarrito() {
    if (!usaCarrito()) {
        paginaCarrito.innerHTML = `<div class="vacio"><h2>El carrito es para los clientes</h2><p>El personal registra las ventas desde Órdenes.</p><a class="boton" href="ordenes.html">Ir a Órdenes</a></div>`;
        return;
    }
    try {
        [productos, promociones] = await Promise.all([
            pedirAPI("/productos"),
            pedirAPI("/dashboard"),   // para el precio con descuento
        ]);
    } catch (error) {
        mostrarError(paginaCarrito, error.message);
        return;
    }

    // El carrito se guardó hace rato: se revisa contra el catálogo de hoy
    const avisos = [];
    const revisado = [];
    for (const renglon of leerCarrito()) {
        const p = productos.find(p => p.id === renglon.id_producto);
        if (!p) {
            avisos.push("Quitamos un producto que ya no está en el catálogo.");
            continue;
        }
        if (p.stock === 0) {
            avisos.push(`${p.nombre} se agotó y lo quitamos del carrito.`);
            continue;
        }
        if (renglon.cantidad > p.stock) {
            avisos.push(`De ${p.nombre} solo quedan ${p.stock}: ajustamos la cantidad.`);
            renglon.cantidad = p.stock;
        }
        revisado.push(renglon);
    }
    guardarCarrito(revisado);

    let notas = leerNotas();   // las que escribiste antes (aunque hayas ido a iniciar sesión)
    function precioDe(p) {
        const promo = promocionDe(p.id);
        return promo ? conDescuento(p.precio, promo.descuento) : p.precio;
    }

    function dibujar() {
        const carrito = leerCarrito();
        const avisosHTML = avisos.length ? `<div class="carrito-avisos" role="status">${avisos.map(a => `<p>${escapar(a)}</p>`).join("")}</div>` : "";
        if (carrito.length === 0) {
            paginaCarrito.innerHTML = avisosHTML + `<div class="vacio"><h2>Tu carrito está vacío</h2><p>Agrega piezas desde el catálogo.</p><a class="boton" href="producto.html">Ver productos</a></div>`;
            return;
        }
        let total = 0;
        let piezas = 0;
        const renglones = carrito.map(r => {
            const p = productos.find(p => p.id === r.id_producto);
            const promo = promocionDe(p.id);
            const subtotal = precioDe(p) * r.cantidad;
            total += subtotal;
            piezas += r.cantidad;
            return `
                <li class="carrito-renglon">
                    <div class="carrito-producto">
                        <a href="detalle.html?id=${p.id}">${escapar(p.nombre)}</a>
                        <small>${dinero(precioDe(p))} c/u${promo ? ` · -${promo.descuento}%` : ""}</small>
                    </div>
                    <div class="cantidad" role="group" aria-label="Cantidad de ${escapar(p.nombre)}">
                        <button type="button" data-restar="${p.id}" aria-label="Una pieza menos" ${r.cantidad === 1 ? "disabled" : ""}>−</button>
                        <span>${r.cantidad}</span>
                        <button type="button" data-sumar="${p.id}" aria-label="Una pieza más" ${r.cantidad >= p.stock ? "disabled" : ""}>+</button>
                    </div>
                    <strong class="carrito-subtotal">${dinero(subtotal)}</strong>
                    <button type="button" class="quitar-fila" data-quitar="${p.id}" aria-label="Quitar ${escapar(p.nombre)}">✕</button>
                </li>`;
        }).join("");

        paginaCarrito.innerHTML = avisosHTML + `
            <div class="carrito">
                <ul class="carrito-lista">${renglones}</ul>
                <aside class="carrito-resumen" aria-label="Resumen del pedido">
                    <div class="carrito-total"><span>Total</span><strong>${dinero(total)}</strong></div>
                    <span class="contador">${piezas} ${piezas === 1 ? "pieza" : "piezas"}</span>
                    <div class="campo">
                        <label for="carrito-notas">Notas para la tienda (opcional)</label>
                        <textarea id="carrito-notas" rows="2" maxlength="255" placeholder="Ej. Paso a recogerlo el sábado">${escapar(notas)}</textarea>
                    </div>
                    ${leerIdLogin()
                        ? `<button class="boton" id="hacer-pedido">Hacer pedido</button>`
                        : `<a class="boton" href="${enlaceLogin()}">Inicia sesión para pedir</a>`}
                    <p class="mensaje-error" id="carrito-error"></p>
                </aside>
            </div>`;
    }

    // Botones − + ✕ y "Hacer pedido" (se escuchan en la página porque se vuelve a dibujar)
    paginaCarrito.addEventListener("click", async e => {
        const boton = e.target.closest("button");
        if (!boton) return;
        const carrito = leerCarrito();
        if (boton.dataset.sumar || boton.dataset.restar || boton.dataset.quitar) {
            const id = Number(boton.dataset.sumar || boton.dataset.restar || boton.dataset.quitar);
            const renglon = carrito.find(r => r.id_producto === id);
            if (!renglon) {   // lo quitaron en otra pestaña: solo se vuelve a dibujar
                dibujar();
                return;
            }
            if (boton.dataset.sumar) renglon.cantidad++;
            if (boton.dataset.restar) renglon.cantidad--;
            guardarCarrito(boton.dataset.quitar ? carrito.filter(r => r !== renglon) : carrito);
            dibujar();
            return;
        }
        if (boton.id !== "hacer-pedido") return;

        boton.disabled = true;
        boton.textContent = "Enviando pedido…";
        try {
            const nueva = await pedirAPI("/ordenes", {
                method: "POST",
                body: JSON.stringify({
                    tipo: "Venta",
                    observaciones: notas.trim() || null,
                    productos: carrito.map(r => ({ id_producto: r.id_producto, cantidad: r.cantidad })),   // el precio lo pone la tienda
                }),
            });
            guardarCarrito([]);
            guardarNotas("");
            location.href = "ordenes.html?ver=" + nueva.id;   // se abre el pedido que acabas de hacer
        } catch (error) {
            document.getElementById("carrito-error").textContent = error.message;
            boton.disabled = false;
            boton.textContent = "Hacer pedido";
        }
    });

    // Las notas se guardan mientras escribes, para no perderlas al cambiar una cantidad
    paginaCarrito.addEventListener("input", e => {
        if (e.target.id !== "carrito-notas") return;
        notas = e.target.value;
        guardarNotas(notas);
    });

    window.addEventListener("sesioncambiada", () => {
        if (!usaCarrito()) location.reload();
        else dibujar();
    });
    // Si cambias el carrito en otra pestaña, esta página se actualiza sola
    window.addEventListener("storage", e => { if (e.key === "carrito") dibujar(); });
    dibujar();
}

// ===== Contacto (contacto.html): datos de la tienda → GET /api/soporte =====
const listaContacto = document.getElementById("lista-contacto");

if (listaContacto) {
    cargarContacto();
}

async function cargarContacto() {
    let contactos;
    try {
        contactos = await pedirAPI("/soporte");
    } catch (error) {
        listaContacto.innerHTML = `<li><small>Error</small><span>${escapar(error.message)}</span></li>`;
        return;
    }

    let filas = "";
    const vistos = new Set();
    for (const c of contactos) {
        // Si hay dos contactos iguales en la base de datos, se muestra solo uno
        const clave = [c.correo, c.telefono, c.direccion, c.horario].join("|");
        if (vistos.has(clave)) continue;
        vistos.add(clave);

        if (c.correo) filas += `<li><small>Correo</small><a href="mailto:${escapar(c.correo)}">${escapar(c.correo)}</a></li>`;
        if (c.telefono) filas += `<li><small>Teléfono</small><a href="tel:${escapar(c.telefono.replace(/[^0-9+]/g, ""))}">${escapar(c.telefono)}</a></li>`;
        if (c.direccion) filas += `<li><small>Dirección</small><span>${escapar(c.direccion)}</span></li>`;
        if (c.horario) filas += `<li><small>Horario</small><span>${escapar(c.horario)}</span></li>`;
    }
    if (filas === "") filas = `<li><span>Todavía no hay datos de contacto.</span></li>`;
    listaContacto.innerHTML = filas;
}

// ===== Formulario de contacto (contacto.html) → empieza una conversación del chat =====
const formContacto = document.getElementById("form-contacto");

if (formContacto) {
    const asunto = document.getElementById("asunto");
    const mensaje = document.getElementById("mensaje");
    const aviso = document.getElementById("aviso-contacto");
    const botonEnviar = document.getElementById("enviar-contacto");

    // Lo que se ve depende de quién inició sesión: solo el Cliente escribe desde aquí
    function pintarContacto() {
        document.getElementById("campos-contacto").hidden = !esCliente();
        if (esCliente()) {
            aviso.innerHTML = `Te contestamos por chat. Tus conversaciones están en <a href="mensajes.html">Mensajes</a>.`;
        } else if (leerRol() === "Almacenista") {
            aviso.textContent = "El chat de los clientes lo atienden el Administrador y los Empleados.";
        } else if (leerUsuario()) {
            aviso.innerHTML = `Los mensajes de los clientes se contestan en <a href="mensajes.html">Mensajes</a>.`;
        } else {
            aviso.innerHTML = `Para escribirnos, <a href="${enlaceLogin()}">inicia sesión</a> o crea tu cuenta. Te contestamos aquí mismo, por chat.`;
        }
    }
    pintarContacto();
    window.addEventListener("sesioncambiada", pintarContacto);

    formContacto.addEventListener("submit", async e => {
        e.preventDefault();
        const todoOk = [
            marcarError(asunto, asunto.value ? "" : "Elige un asunto"),
            marcarError(mensaje, mensaje.value.trim() ? "" : "Escribe tu mensaje"),
        ].every(Boolean);
        if (!todoOk) return;

        botonEnviar.disabled = true;
        try {
            const conversacion = await pedirAPI("/conversaciones", {
                method: "POST",
                body: JSON.stringify({ asunto: asunto.value, mensaje: mensaje.value.trim() }),
            });
            location.href = "mensajes.html?conversacion=" + conversacion.id;   // se abre el chat
        } catch (error) {
            marcarError(mensaje, error.message);
            botonEnviar.disabled = false;
        }
    });
}


// ===== Chat de soporte (mensajes.html) → /api/conversaciones =====
// El Cliente ve sus conversaciones. El Administrador y los Empleados ven las de todos y contestan.
const chat = document.getElementById("chat");
const PERSONAL_DE_SOPORTE = ["Administrador", "Empleado"];   // igual que en el microservicio de Soporte
const CADA_CUANTO = 5000;                                     // cada 5 segundos se buscan mensajes nuevos

if (chat) {
    iniciarChat();
    // Si alguien entra o sale, la página se vuelve a cargar con lo que le toca ver
    window.addEventListener("sesioncambiada", () => location.reload());
}

function iniciarChat() {
    const lista = document.getElementById("lista-conversaciones");
    const filtro = document.getElementById("filtro-conversaciones");
    const asunto = document.getElementById("chat-asunto");
    const datos = document.getElementById("chat-datos");
    const acciones = document.getElementById("chat-acciones");
    const cajaMensajes = document.getElementById("chat-mensajes");
    const formMensaje = document.getElementById("form-mensaje");
    const texto = document.getElementById("texto-mensaje");
    const botonEnviar = document.getElementById("enviar-mensaje");
    const errorChat = document.getElementById("chat-error");
    const idLogin = leerIdLogin();
    const esPersonal = PERSONAL_DE_SOPORTE.includes(leerRol());

    let conversaciones = [];
    let abierta = null;            // la conversación que se está viendo
    let estadoElegido = "Abierta"; // filtro de la lista: "Abierta" o "Cerrada"

    if (!idLogin) {
        chat.innerHTML = `<div class="vacio"><h2>Inicia sesión para ver tus mensajes</h2>
            <p>Aquí platicas con la refaccionaria.</p><a class="boton" href="${enlaceLogin()}">Iniciar sesión</a></div>`;
        return;
    }
    if (!esCliente() && !esPersonal) {
        chat.innerHTML = `<div class="vacio"><h2>El chat lo atienden el Administrador y los Empleados</h2>
            <p>Con tu rol no puedes ver los mensajes de los clientes.</p></div>`;
        return;
    }
    document.getElementById("subtitulo-mensajes").textContent = esPersonal
        ? "Mensajes de los clientes. Contesta y cierra la conversación cuando quede resuelta."
        : "Tus conversaciones con la refaccionaria. Te contestamos aquí mismo.";
    document.getElementById("boton-nueva-conversacion").hidden = esPersonal;

    async function cargarLista() {
        try {
            conversaciones = await pedirAPI("/conversaciones");
        } catch (error) {
            lista.innerHTML = `<li class="lista-vacia">${escapar(error.message)}</li>`;
            return;
        }
        pintarLista();
    }

    function pintarLista() {
        const visibles = conversaciones.filter(c => c.estado === estadoElegido);
        if (visibles.length === 0) {
            lista.innerHTML = `<li class="lista-vacia">${estadoElegido === "Abierta" ? "No hay conversaciones abiertas" : "No hay conversaciones cerradas"}</li>`;
            return;
        }
        lista.innerHTML = visibles.map(c => {
            const ultimo = c.ultimo_mensaje;
            // Al personal le avisa qué falta contestar; al cliente, cuándo ya le contestaron
            let aviso = "";
            if (c.estado === "Abierta" && esPersonal && c.esperando_respuesta) aviso = `<span class="insignia pendiente">Sin contestar</span>`;
            if (c.estado === "Abierta" && !esPersonal && !c.esperando_respuesta) aviso = `<span class="insignia completada">Respondido</span>`;
            return `<li><button class="conversacion" data-id="${c.id}" aria-current="${abierta !== null && abierta.id === c.id}">
                <span class="conversacion-arriba"><strong>${escapar(c.asunto)}</strong>${aviso}</span>
                <small>${esPersonal ? escapar(c.cliente) + " · " : ""}${ultimo ? fechaHora(ultimo.fecha) : ""}</small>
                <span class="conversacion-texto">${ultimo ? escapar(ultimo.texto) : ""}</span>
            </button></li>`;
        }).join("");
    }

    async function abrir(id) {
        let conversacion;
        try {
            conversacion = await pedirAPI(`/conversaciones/${id}`);
        } catch (error) {
            if (error.estado === 404 && abierta !== null && abierta.id === id) {
                cerrarVista();   // la eliminaron mientras la veías
                errorChat.textContent = "Esa conversación ya no existe.";
                return;
            }
            errorChat.textContent = error.message;
            return;
        }
        errorChat.textContent = "";
        // Solo se vuelven a dibujar los mensajes si algo cambió (así no te mueve mientras lees)
        const cambio = abierta === null || abierta.id !== conversacion.id || abierta.estado !== conversacion.estado
            || abierta.mensajes.length !== conversacion.mensajes.length;
        abierta = conversacion;
        chat.classList.add("viendo");   // en el celular se esconde la lista y se ve el chat
        history.replaceState(null, "", "?conversacion=" + id);
        if (cambio) pintarConversacion();
        pintarLista();
    }

    function pintarConversacion() {
        const c = abierta;
        asunto.textContent = c.asunto;
        datos.innerHTML = (esPersonal ? escapar(c.cliente) + " · " : "") + insigniaEstado(c.estado);
        acciones.innerHTML = !esPersonal ? "" : `
            <button class="boton boton-borde boton-chico" data-estado="${c.estado === "Abierta" ? "Cerrada" : "Abierta"}">
                ${c.estado === "Abierta" ? "Cerrar" : "Reabrir"}</button>
            ${esAdministrador() ? `<button class="boton boton-chico boton-peligro" data-eliminar>Eliminar</button>` : ""}`;
        formMensaje.hidden = c.estado !== "Abierta";

        cajaMensajes.innerHTML = c.mensajes.map(m => {
            // A la derecha va "tu lado": el cliente ve ahí lo suyo; el personal, lo que contestó la tienda
            const deMiLado = esPersonal ? m.rol !== "Cliente" : m.id_login === idLogin;
            const quien = m.id_login === idLogin ? "Tú" : escapar(m.autor) + (m.rol !== "Cliente" ? " · " + m.rol : "");
            return `<div class="burbuja ${deMiLado ? "mia" : ""}">
                <small>${quien}</small>
                <p>${escapar(m.texto)}</p>
                <time>${fechaHora(m.fecha)}</time>
            </div>`;
        }).join("") + (c.estado === "Cerrada" ? `<p class="chat-aviso">Esta conversación está cerrada.</p>` : "");
        cajaMensajes.scrollTop = cajaMensajes.scrollHeight;   // hasta el mensaje más nuevo
    }

    function cerrarVista() {
        abierta = null;
        chat.classList.remove("viendo");
        history.replaceState(null, "", "mensajes.html");
        asunto.textContent = "Elige una conversación";
        datos.innerHTML = acciones.innerHTML = "";
        cajaMensajes.innerHTML = `<p class="chat-vacio">Elige una conversación de la lista para ver los mensajes.</p>`;
        formMensaje.hidden = true;
        pintarLista();
    }

    filtro.addEventListener("click", e => {
        const chip = e.target.closest(".chip");
        if (!chip) return;
        estadoElegido = chip.dataset.estado;
        filtro.querySelectorAll(".chip").forEach(c => c.setAttribute("aria-pressed", String(c === chip)));
        pintarLista();
    });

    lista.addEventListener("click", e => {
        const boton = e.target.closest(".conversacion");
        if (boton) abrir(Number(boton.dataset.id));
    });

    document.getElementById("chat-volver").addEventListener("click", cerrarVista);

    formMensaje.addEventListener("submit", async e => {
        e.preventDefault();
        if (!texto.value.trim()) return;
        botonEnviar.disabled = true;
        try {
            abierta = await pedirAPI(`/conversaciones/${abierta.id}/mensajes`, {
                method: "POST",
                body: JSON.stringify({ texto: texto.value.trim() }),
            });
            texto.value = "";
            errorChat.textContent = "";
            pintarConversacion();
            cargarLista();
        } catch (error) {
            errorChat.textContent = error.message;
        } finally {
            botonEnviar.disabled = false;
            texto.focus();
        }
    });

    // En la computadora, Enter manda el mensaje y Shift+Enter hace un salto de línea
    texto.addEventListener("keydown", e => {
        if (e.key === "Enter" && !e.shiftKey && !e.isComposing && matchMedia("(pointer: fine)").matches) {
            e.preventDefault();
            formMensaje.requestSubmit();
        }
    });

    // Cerrar / Reabrir (personal) y Eliminar (solo el Administrador)
    acciones.addEventListener("click", async e => {
        const boton = e.target.closest("button");
        if (!boton) return;
        if (boton.hasAttribute("data-eliminar")
            && !confirm(`¿Eliminar la conversación "${abierta.asunto}" con todos sus mensajes?`)) return;
        boton.disabled = true;
        try {
            if (boton.hasAttribute("data-eliminar")) {
                await pedirAPI(`/conversaciones/${abierta.id}`, { method: "DELETE" });
                cerrarVista();
            } else {
                abierta = await pedirAPI(`/conversaciones/${abierta.id}/estado`, {
                    method: "PATCH",
                    body: JSON.stringify({ estado: boton.dataset.estado }),
                });
                pintarConversacion();
            }
            cargarLista();
        } catch (error) {
            errorChat.textContent = error.message;
            boton.disabled = false;
        }
    });

    // Cada 5 segundos se buscan mensajes nuevos (si la pestaña está a la vista)
    setInterval(() => {
        if (document.hidden) return;
        cargarLista();
        if (abierta) abrir(abierta.id);
    }, CADA_CUANTO);

    cargarLista();
    // Si llegas desde Contacto (mensajes.html?conversacion=5) se abre ese chat
    const desdeEnlace = Number(new URLSearchParams(location.search).get("conversacion"));
    if (desdeEnlace) abrir(desdeEnlace);
}

// ===== Órdenes (ordenes.html) → /api/ordenes y /api/inventario/movimientos =====
// Compra = la mercancía ENTRA (sube el stock) · Venta = la mercancía SALE (baja el stock)
// El stock solo se mueve cuando la orden pasa a "Completada".
const listaOrdenes = document.getElementById("lista-ordenes");

// A qué estado puede pasar una orden (igual que en el microservicio de Órdenes)
const SIGUIENTES_ESTADOS = {
    "Pendiente": ["En Proceso", "Completada", "Cancelada"],
    "En Proceso": ["Completada", "Cancelada"],
    "Completada": [],
    "Cancelada": [],
};

function numeroOrden(id) {
    return "#" + String(id).padStart(4, "0");
}

function fechaHora(texto) {
    // "2026-10-22T14:30:12.123000" → "22 oct 2026, 14:30"
    const [dia, hora] = texto.split("T");
    const fecha = new Date(dia + "T00:00:00").toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric" });
    return `${fecha}, ${hora.slice(0, 5)}`;
}

function insigniaTipo(tipo) {
    return tipo === "Compra"
        ? `<span class="insignia entrada">↓ Entrada</span>`
        : `<span class="insignia salida">↑ Salida</span>`;
}

function insigniaEstado(estado) {
    // "En Proceso" → clase "en-proceso"
    return `<span class="insignia ${estado.toLowerCase().replace(" ", "-")}">${escapar(estado)}</span>`;
}

if (listaOrdenes) {
    iniciarOrdenes();
    // Si alguien sale, la página se vuelve a cargar:
    // así no se quedan a la vista las órdenes de quien ya salió
    window.addEventListener("sesioncambiada", () => location.reload());
}

function iniciarOrdenes() {
    let tipoElegido = "";          // "" = todas, "Compra" o "Venta"
    let estadoElegido = "";        // "" = todos, "En Proceso" o "Cancelada"
    let catalogo = [];             // productos para el formulario de nueva orden
    const contador = document.getElementById("contador-ordenes");
    const filtro = document.getElementById("filtro-tipo");
    const dialogoDetalle = document.getElementById("dialogo-detalle");
    const dialogoNueva = document.getElementById("dialogo-nueva");
    const acciones = document.getElementById("detalle-acciones");
    const errorDetalle = document.getElementById("detalle-error");
    const formOrden = document.getElementById("form-orden");
    const filas = document.getElementById("filas-productos");
    const errorOrden = document.getElementById("orden-error");
    const botonGuardar = document.getElementById("guardar-orden");

    // Botones ✕ y "Cancelar" de las dos ventanas
    document.querySelectorAll("[data-cerrar]").forEach(boton =>
        boton.addEventListener("click", () => boton.closest("dialog").close()));

    // ----- Lista de órdenes -----
    async function cargarOrdenes() {
        contador.textContent = "Cargando órdenes…";
        try {
            const filtros = new URLSearchParams();
            if (tipoElegido) filtros.set("tipo", tipoElegido);
            if (estadoElegido) filtros.set("estado", estadoElegido);
            let ordenes = await pedirAPI("/ordenes?" + filtros);
            // En Entradas y Salidas no van las canceladas: esas tienen su propio botón
            if (tipoElegido) ordenes = ordenes.filter(o => o.estado !== "Cancelada");
            contador.textContent = `${ordenes.length} ${ordenes.length === 1 ? "orden" : "órdenes"}`;
            if (ordenes.length === 0) {
                listaOrdenes.innerHTML = estadoElegido === "Cancelada"
                    ? `<div class="vacio"><h2>No hay órdenes canceladas</h2><p>Aquí aparecen las órdenes que cancela el Administrador.</p></div>`
                    : estadoElegido === "En Proceso"
                    ? `<div class="vacio"><h2>No hay órdenes en proceso</h2><p>Aquí aparecen las órdenes que ya se empezaron y todavía no se completan.</p></div>`
                    : `<div class="vacio"><h2>No hay órdenes</h2><p>Crea la primera con “+ Nueva orden”.</p></div>`;
                return;
            }
            listaOrdenes.innerHTML = ordenes.map(o => `
                <article class="orden">
                    <span class="orden-numero">${numeroOrden(o.id)}</span>
                    <div class="orden-info">
                        ${insigniaTipo(o.tipo)} ${insigniaEstado(o.estado)}
                        <small>${fechaHora(o.fecha)} · ${o.detalles.length} ${o.detalles.length === 1 ? "producto" : "productos"}${o.observaciones ? " · " + escapar(o.observaciones) : ""}</small>
                    </div>
                    <span class="orden-total">${dinero(o.total)}</span>
                    <button class="boton boton-borde boton-chico" data-ver="${o.id}">Ver detalle</button>
                </article>
            `).join("");
        } catch (error) {
            contador.textContent = "";
            mostrarError(listaOrdenes, error.message);
        }
    }

    // ----- Movimientos de inventario (entradas y salidas) -----
    async function cargarMovimientos() {
        if (esCliente()) return;   // el inventario es información interna de la tienda
        const cuerpo = document.querySelector("#tabla-movimientos tbody");
        try {
            const movimientos = await pedirAPI("/inventario/movimientos"  );
            cuerpo.innerHTML = movimientos.length === 0
                ? `<tr><td colspan="5">Todavía no hay movimientos. Se registran al completar una orden.</td></tr>`
                : movimientos.slice(0, 15).map(m => `
                    <tr>
                        <td>${fechaHora(m.fecha)}</td>
                        <td>${escapar(m.producto)}</td>
                        <td>${m.tipo === "Entrada" ? `<span class="insignia entrada">↓ Entrada</span>` : `<span class="insignia salida">↑ Salida</span>`}</td>
                        <td class="numero">${m.cantidad}</td>
                        <td>${m.id_orden ? numeroOrden(m.id_orden) : "—"}</td>
                    </tr>`).join("");
        } catch (error) {
            cuerpo.innerHTML = `<tr><td colspan="5">${escapar(error.message)}</td></tr>`;
        }
    }

    // ----- Detalle de una orden -----
    async function verDetalle(id) {
        const cuerpo = document.getElementById("detalle-cuerpo");
        errorDetalle.textContent = "";
        try {
            const o = await pedirAPI("/ordenes/" + id );
            document.getElementById("detalle-titulo").textContent = `Orden ${numeroOrden(o.id)}`;
            cuerpo.innerHTML = `
                <div class="detalle-datos">
                    ${insigniaTipo(o.tipo)} ${insigniaEstado(o.estado)}
                    <span>${fechaHora(o.fecha)}</span>
                    ${o.observaciones ? `<span>${escapar(o.observaciones)}</span>` : ""}
                </div>
                <div class="tabla-envoltura">
                    <table class="tabla">
                        <thead><tr><th>Producto</th><th class="numero">Cantidad</th><th class="numero">Precio</th><th class="numero">Subtotal</th></tr></thead>
                        <tbody>
                            ${o.detalles.map(d => `<tr>
                                <td>${escapar(d.producto)}</td>
                                <td class="numero">${d.cantidad}</td>
                                <td class="numero">${dinero(d.precio_unitario)}</td>
                                <td class="numero">${dinero(d.subtotal)}</td>
                            </tr>`).join("")}
                        </tbody>
                        <tfoot><tr><td colspan="3">Total</td><td class="numero">${dinero(o.total)}</td></tr></tfoot>
                    </table>
                </div>`;

            // Botones para avanzar el estado (solo con sesión iniciada)
            const siguientes = SIGUIENTES_ESTADOS[o.estado] || [];
            if (siguientes.length === 0) {
                acciones.innerHTML = `<span class="contador">Esta orden ya está ${o.estado.toLowerCase()}.</span>`;
            } else if (!leerIdLogin()) {
                acciones.innerHTML = `<span class="contador">Inicia sesión para cambiar el estado.</span>`;
            } else if (esCliente()) {
                // El cliente no mueve estados: la tienda procesa su pedido
                acciones.innerHTML = `<span class="contador">La tienda está revisando tu pedido.</span>`;
            } else {
                // Cada rol solo ve los botones que puede usar (el microservicio también lo revisa)
                const permitidos = siguientes.filter(estado =>
                    estado === "Cancelada" ? esAdministrador() : puedeAvanzar(o.tipo));
                acciones.innerHTML = permitidos.map(estado => {
                    const estilo = estado === "Cancelada" ? "boton-peligro" : estado === "Completada" ? "" : "boton-borde";
                    const texto = estado === "Cancelada" ? "Cancelar orden" : "Pasar a " + estado;
                    return `<button class="boton ${estilo}" data-estado="${estado}" data-orden="${o.id}">${texto}</button>`;
                }).join("");
                if (permitidos.length === 0) {
                    acciones.innerHTML = `<span class="contador">Un ${leerRol()} no puede cambiar órdenes de ${o.tipo}.</span>`;
                } else if (!esAdministrador()) {
                    acciones.innerHTML += `<span class="contador">Solo un Administrador puede cancelar.</span>`;
                }
            }
        } catch (error) {
            cuerpo.innerHTML = "";
            acciones.innerHTML = "";
            errorDetalle.textContent = error.message;
        }
        if (!dialogoDetalle.open) dialogoDetalle.showModal();
    }

    // Cambiar el estado: al pasar a "Completada" el microservicio mueve el stock
    acciones.addEventListener("click", async e => {
        const boton = e.target.closest("[data-estado]");
        if (!boton) return;
        // Cancelar no se puede deshacer: se pregunta antes
        if (boton.dataset.estado === "Cancelada"
            && !confirm(`¿Cancelar la orden ${numeroOrden(boton.dataset.orden)}? Ya no se podrá completar ni reabrir.`)) return;
        acciones.querySelectorAll("button").forEach(b => b.disabled = true);
        try {
            await pedirAPI(`/ordenes/${boton.dataset.orden}/estado`, {
                method: "PATCH",
                body: JSON.stringify({ estado: boton.dataset.estado }),
            });
            await verDetalle(boton.dataset.orden);
            cargarOrdenes();
            cargarMovimientos();
        } catch (error) {
            errorDetalle.textContent = error.message;   // ej. "No hay suficiente stock de ..."
            acciones.querySelectorAll("button").forEach(b => b.disabled = false);
        }
    });

    listaOrdenes.addEventListener("click", e => {
        const boton = e.target.closest("[data-ver]");
        if (boton) verDetalle(boton.dataset.ver);
    });

    filtro.addEventListener("click", e => {
        const chip = e.target.closest(".chip");
        if (!chip) return;
        tipoElegido = chip.dataset.tipo || "";
        estadoElegido = chip.dataset.estado || "";
        filtro.querySelectorAll(".chip").forEach(c => c.setAttribute("aria-pressed", c === chip));
        cargarOrdenes();
    });

    // ----- Nueva orden -----
    function agregarFila(idProducto = null, cantidad = 1) {
        const fila = document.createElement("div");
        fila.className = "fila-producto";
        fila.innerHTML = `
            <select aria-label="Producto">
                ${catalogo.map(p => `<option value="${p.id}">${escapar(p.nombre)} (stock ${p.stock})</option>`).join("")}
            </select>
            <input type="number" class="cantidad-fila" min="1" step="1" value="1" aria-label="Cantidad" inputmode="numeric">
            <input type="number" class="precio-fila" min="0" step="0.01" aria-label="Precio unitario" inputmode="decimal">
            <button type="button" class="quitar-fila" aria-label="Quitar producto">✕</button>`;
        filas.append(fila);
        if (idProducto) fila.querySelector("select").value = idProducto;
        fila.querySelector(".cantidad-fila").value = cantidad;
        ponerPrecio(fila);
        actualizarTotal();
    }

    // Al elegir un producto se sugiere su precio actual. En una venta lleva el descuento
    // de su promoción, igual que en el microservicio. Solo quien puede cambiar el precio
    // (el Administrador en ventas; Administrador y Almacenista en compras) lo puede editar
    function ponerPrecio(fila) {
        const tipo = document.getElementById("orden-tipo").value;
        fila.querySelector(".precio-fila").readOnly = !(PUEDEN_CAMBIAR_PRECIO[tipo] || []).includes(leerRol());
        const producto = catalogo.find(p => p.id === Number(fila.querySelector("select").value));
        if (!producto) {
            fila.querySelector(".precio-fila").value = 0;
            return;
        }
        const promo = document.getElementById("orden-tipo").value === "Venta" ? promocionDe(producto.id) : null;
        fila.querySelector(".precio-fila").value = promo ? conDescuento(producto.precio, promo.descuento) : producto.precio;
    }

    // Si el precio se deja vacío va null (y no 0): así el microservicio pone el precio actual
    function leerFilas() {
        return [...filas.querySelectorAll(".fila-producto")].map(fila => {
            const precio = fila.querySelector(".precio-fila").value.trim();
            return {
                id_producto: Number(fila.querySelector("select").value),
                cantidad: Number(fila.querySelector(".cantidad-fila").value),
                precio_unitario: precio === "" ? null : Number(precio),
            };
        });
    }

    function actualizarTotal() {
        const total = leerFilas().reduce((suma, p) => suma + (p.cantidad || 0) * (p.precio_unitario || 0), 0);
        document.getElementById("orden-total").textContent = dinero(total);
    }

    filas.addEventListener("change", e => {
        if (e.target.tagName === "SELECT") ponerPrecio(e.target.closest(".fila-producto"));
        actualizarTotal();
    });
    filas.addEventListener("input", actualizarTotal);
    filas.addEventListener("click", e => {
        if (!e.target.closest(".quitar-fila")) return;
        e.target.closest(".fila-producto").remove();
        actualizarTotal();
    });
    document.getElementById("agregar-fila").addEventListener("click", () => agregarFila());

    // Al cambiar entre Venta y Compra se vuelven a sugerir los precios
    document.getElementById("orden-tipo").addEventListener("change", () => {
        filas.querySelectorAll(".fila-producto").forEach(ponerPrecio);
        actualizarTotal();
    });

    // pedido = { id_producto, cantidad, tipo } cuando llegas desde el detalle de un producto
    async function abrirNuevaOrden(pedido = null) {
        // Para crear órdenes hay que iniciar sesión (la orden guarda quién la hizo)
        if (!leerIdLogin()) {
            guardarUsuario(null);
            location.href = enlaceLogin();
            return;
        }
        if (catalogo.length === 0) {
            try {
                [catalogo, promociones] = await Promise.all([
                    pedirAPI("/productos"),
                    pedirAPI("/dashboard"),   // para sugerir el precio con descuento
                ]);
            } catch (error) {
                contador.textContent = error.message;
                return;
            }
        }
        formOrden.reset();
        // Cada rol solo puede elegir los tipos de orden que tiene permitidos
        const selectTipo = document.getElementById("orden-tipo");
        [...selectTipo.options].forEach(opcion => {
            const tipo = opcion.value;
            opcion.disabled = !puedeCrear(tipo);
            opcion.hidden = esCliente() && !puedeCrear(tipo);   // el cliente ni siquiera ve las compras
            opcion.textContent = !puedeCrear(tipo) ? `${tipo}: solo ${PUEDEN_CREAR[tipo].join(", ")}`
                : tipo === "Venta" ? "Venta: la mercancía sale (baja el stock)"
                : "Compra: la mercancía entra (sube el stock)";
        });
        selectTipo.value = [...selectTipo.options].find(opcion => !opcion.disabled).value;
        if (pedido && puedeCrear(pedido.tipo)) selectTipo.value = pedido.tipo;
        filas.innerHTML = "";
        errorOrden.textContent = "";
        if (pedido) agregarFila(pedido.id_producto, pedido.cantidad);
        else agregarFila();
        dialogoNueva.showModal();
    }

    document.getElementById("boton-nueva-orden").addEventListener("click", () => abrirNuevaOrden());

    formOrden.addEventListener("submit", async e => {
        e.preventDefault();
        const productosOrden = leerFilas();
        const ids = productosOrden.map(p => p.id_producto);

        let problema = "";
        if (productosOrden.length === 0) problema = "Agrega al menos un producto.";
        else if (productosOrden.some(p => !Number.isInteger(p.cantidad) || p.cantidad < 1)) problema = "La cantidad debe ser un número entero de 1 o más.";
        else if (productosOrden.some(p => p.precio_unitario !== null && !(p.precio_unitario >= 0))) problema = "El precio no puede ser negativo.";
        else if (new Set(ids).size !== ids.length) problema = "Repetiste un producto: mejor aumenta su cantidad.";
        if (!problema && esCliente()) {
            // Igual que en el carrito: el cliente no pide más piezas de las que hay
            for (const p of productosOrden) {
                const producto = catalogo.find(c => c.id === p.id_producto);
                if (producto && p.cantidad > producto.stock) {
                    problema = producto.stock === 0 ? `${producto.nombre} está agotado.`
                        : `De ${producto.nombre} solo hay ${producto.stock} en existencia.`;
                    break;
                }
            }
        }
        errorOrden.textContent = problema;
        if (problema) return;

        botonGuardar.disabled = true;
        botonGuardar.textContent = "Guardando…";
        try {
            const observaciones = document.getElementById("orden-observaciones").value.trim();
            const nueva = await pedirAPI("/ordenes", {
                method: "POST",
                body: JSON.stringify({
                    tipo: document.getElementById("orden-tipo").value,
                    observaciones: observaciones || null,
                    productos: productosOrden,
                }),
            });
            dialogoNueva.close();
            await cargarOrdenes();
            verDetalle(nueva.id);   // se abre para que puedas completarla
        } catch (error) {
            errorOrden.textContent = error.message;
        } finally {
            botonGuardar.disabled = false;
            botonGuardar.textContent = "Guardar orden";
        }
    });

    // Sin sesión no hay órdenes que mostrar: el microservicio pide saber quién consulta
    if (!leerIdLogin()) {
        document.getElementById("boton-nueva-orden").hidden = true;
        filtro.hidden = true;
        document.getElementById("seccion-movimientos").hidden = true;
        listaOrdenes.innerHTML = `<div class="vacio"><h2>Inicia sesión para ver las órdenes</h2>
            <p>Los clientes ven aquí sus pedidos y el personal, todas las órdenes.</p><a class="boton" href="${enlaceLogin()}">Iniciar sesión</a></div>`;
        return;
    }

    // El cliente ve la página como "Mis pedidos": sin filtros de compras ni inventario
    if (esCliente()) {
        document.querySelector(".cabecera-pagina .etiqueta-seccion").textContent = "Tu cuenta";
        document.querySelector(".cabecera-pagina h1").textContent = "Mis pedidos";
        document.querySelector(".subtitulo-pagina").textContent = "Tus pedidos a la refaccionaria y su estado.";
        document.getElementById("boton-nueva-orden").textContent = "+ Nuevo pedido";
        filtro.hidden = true;
        document.getElementById("seccion-movimientos").hidden = true;
    }

    cargarOrdenes();
    cargarMovimientos();

    // Si llegas desde el detalle de un producto (detalle.html), se abre la nueva orden con ese producto
    const pedido = new URLSearchParams(location.search);
    if (pedido.get("ver")) {
        // Desde el carrito: se abre el pedido que acabas de hacer
        history.replaceState(null, "", "ordenes.html");
        verDetalle(Number(pedido.get("ver")));
    }
    if (pedido.get("pedir")) {
        history.replaceState(null, "", "ordenes.html");   // para que al recargar no se vuelva a abrir
        abrirNuevaOrden({
            id_producto: Number(pedido.get("pedir")),
            cantidad: Number(pedido.get("cantidad")) || 1,
            tipo: pedido.get("tipo") === "Compra" ? "Compra" : "Venta",
        });
    }

}
// ===== Almacén (almacen.html): el stock de todos los productos =====
// Solo para el Almacenista y el Administrador. Usa /api/productos, /api/ordenes y /api/inventario/movimientos
const paginaAlmacen = document.getElementById("almacen");
const POCAS_PIEZAS = 8;   // igual que "Últimas 8" en el catálogo: con 8 o menos hay que surtir

if (paginaAlmacen) {
    iniciarAlmacen();
    // Si alguien entra o sale, la página se vuelve a cargar con lo que le toca ver
    window.addEventListener("sesioncambiada", () => location.reload());
}

async function iniciarAlmacen() {
    const resumen = document.getElementById("resumen-almacen");
    const cuerpo = document.getElementById("tabla-almacen");
    const contador = document.getElementById("contador-almacen");
    const buscar = document.getElementById("buscar-almacen");
    const filtro = document.getElementById("filtro-almacen");
    const dialogoMovimientos = document.getElementById("dialogo-movimientos");

    document.querySelectorAll("[data-cerrar]").forEach(boton =>
        boton.addEventListener("click", () => boton.closest("dialog").close()));

    if (!leerIdLogin()) {
        paginaAlmacen.innerHTML = `<div class="vacio"><h2>Inicia sesión para ver el almacén</h2>
            <p>Esta sección es para el Almacenista y el Administrador.</p><a class="boton" href="${enlaceLogin()}">Iniciar sesión</a></div>`;
        document.getElementById("boton-ir-ordenes").hidden = true;
        return;
    }
    if (!veAlmacen()) {
        paginaAlmacen.innerHTML = `<div class="vacio"><h2>El almacén lo ven el Almacenista y el Administrador</h2>
            <p>Con tu rol no puedes ver el inventario de la tienda.</p><a class="boton" href="producto.html">Ver productos</a></div>`;
        document.getElementById("boton-ir-ordenes").hidden = true;
        return;
    }

    let filas = [];              // cada producto con lo que está por entrar y por salir
    let filtroElegido = "todos"; // "todos", "surtir" o "agotados"
    let orden = { campo: "stock", subiendo: true };   // primero lo que tiene menos piezas
    contador.textContent = "Cargando almacén…";

    try {
        const [lista, ordenes] = await Promise.all([
            pedirAPI("/productos"),
            pedirAPI("/ordenes")
        ]);
        // Lo que todavía no se mueve: compras y ventas Pendientes o En Proceso
        const porEntrar = {};
        const porSalir = {};
        ordenes.filter(o => o.estado === "Pendiente" || o.estado === "En Proceso").forEach(o => {
            const destino = o.tipo === "Compra" ? porEntrar : porSalir;
            o.detalles.forEach(d => destino[d.id_producto] = (destino[d.id_producto] || 0) + d.cantidad);
        });
        filas = lista.map(p => ({
            ...p,
            porEntrar: porEntrar[p.id] || 0,
            porSalir: porSalir[p.id] || 0,
            valor: Math.round(p.precio * p.stock * 100) / 100,
        }));
    } catch (error) {
        contador.textContent = "";
        mostrarError(paginaAlmacen, error.message);
        return;
    }

    // ----- Las tarjetas de arriba: los números importantes del almacén -----
    const piezas = filas.reduce((suma, p) => suma + p.stock, 0);
    const valor = filas.reduce((suma, p) => suma + p.valor, 0);
    const porSurtir = filas.filter(p => p.stock > 0 && p.stock <= POCAS_PIEZAS).length;
    const agotados = filas.filter(p => p.stock === 0).length;
    resumen.innerHTML = `
        <div class="tarjeta-dato"><small>Productos</small><strong>${filas.length}</strong></div>
        <div class="tarjeta-dato"><small>Piezas en almacén</small><strong>${piezas.toLocaleString("es-MX")}</strong></div>
        <div class="tarjeta-dato"><small>Valor del inventario</small><strong>${dinero(valor)}</strong></div>
        <button class="tarjeta-dato ${porSurtir ? "aviso" : ""}" data-ir="surtir"><small>Por surtir</small><strong>${porSurtir}</strong></button>
        <button class="tarjeta-dato ${agotados ? "peligro" : ""}" data-ir="agotados"><small>Agotados</small><strong>${agotados}</strong></button>`;

    // ----- La tabla -----
    function estadoDe(stock) {
        if (stock === 0) return `<span class="existencia agotado">Agotado</span>`;
        if (stock <= POCAS_PIEZAS) return `<span class="existencia pocas">Surtir</span>`;
        return `<span class="existencia hay">Bien</span>`;
    }

    // Compras que van a entrar (+) y ventas que van a salir (−). Si las ventas piden más
    // de lo que hay (contando lo que va a entrar), se avisa cuántas piezas faltan
    function porMover(p) {
        const partes = [];
        if (p.porEntrar) partes.push(`<span class="insignia entrada" title="Compras por completar">+${p.porEntrar}</span>`);
        if (p.porSalir) partes.push(`<span class="insignia salida" title="Ventas por completar">−${p.porSalir}</span>`);
        const faltan = p.porSalir - p.stock - p.porEntrar;
        if (faltan > 0) partes.push(`<span class="insignia faltan" title="Las ventas pendientes piden más de lo que hay">Faltan ${faltan}</span>`);
        return partes.length ? `<span class="por-mover">${partes.join("")}</span>` : "—";
    }

    function dibujar() {
        const texto = sinAcentos(buscar.value.trim());
        const visibles = filas.filter(p =>
            (sinAcentos(p.nombre).includes(texto) || codigo(p.id).toLowerCase().includes(texto)) &&
            (filtroElegido === "todos"
                || (filtroElegido === "surtir" && p.stock > 0 && p.stock <= POCAS_PIEZAS)
                || (filtroElegido === "agotados" && p.stock === 0))
        );
        visibles.sort((a, b) => {
            const resultado = orden.campo === "nombre" ? a.nombre.localeCompare(b.nombre, "es") : a[orden.campo] - b[orden.campo];
            return orden.subiendo ? resultado : -resultado;
        });
        document.querySelectorAll(".ordenar").forEach(boton => {
            const activo = boton.dataset.orden === orden.campo;
            boton.closest("th").setAttribute("aria-sort", activo ? (orden.subiendo ? "ascending" : "descending") : "none");
            boton.dataset.flecha = activo ? (orden.subiendo ? "↑" : "↓") : "";
        });

        contador.textContent = `${visibles.length} de ${filas.length} productos`;
        if (visibles.length === 0) {
            cuerpo.innerHTML = `<tr><td colspan="6">${filtroElegido === "agotados" && !texto ? "No hay productos agotados." : filtroElegido === "surtir" && !texto ? "No hay productos por surtir." : "Ningún producto coincide con la búsqueda."}</td></tr>`;
            return;
        }
        cuerpo.innerHTML = visibles.map(p => `
            <tr class="${p.stock === 0 ? "fila-agotado" : p.stock <= POCAS_PIEZAS ? "fila-pocas" : ""}">
                <td><a href="detalle.html?id=${p.id}" class="producto-almacen"><small>${codigo(p.id)}</small>${escapar(p.nombre)}</a></td>
                <td>${escapar(p.categoria)}</td>
                <td class="numero"><span class="existencia-numero">${p.stock}</span> ${estadoDe(p.stock)}</td>
                <td>${porMover(p)}</td>
                <td class="numero">${dinero(p.valor)}</td>
                <td class="acciones-almacen">
                    <button class="boton boton-borde boton-chico" data-movimientos="${p.id}">Movimientos</button>
                    <a class="boton boton-chico" href="ordenes.html?pedir=${p.id}&tipo=Compra">Surtir</a>
                </td>
            </tr>`).join("");
    }

    function elegirFiltro(valor) {
        filtroElegido = valor;
        filtro.querySelectorAll(".chip").forEach(c => c.setAttribute("aria-pressed", String(c.dataset.filtro === valor)));
        dibujar();
    }

    filtro.addEventListener("click", e => {
        const chip = e.target.closest(".chip");
        if (chip) elegirFiltro(chip.dataset.filtro);
    });
    // Las tarjetas "Por surtir" y "Agotados" también filtran la tabla
    resumen.addEventListener("click", e => {
        const tarjeta = e.target.closest("[data-ir]");
        if (tarjeta) elegirFiltro(tarjeta.dataset.ir);
    });
    buscar.addEventListener("input", dibujar);
    document.querySelector(".tabla-almacen thead").addEventListener("click", e => {
        const boton = e.target.closest(".ordenar");
        if (!boton) return;
        orden = { campo: boton.dataset.orden, subiendo: orden.campo === boton.dataset.orden ? !orden.subiendo : true };
        dibujar();
    });

    // ----- Movimientos de un producto (entradas y salidas que ya pasaron) -----
    cuerpo.addEventListener("click", async e => {
        const boton = e.target.closest("[data-movimientos]");
        if (!boton) return;
        const producto = filas.find(p => p.id === Number(boton.dataset.movimientos));
        const caja = document.getElementById("movimientos-cuerpo");
        document.getElementById("movimientos-titulo").textContent = producto.nombre;
        caja.innerHTML = `<p class="contador">Cargando movimientos…</p>`;
        dialogoMovimientos.showModal();
        try {
            const movimientos = await pedirAPI(`/inventario/movimientos?id_producto=${producto.id}`);
            const entradas = movimientos.filter(m => m.tipo === "Entrada").reduce((s, m) => s + m.cantidad, 0);
            const salidas = movimientos.filter(m => m.tipo === "Salida").reduce((s, m) => s + m.cantidad, 0);
            caja.innerHTML = `
                <div class="detalle-datos">
                    <span>Existencia: <strong>${producto.stock}</strong></span>
                    <span class="insignia entrada">↓ ${entradas} entraron</span>
                    <span class="insignia salida">↑ ${salidas} salieron</span>
                </div>
                ${movimientos.length === 0 ? `<p class="contador">Todavía no tiene movimientos. Se registran al completar una orden.</p>` : `
                <div class="tabla-envoltura">
                    <table class="tabla">
                        <thead><tr><th>Fecha</th><th>Movimiento</th><th class="numero">Cantidad</th><th>Orden</th></tr></thead>
                        <tbody>${movimientos.map(m => `<tr>
                            <td>${fechaHora(m.fecha)}</td>
                            <td>${insigniaTipo(m.tipo === "Entrada" ? "Compra" : "Venta")}</td>
                            <td class="numero">${m.cantidad}</td>
                            <td>${m.id_orden ? numeroOrden(m.id_orden) : "—"}</td>
                        </tr>`).join("")}</tbody>
                    </table>
                </div>`}`;
        } catch (error) {
            caja.innerHTML = `<p class="mensaje-error">${escapar(error.message)}</p>`;
        }
    });

    dibujar();
}

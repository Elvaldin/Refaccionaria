/* ==========================================================
   Refaccionaria - Datos iniciales (usuarios, catálogo y contacto)
   Ejecútalo después de 01_crear_base.sql
   Se puede correr varias veces: no duplica nada.

   Usuarios para entrar a la página:
       admin    / Admin123      (rol Administrador)
       empleado / Empleado123   (rol Empleado)
       almacen  / Almacen123    (rol Almacenista)
       cliente  / Cliente123    (rol Cliente)

   ⚠️  Esas contraseñas son públicas: son solo para desarrollo.
   En el servidor de producción, después de este script corre
   11_quitar_usuarios_de_prueba.sql y cámbiale la contraseña al
   admin con Backend/Login/cambiar_contrasena.py.
   ========================================================== */

USE Refaccionaria;
GO

/* ---------- Usuarios de prueba ---------- */
-- Las contraseñas ya van como hash bcrypt (así las guarda el microservicio de Login)
IF NOT EXISTS (SELECT 1 FROM LOGIN WHERE Username = 'admin')
    INSERT INTO LOGIN (Username, Email, Password, Rol) VALUES
    ('admin', 'admin@refaccionaria.com', '$2b$12$9AmyQI4r4o/HLhgDNq/ctuiXRLLBJtQcrJz.6FtXWS6dftxox1DcC', 'Administrador');

IF NOT EXISTS (SELECT 1 FROM LOGIN WHERE Username = 'empleado')
    INSERT INTO LOGIN (Username, Email, Password, Rol) VALUES
    ('empleado', 'empleado@refaccionaria.com', '$2b$12$5JghlBpWB8963Ka7.U3oG.cjA4PbKUyyGOKoOeuKJrhjoFthm81Ce', 'Empleado');

IF NOT EXISTS (SELECT 1 FROM LOGIN WHERE Username = 'almacen')
    INSERT INTO LOGIN (Username, Email, Password, Rol) VALUES
    ('almacen', 'almacen@refaccionaria.com', '$2b$12$A3cvRzeFJfcuYTjq1jpWDuaTuzuwg3iOjfYfU1zzKM4HRZCmbpelO', 'Almacenista');

IF NOT EXISTS (SELECT 1 FROM LOGIN WHERE Username = 'cliente')
    INSERT INTO LOGIN (Username, Email, Password, Rol) VALUES
    ('cliente', 'cliente@correo.com', '$2b$12$aPIDkNvptKQohbqB0S8MjOHzrc9bj0qbyZWIoqrN23OsvBQM0ux1W', 'Cliente');
GO

/* ---------- Categorías ---------- */
INSERT INTO CATEGORIAS (Nombre, Descripcion)
SELECT nueva.Nombre, nueva.Descripcion
FROM (VALUES
    (N'Motor',                   N'Bujías, filtros, bandas y empaques'),
    (N'Transmisión',             N'Clutch y flechas homocinéticas'),
    (N'Sistema eléctrico',       N'Baterías, alternadores, marchas, bobinas y focos'),
    (N'Frenos',                  N'Balatas, discos, tambores, calipers y líquido'),
    (N'Suspensión y dirección',  N'Amortiguadores, rótulas, terminales, horquillas y bombas')
) AS nueva (Nombre, Descripcion)
WHERE NOT EXISTS (SELECT 1 FROM CATEGORIAS c WHERE c.Nombre = nueva.Nombre);
GO

/* ---------- Productos ---------- */
-- ⚠️ Antes de abrir la tienda cambia el Precio y el Stock por los tuyos de verdad.
--    Los precios son de referencia del mercado mexicano (pesos, IVA incluido).
--    Después de cargarlos, la existencia solo cambia con órdenes de Compra y Venta.
-- Imagen: foto del producto en Frontend/img/productos.
--         NULL = todavía no tiene foto; el Administrador la puede poner al editar el producto.
INSERT INTO PRODUCTOS (Nombre, Descripcion, Precio, Stock, Id_categoria, Imagen)
SELECT nuevo.Nombre, nuevo.Descripcion, nuevo.Precio, nuevo.Stock, c.Id_categoria, nuevo.Imagen
FROM (VALUES
    -- Motor
    (N'Bujía de iridio',                  N'Electrodo central de iridio: chispa más estable y hasta 100,000 km de vida. Precio por pieza.',  260.00, 40, N'Motor', N'img/productos/bujia.jpg'),
    (N'Filtro de aceite (cartucho)',      N'Elemento filtrante de papel para motores con portafiltro. Cámbialo en cada cambio de aceite.',    180.00, 30, N'Motor', N'img/productos/filtro_aceite.jpg'),
    (N'Filtro de aire de motor',          N'Filtro de panel con marco de poliuretano. Revisión cada 10,000 km.',                               260.00, 25, N'Motor', N'img/productos/filtro_aire.jpg'),
    (N'Banda de distribución',            N'Banda dentada de caucho reforzado. Cambio recomendado entre 60,000 y 100,000 km.',                 690.00, 12, N'Motor', N'img/productos/banda_distribucion.jpg'),
    (N'Junta de cabeza',                  N'Empaque multicapa de acero entre el monoblock y la cabeza del motor.',                             950.00,  8, N'Motor', N'img/productos/junta_cabeza.jpg'),
    -- Transmisión
    (N'Plato de presión de clutch',       N'Prensa de clutch con diafragma de resortes. Se recomienda cambiarla junto con el disco.',         1950.00,  6, N'Transmisión', N'img/productos/plato_clutch.jpg'),
    (N'Disco de clutch',                  N'Disco de fricción con amortiguadores de torsión.',                                                1450.00,  6, N'Transmisión', N'img/productos/disco_clutch.jpg'),
    (N'Flecha homocinética',              N'Semieje completo con juntas homocinéticas y cubrepolvos. Precio por lado.',                       2650.00,  4, N'Transmisión', N'img/productos/flecha_homocinetica.jpg'),
    -- Sistema eléctrico
    (N'Batería 12V',                      N'Batería de plomo-ácido libre de mantenimiento. Garantía de 18 meses.',                            2950.00,  8, N'Sistema eléctrico', N'img/productos/bateria.jpg'),
    (N'Alternador 12V 90A',               N'Alternador remanufacturado con regulador integrado. Se entrega a cambio del usado.',              3200.00,  4, N'Sistema eléctrico', N'img/productos/alternador.jpg'),
    (N'Marcha (motor de arranque)',       N'Marcha de 12V con solenoide. Se entrega a cambio de la usada.',                                   2850.00,  4, N'Sistema eléctrico', N'img/productos/marcha.jpg'),
    (N'Bobina de encendido',              N'Módulo de bobinas para motor de 4 cilindros.',                                                    1650.00,  6, N'Sistema eléctrico', N'img/productos/bobina.jpg'),
    (N'Foco halógeno H4 12V 60/55W',      N'Foco de doble filamento para faro delantero (luz alta y baja). Precio por pieza.',                 120.00, 50, N'Sistema eléctrico', N'img/productos/foco_h4.jpg'),
    -- Frenos
    (N'Balatas delanteras cerámicas',     N'Juego de 4 balatas cerámicas: menos polvo y menos ruido.',                                         750.00, 20, N'Frenos', N'img/productos/balatas.jpg'),
    (N'Disco de freno ventilado',         N'Disco ventilado de hierro fundido. Se recomienda cambiar por pares. Precio por pieza.',            980.00, 10, N'Frenos', N'img/productos/disco_freno.jpg'),
    (N'Tambor de freno trasero',          N'Tambor de hierro fundido para frenos traseros. Precio por pieza.',                                 850.00,  8, N'Frenos', N'img/productos/tambor_freno.jpg'),
    (N'Caliper de freno delantero',       N'Mordaza de freno de un pistón, con soporte. Precio por pieza.',                                   1850.00,  4, N'Frenos', N'img/productos/caliper.jpg'),
    (N'Líquido de frenos DOT 3 (1 L)',    N'Líquido hidráulico para frenos y clutch. Cámbialo cada 2 años.',                                   140.00, 30, N'Frenos', N'img/productos/liquido_frenos.jpg'),
    -- Suspensión y dirección
    (N'Amortiguador delantero de gas',    N'Amortiguador hidráulico presurizado con gas. Se recomienda cambiar por pares. Precio por pieza.', 1250.00, 10, N'Suspensión y dirección', NULL),
    (N'Rótula de suspensión inferior',    N'Rótula de acero con cubrepolvo y grasera.',                                                        450.00, 12, N'Suspensión y dirección', NULL),
    (N'Terminal de dirección',            N'Terminal exterior que une la cremallera con el muñón de la rueda. Precio por pieza.',               380.00, 14, N'Suspensión y dirección', N'img/productos/terminal_direccion.jpg'),
    (N'Horquilla inferior',               N'Brazo de control de suspensión con bujes y rótula.',                                              1550.00,  6, N'Suspensión y dirección', N'img/productos/horquilla.jpg'),
    (N'Bomba de dirección hidráulica',    N'Bomba remanufacturada para dirección hidráulica. Se entrega a cambio de la usada.',               2950.00,  3, N'Suspensión y dirección', NULL)
) AS nuevo (Nombre, Descripcion, Precio, Stock, Categoria, Imagen)
JOIN CATEGORIAS c ON c.Nombre = nuevo.Categoria
WHERE NOT EXISTS (SELECT 1 FROM PRODUCTOS p WHERE p.Nombre = nuevo.Nombre);
GO

-- Las promociones las crea el Administrador desde la portada (ya no hay una de ejemplo).

/* ---------- Contacto de la tienda ---------- */
IF NOT EXISTS (SELECT 1 FROM SOPORTE)
    INSERT INTO SOPORTE (Correo, Telefono, Direccion, Horario) VALUES
    ('ventas@refaccionaria.com', '55 1234 5678', 'Av. Insurgentes 123, CDMX', 'Lunes a sábado, 9:00 a 19:00');
GO

/* ---------- Revisión ---------- */
SELECT 'LOGIN' AS Tabla, COUNT(*) AS Filas FROM LOGIN
UNION ALL SELECT 'CATEGORIAS', COUNT(*) FROM CATEGORIAS
UNION ALL SELECT 'PRODUCTOS', COUNT(*) FROM PRODUCTOS
UNION ALL SELECT 'PROMOCION', COUNT(*) FROM PROMOCION
UNION ALL SELECT 'PROMOCIONPRODUCTO', COUNT(*) FROM PROMOCIONPRODUCTO
UNION ALL SELECT 'SOPORTE', COUNT(*) FROM SOPORTE;
GO

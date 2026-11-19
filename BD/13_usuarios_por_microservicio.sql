/* ==========================================================
   Refaccionaria - Un usuario de SQL Server por microservicio
   (recomendado para el servidor de producción)

   Con 10_usuario_app.sql los 5 microservicios comparten un solo
   usuario que puede leer y cambiar TODAS las tablas. Si alguien
   lograra controlar uno (por ejemplo Soporte), podría leer los
   hashes de las contraseñas o cambiar precios y existencias.

   Este script crea 5 usuarios, cada uno solo con lo que su
   microservicio necesita. Por ejemplo, solo Login puede ver la
   columna Password; los demás solo ven el Id y el Rol de LOGIN.

   Cómo usarlo:
   1. Cambia las 5 PEGA-AQUI-... por 5 contraseñas nuevas y distintas.
   2. Ejecuta el script.
   3. Pon cada usuario y su contraseña en el .env (o en Secret
      Manager) de SU microservicio: BD_USER y BD_PASSWORD.
   4. Cierra el archivo SIN GUARDAR (las contraseñas no deben
      quedarse escritas aquí).
   Si falta alguna contraseña o se repiten, no hace nada.
   Se puede correr varias veces: si un usuario ya existe, solo le
   cambia la contraseña y le vuelve a dar sus permisos.
   ========================================================== */

USE master;
GO

DECLARE @usuarios TABLE (Nombre SYSNAME PRIMARY KEY, Contrasena NVARCHAR(128));
INSERT INTO @usuarios (Nombre, Contrasena) VALUES
    (N'refaccionaria_login',       N'PEGA-AQUI-LA-CONTRASENA-DE-LOGIN'),
    (N'refaccionaria_productos',   N'PEGA-AQUI-LA-CONTRASENA-DE-PRODUCTOS'),
    (N'refaccionaria_promociones', N'PEGA-AQUI-LA-CONTRASENA-DE-PROMOCIONES'),
    (N'refaccionaria_ordenes',     N'PEGA-AQUI-LA-CONTRASENA-DE-ORDENES'),
    (N'refaccionaria_soporte',     N'PEGA-AQUI-LA-CONTRASENA-DE-SOPORTE');

-- Seguro: si algo falta, SET NOEXEC ON se brinca todo lo que sigue
-- (hasta el SET NOEXEC OFF del final)
IF EXISTS (SELECT 1 FROM @usuarios WHERE Contrasena LIKE N'PEGA-AQUI%')
BEGIN
    RAISERROR(N'No se cambió nada. Primero cambia las 5 PEGA-AQUI-... por contraseñas nuevas.', 16, 1);
    SET NOEXEC ON;
END
ELSE IF (SELECT COUNT(DISTINCT Contrasena) FROM @usuarios) < 5
BEGIN
    RAISERROR(N'No se cambió nada. Usa una contraseña distinta para cada microservicio.', 16, 1);
    SET NOEXEC ON;
END
ELSE
BEGIN
    DECLARE @nombre SYSNAME, @contrasena NVARCHAR(128), @sql NVARCHAR(MAX);
    DECLARE cuentas CURSOR LOCAL FAST_FORWARD FOR SELECT Nombre, Contrasena FROM @usuarios;
    OPEN cuentas;
    FETCH NEXT FROM cuentas INTO @nombre, @contrasena;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @sql = CASE WHEN EXISTS (SELECT 1 FROM sys.server_principals WHERE name = @nombre)
            THEN N'ALTER LOGIN ' + QUOTENAME(@nombre) + N' WITH PASSWORD = ' + QUOTENAME(@contrasena, '''')
            ELSE N'CREATE LOGIN ' + QUOTENAME(@nombre) + N' WITH PASSWORD = ' + QUOTENAME(@contrasena, '''')
                 + N', DEFAULT_DATABASE = Refaccionaria, CHECK_POLICY = ON'
        END;
        EXEC (@sql);
        FETCH NEXT FROM cuentas INTO @nombre, @contrasena;
    END
    CLOSE cuentas;
    DEALLOCATE cuentas;
END
GO

USE Refaccionaria;
GO

IF USER_ID(N'refaccionaria_login')       IS NULL CREATE USER refaccionaria_login       FOR LOGIN refaccionaria_login;
IF USER_ID(N'refaccionaria_productos')   IS NULL CREATE USER refaccionaria_productos   FOR LOGIN refaccionaria_productos;
IF USER_ID(N'refaccionaria_promociones') IS NULL CREATE USER refaccionaria_promociones FOR LOGIN refaccionaria_promociones;
IF USER_ID(N'refaccionaria_ordenes')     IS NULL CREATE USER refaccionaria_ordenes     FOR LOGIN refaccionaria_ordenes;
IF USER_ID(N'refaccionaria_soporte')     IS NULL CREATE USER refaccionaria_soporte     FOR LOGIN refaccionaria_soporte;
GO

/* ---------- Login: usuarios y contraseñas ---------- */
GRANT SELECT, INSERT ON dbo.LOGIN TO refaccionaria_login;
GRANT UPDATE (Password) ON dbo.LOGIN TO refaccionaria_login;      -- cambiar_contrasena.py

/* ---------- Productos: catálogo ---------- */
GRANT SELECT, INSERT, DELETE ON dbo.CATEGORIAS TO refaccionaria_productos;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.PRODUCTOS TO refaccionaria_productos;
GRANT SELECT (Id_login, Rol) ON dbo.LOGIN TO refaccionaria_productos;   -- solo para revisar el rol

/* ---------- Promociones ---------- */
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.PROMOCION TO refaccionaria_promociones;
GRANT SELECT, INSERT, DELETE ON dbo.PROMOCIONPRODUCTO TO refaccionaria_promociones;
GRANT SELECT (Id_producto, Nombre, Precio) ON dbo.PRODUCTOS TO refaccionaria_promociones;
GRANT SELECT (Id_login, Rol) ON dbo.LOGIN TO refaccionaria_promociones;

/* ---------- Órdenes e inventario ---------- */
-- Las órdenes no se borran: solo cambian de estado
GRANT SELECT, INSERT, UPDATE ON dbo.ORDENES TO refaccionaria_ordenes;
GRANT SELECT, INSERT ON dbo.DETALLEORDEN TO refaccionaria_ordenes;
GRANT SELECT, INSERT ON dbo.MOVIMIENTOS_INVENTARIO TO refaccionaria_ordenes;
-- Del producto solo lee lo necesario y solo cambia la existencia (Stock), nunca el precio
GRANT SELECT (Id_producto, Nombre, Precio, Stock) ON dbo.PRODUCTOS TO refaccionaria_ordenes;
GRANT UPDATE (Stock) ON dbo.PRODUCTOS TO refaccionaria_ordenes;
GRANT SELECT ON dbo.PROMOCION TO refaccionaria_ordenes;            -- el descuento vigente
GRANT SELECT ON dbo.PROMOCIONPRODUCTO TO refaccionaria_ordenes;
GRANT SELECT (Id_login, Rol) ON dbo.LOGIN TO refaccionaria_ordenes;

/* ---------- Soporte: contacto y chat ---------- */
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.SOPORTE TO refaccionaria_soporte;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.CONVERSACION TO refaccionaria_soporte;
GRANT SELECT, INSERT, DELETE ON dbo.MENSAJE TO refaccionaria_soporte;
GRANT SELECT (Id_login, Username, Rol) ON dbo.LOGIN TO refaccionaria_soporte;   -- el nombre de quien escribe
GO

-- Revisión: qué puede hacer cada usuario (tabla, columna y permiso)
SELECT pr.name AS usuario, OBJECT_NAME(pe.major_id) AS tabla,
       ISNULL(COL_NAME(pe.major_id, pe.minor_id), '(todas)') AS columna, pe.permission_name AS permiso
FROM sys.database_permissions pe
JOIN sys.database_principals pr ON pr.principal_id = pe.grantee_principal_id
WHERE pr.name LIKE N'refaccionaria[_]%' AND pe.class = 1
ORDER BY usuario, tabla, columna, permiso;
GO

-- Fin del seguro: SQL Server vuelve a ejecutar normalmente
SET NOEXEC OFF;
GO

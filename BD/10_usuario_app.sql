/* ==========================================================
   Refaccionaria - Usuario de SQL Server solo para la app

   Los 5 microservicios entran con este usuario en vez de "sa".
   Solo puede leer y escribir datos de la base Refaccionaria:
   no puede borrar tablas, crear bases ni tocar otras bases.

   Cómo usarlo:
   1. Cambia PEGA-AQUI-LA-CONTRASENA por la contraseña nueva.
   2. Ejecuta el script.
   3. Cierra el archivo SIN GUARDAR (la contraseña no debe
      quedarse escrita aquí).
   Se puede correr varias veces: si el usuario ya existe,
   solo le cambia la contraseña.
   ========================================================== */

USE master;
GO

DECLARE @contrasena NVARCHAR(128) = N'PEGA-AQUI-LA-CONTRASENA';
IF @contrasena = N'PEGA-AQUI-LA-CONTRASENA'
BEGIN
    -- SET NOEXEC ON: se brinca todo lo que sigue (hasta el SET NOEXEC OFF del final)
    RAISERROR(N'No se cambió nada. Primero cambia PEGA-AQUI-LA-CONTRASENA por la contraseña nueva.', 16, 1);
    SET NOEXEC ON;
END
ELSE
BEGIN
    DECLARE @sql NVARCHAR(MAX) =
        CASE WHEN EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'refaccionaria_app')
             THEN N'ALTER LOGIN refaccionaria_app WITH PASSWORD = ' + QUOTENAME(@contrasena, '''')
             ELSE N'CREATE LOGIN refaccionaria_app WITH PASSWORD = ' + QUOTENAME(@contrasena, '''')
                  + N', DEFAULT_DATABASE = Refaccionaria, CHECK_POLICY = ON'
        END;
    EXEC (@sql);
END
GO

USE Refaccionaria;
GO

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'refaccionaria_app')
    CREATE USER refaccionaria_app FOR LOGIN refaccionaria_app;

-- Solo leer y escribir datos (SELECT, INSERT, UPDATE, DELETE)
ALTER ROLE db_datareader ADD MEMBER refaccionaria_app;
ALTER ROLE db_datawriter ADD MEMBER refaccionaria_app;
GO

-- Revisión: deben salir 2 filas (db_datareader y db_datawriter)
SELECT u.name AS usuario, r.name AS permiso
FROM sys.database_role_members m
JOIN sys.database_principals r ON r.principal_id = m.role_principal_id
JOIN sys.database_principals u ON u.principal_id = m.member_principal_id
WHERE u.name = N'refaccionaria_app';
GO

-- Fin del seguro: SQL Server vuelve a ejecutar normalmente
SET NOEXEC OFF;
GO

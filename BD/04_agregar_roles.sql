/* ==========================================================
   Refaccionaria - Actualización: roles de usuario
   Solo es necesario en bases creadas ANTES de que existiera la
   columna Rol (o con la versión anterior de los roles).
   Se puede correr varias veces sin problema.

   Roles:
       Administrador  puede todo y crea usuarios de cualquier rol
       Empleado       hace ventas y las avanza; no compras ni cancelar
       Almacenista    registra compras (mercancía que entra) y las avanza
       Cliente        solo hace pedidos y solo ve sus propias órdenes
   ========================================================== */

USE Refaccionaria;
GO

-- 1) La columna Rol. Los usuarios que ya existen quedan como Empleado
IF COL_LENGTH('dbo.LOGIN', 'Rol') IS NULL
    ALTER TABLE LOGIN ADD Rol VARCHAR(20) NOT NULL
        CONSTRAINT DF_LOGIN_ROL DEFAULT 'Empleado' WITH VALUES;
GO

-- 2) Se quita la regla anterior para poder cambiar los roles
IF OBJECT_ID('dbo.CK_LOGIN_ROL', 'C') IS NOT NULL
    ALTER TABLE LOGIN DROP CONSTRAINT CK_LOGIN_ROL;
GO

-- 3) El rol Vendedor ahora se llama Empleado
UPDATE LOGIN SET Rol = 'Empleado' WHERE Rol = 'Vendedor';
GO

-- 4) El valor por omisión también es Empleado
IF OBJECT_ID('dbo.DF_LOGIN_ROL', 'D') IS NOT NULL
    ALTER TABLE LOGIN DROP CONSTRAINT DF_LOGIN_ROL;
ALTER TABLE LOGIN ADD CONSTRAINT DF_LOGIN_ROL DEFAULT 'Empleado' FOR Rol;
GO

-- 5) Solo se permiten estos cuatro roles
ALTER TABLE LOGIN ADD CONSTRAINT CK_LOGIN_ROL
    CHECK (Rol IN ('Administrador', 'Empleado', 'Almacenista', 'Cliente'));
GO

-- 6) El usuario admin es Administrador
UPDATE LOGIN SET Rol = 'Administrador' WHERE Username = 'admin';
GO

-- 7) Los usuarios de prueba (empleado, almacen, cliente) ya no se crean aquí:
--    están en 12_usuarios_de_prueba.sql, que es SOLO para tu computadora.

SELECT Id_login, Username, Rol FROM LOGIN;
GO
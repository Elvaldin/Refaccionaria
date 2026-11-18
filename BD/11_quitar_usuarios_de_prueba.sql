/* ==========================================================
   Refaccionaria - Quitar los usuarios de prueba (SOLO EN PRODUCCIÓN)

   Borra los usuarios empleado, almacen y cliente: sus contraseñas
   están escritas en el README y en 02_datos_ejemplo.sql, así que
   cualquiera podría entrar con ellos.

   NO borra al admin. A él cámbiale la contraseña con:
       cd Backend/Login
       ../../.venv/bin/python cambiar_contrasena.py admin

   ⚠️  NO lo corras en tu computadora de desarrollo: las pruebas
   automáticas (pruebas.sh) y la demo usan estos usuarios.

   Si alguno ya tiene órdenes o mensajes del chat, no se borra
   (su historial apunta a él) y aparece en la lista de abajo:
   a ese cámbiale la contraseña con cambiar_contrasena.py.
   Se puede correr varias veces.
   ========================================================== */

USE Refaccionaria;
GO

DECLARE @prueba TABLE (Username VARCHAR(50) PRIMARY KEY);
INSERT INTO @prueba VALUES ('empleado'), ('almacen'), ('cliente');

-- Los que tienen historial se quedan (avisa cuáles)
SELECT l.Username AS [No se borró porque tiene historial: cámbiale la contraseña]
FROM LOGIN l
JOIN @prueba p ON p.Username = l.Username
WHERE EXISTS (SELECT 1 FROM ORDENES o      WHERE o.Id_login = l.Id_login)
   OR EXISTS (SELECT 1 FROM CONVERSACION c WHERE c.Id_login = l.Id_login)
   OR EXISTS (SELECT 1 FROM MENSAJE m      WHERE m.Id_login = l.Id_login);

-- Los demás se borran
DELETE l
FROM LOGIN l
JOIN @prueba p ON p.Username = l.Username
WHERE NOT EXISTS (SELECT 1 FROM ORDENES o      WHERE o.Id_login = l.Id_login)
  AND NOT EXISTS (SELECT 1 FROM CONVERSACION c WHERE c.Id_login = l.Id_login)
  AND NOT EXISTS (SELECT 1 FROM MENSAJE m      WHERE m.Id_login = l.Id_login);

PRINT CONCAT(@@ROWCOUNT, ' usuario(s) de prueba borrado(s).');
GO

-- Los usuarios que quedan
SELECT Id_login, Username, Rol FROM LOGIN ORDER BY Id_login;

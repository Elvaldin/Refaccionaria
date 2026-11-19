/* ==========================================================
   Refaccionaria - Usuarios de prueba (SOLO EN TU COMPUTADORA)

   ⚠️  NUNCA lo corras en el servidor de producción: estas
   contraseñas están escritas en el README, así que cualquiera
   podría entrar con ellas (incluso como Administrador).

   Ejecútalo después de 01_crear_base.sql y 02_datos_ejemplo.sql.
   Los usan la demo y las pruebas automáticas (pruebas.sh):
       admin    / Admin123      (rol Administrador)
       empleado / Empleado123   (rol Empleado)
       almacen  / Almacen123    (rol Almacenista)
       cliente  / Cliente123    (rol Cliente)
   Se puede correr varias veces: no duplica nada.

   En producción el primer Administrador se crea con:
       cd Backend/Login
       ../../.venv/bin/python crear_administrador.py
   ========================================================== */

USE Refaccionaria;
GO

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

SELECT Id_login, Username, Rol FROM LOGIN ORDER BY Id_login;
GO

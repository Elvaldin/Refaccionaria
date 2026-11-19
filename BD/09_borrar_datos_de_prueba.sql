/* ==========================================================
   Refaccionaria - Borrar los datos de prueba (UNA SOLA VEZ)

   ⚠️  CUIDADO: BORRA TODAS las órdenes, movimientos de inventario,
   promociones, conversaciones del chat, productos y categorías.
   Úsalo solo antes de abrir la tienda, para quitar los datos
   ficticios. Si ya tienes ventas reales, NO lo corras.

   NO borra los usuarios ni los datos de contacto.

   Para que no se corra por accidente, primero cambia
   N'NO' por N'SI, BORRAR TODO' en la línea de @confirmo.
   Si no, no borra nada. Al terminar cierra el archivo SIN GUARDAR.

   Después de correrlo, ejecuta 02_datos_ejemplo.sql para cargar
   el catálogo real (5 categorías y sus piezas). El 02 no crea
   usuarios: NO corras 12_usuarios_de_prueba.sql en producción.
   ========================================================== */

USE Refaccionaria;
GO

-- Seguro: sin la confirmación, SET NOEXEC ON hace que SQL Server se brinque
-- todo lo que sigue (hasta el SET NOEXEC OFF del final)
DECLARE @confirmo NVARCHAR(20) = N'NO';
IF @confirmo <> N'SI, BORRAR TODO'
BEGIN
    RAISERROR(N'No se borró nada. Si de verdad quieres borrar todo, cambia N''NO'' por N''SI, BORRAR TODO'' en @confirmo.', 16, 1);
    SET NOEXEC ON;
END
GO

BEGIN TRANSACTION;
    DELETE FROM MOVIMIENTOS_INVENTARIO;
    DELETE FROM DETALLEORDEN;
    DELETE FROM ORDENES;
    DELETE FROM PROMOCIONPRODUCTO;
    DELETE FROM PROMOCION;
    DELETE FROM MENSAJE;
    DELETE FROM CONVERSACION;
    DELETE FROM PRODUCTOS;
    DELETE FROM CATEGORIAS;
COMMIT;
GO

-- Los números vuelven a empezar en 1 (el primer producto será REF-001).
-- Solo en tablas que ya tuvieron filas: en una tabla que nunca se usó, RESEED 0
-- haría que el primer número fuera 0.
DECLARE @tabla SYSNAME;
DECLARE tablas CURSOR LOCAL FAST_FORWARD FOR
    SELECT OBJECT_NAME(object_id) FROM sys.identity_columns
    WHERE OBJECT_NAME(object_id) IN ('MOVIMIENTOS_INVENTARIO', 'DETALLEORDEN', 'ORDENES', 'PROMOCION',
                                     'MENSAJE', 'CONVERSACION', 'PRODUCTOS', 'CATEGORIAS')
      AND last_value IS NOT NULL;
OPEN tablas;
FETCH NEXT FROM tablas INTO @tabla;
WHILE @@FETCH_STATUS = 0
BEGIN
    DBCC CHECKIDENT (@tabla, RESEED, 0) WITH NO_INFOMSGS;
    FETCH NEXT FROM tablas INTO @tabla;
END
CLOSE tablas;
DEALLOCATE tablas;
GO

SELECT 'ORDENES' AS Tabla, COUNT(*) AS Filas FROM ORDENES
UNION ALL SELECT 'PRODUCTOS', COUNT(*) FROM PRODUCTOS
UNION ALL SELECT 'CATEGORIAS', COUNT(*) FROM CATEGORIAS
UNION ALL SELECT 'PROMOCION', COUNT(*) FROM PROMOCION
UNION ALL SELECT 'CONVERSACION', COUNT(*) FROM CONVERSACION
UNION ALL SELECT 'LOGIN (se quedan)', COUNT(*) FROM LOGIN;
GO

-- Fin del seguro: SQL Server vuelve a ejecutar normalmente
SET NOEXEC OFF;
GO

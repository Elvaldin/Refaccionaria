/* ==========================================================
   Refaccionaria - Actualización: números (Id) sin saltos de 1000
   SQL Server guarda en memoria los siguientes 1000 números de cada tabla
   para ir más rápido. Si se reinicia (por ejemplo, al apagar Docker), esos
   números se pierden y el siguiente producto sale como REF-5021 en vez de REF-011.
   Este script:
     1) Apaga esa memoria (IDENTITY_CACHE), así ya no hay saltos al reiniciar.
     2) Regresa el contador de cada tabla al número más alto que de verdad existe.
   No cambia ni borra ningún dato. Se puede correr varias veces sin problema.
   ========================================================== */

USE Refaccionaria;
GO

-- 1) Sin memoria de números: al reiniciar SQL Server ya no se brinca 1000
ALTER DATABASE SCOPED CONFIGURATION SET IDENTITY_CACHE = OFF;
GO

-- 2) Cada contador se regresa al Id más alto que existe (el siguiente será ese + 1).
--    Nunca baja de un Id que ya existe, así que no se pueden repetir números.
DECLARE @tabla SYSNAME, @columna SYSNAME, @maximo INT, @sql NVARCHAR(400);
DECLARE tablas CURSOR LOCAL FAST_FORWARD FOR
    SELECT OBJECT_NAME(ic.object_id), ic.name
    FROM sys.identity_columns ic
    WHERE OBJECTPROPERTY(ic.object_id, 'IsUserTable') = 1;
OPEN tablas;
FETCH NEXT FROM tablas INTO @tabla, @columna;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @sql = N'SELECT @m = ISNULL(MAX(' + QUOTENAME(@columna) + N'), 0) FROM ' + QUOTENAME(@tabla);
    EXEC sp_executesql @sql, N'@m INT OUTPUT', @m = @maximo OUTPUT;
    DBCC CHECKIDENT (@tabla, RESEED, @maximo) WITH NO_INFOMSGS;
    FETCH NEXT FROM tablas INTO @tabla, @columna;
END
CLOSE tablas;
DEALLOCATE tablas;
GO

-- Revisión: "ultimo_numero" debe ser igual a "id_mas_alto" (o 0 si la tabla está vacía)
SELECT OBJECT_NAME(object_id) AS tabla, CAST(last_value AS INT) AS ultimo_numero
FROM sys.identity_columns
WHERE OBJECTPROPERTY(object_id, 'IsUserTable') = 1
ORDER BY tabla;
GO

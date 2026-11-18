/* ==========================================================
   Refaccionaria - Actualización: textos con emojis (Unicode)
   Solo es necesario en bases creadas ANTES de que los textos que
   escribe la gente fueran NVARCHAR. Con VARCHAR un emoji como 😀
   se guardaba como "??" (por ejemplo, en el chat de soporte).
   No se pierde ningún dato. Se puede correr varias veces sin problema.
   ========================================================== */

USE Refaccionaria;
GO

-- El nombre de la categoría tiene la regla UQ_CATEGORIAS_NOMBRE:
-- se quita, se cambia la columna y se vuelve a poner
IF EXISTS (SELECT 1 FROM sys.columns c JOIN sys.types t ON t.user_type_id = c.user_type_id
           WHERE c.object_id = OBJECT_ID('dbo.CATEGORIAS') AND c.name = 'Nombre' AND t.name = 'varchar')
BEGIN
    IF EXISTS (SELECT 1 FROM sys.objects WHERE name = 'UQ_CATEGORIAS_NOMBRE')
        ALTER TABLE CATEGORIAS DROP CONSTRAINT UQ_CATEGORIAS_NOMBRE;
    ALTER TABLE CATEGORIAS ALTER COLUMN Nombre NVARCHAR(100) NOT NULL;
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE name = 'UQ_CATEGORIAS_NOMBRE')
    ALTER TABLE CATEGORIAS ADD CONSTRAINT UQ_CATEGORIAS_NOMBRE UNIQUE (Nombre);
GO

-- Los demás textos no tienen reglas encima: se cambian directo.
-- (Si la columna ya es NVARCHAR, no pasa nada)
ALTER TABLE CATEGORIAS             ALTER COLUMN Descripcion   NVARCHAR(255)  NULL;
ALTER TABLE PRODUCTOS              ALTER COLUMN Nombre        NVARCHAR(100)  NOT NULL;
ALTER TABLE PRODUCTOS              ALTER COLUMN Descripcion   NVARCHAR(255)  NULL;
ALTER TABLE PROMOCION              ALTER COLUMN Nombre        NVARCHAR(100)  NOT NULL;
ALTER TABLE PROMOCION              ALTER COLUMN Descripcion   NVARCHAR(255)  NULL;
ALTER TABLE ORDENES                ALTER COLUMN Observaciones NVARCHAR(255)  NULL;
ALTER TABLE MOVIMIENTOS_INVENTARIO ALTER COLUMN Observaciones NVARCHAR(255)  NULL;
ALTER TABLE SOPORTE                ALTER COLUMN Direccion     NVARCHAR(255)  NULL;
ALTER TABLE SOPORTE                ALTER COLUMN Horario       NVARCHAR(100)  NULL;
ALTER TABLE CONVERSACION           ALTER COLUMN Asunto        NVARCHAR(100)  NOT NULL;
ALTER TABLE MENSAJE                ALTER COLUMN Texto         NVARCHAR(1000) NOT NULL;
GO

-- Revisión: todas deben salir como nvarchar
SELECT OBJECT_NAME(c.object_id) AS tabla, c.name AS columna, t.name AS tipo
FROM sys.columns c JOIN sys.types t ON t.user_type_id = c.user_type_id
WHERE (OBJECT_NAME(c.object_id) = 'CATEGORIAS'             AND c.name IN ('Nombre', 'Descripcion'))
   OR (OBJECT_NAME(c.object_id) = 'PRODUCTOS'              AND c.name IN ('Nombre', 'Descripcion'))
   OR (OBJECT_NAME(c.object_id) = 'PROMOCION'              AND c.name IN ('Nombre', 'Descripcion'))
   OR (OBJECT_NAME(c.object_id) = 'ORDENES'                AND c.name = 'Observaciones')
   OR (OBJECT_NAME(c.object_id) = 'MOVIMIENTOS_INVENTARIO' AND c.name = 'Observaciones')
   OR (OBJECT_NAME(c.object_id) = 'SOPORTE'                AND c.name IN ('Direccion', 'Horario'))
   OR (OBJECT_NAME(c.object_id) = 'CONVERSACION'           AND c.name = 'Asunto')
   OR (OBJECT_NAME(c.object_id) = 'MENSAJE'                AND c.name = 'Texto')
ORDER BY tabla, columna;
GO

/* ==========================================================
   Refaccionaria - Actualización: foto de cada producto
   Agrega la columna Imagen a PRODUCTOS (la ruta de la foto,
   por ejemplo img/productos/bujia.jpg). No borra ningún dato.
   Solo hace falta si tu base se creó antes de esta columna.
   Se puede correr varias veces.
   ========================================================== */

USE Refaccionaria;
GO

IF COL_LENGTH('dbo.PRODUCTOS', 'Imagen') IS NULL
    ALTER TABLE PRODUCTOS ADD Imagen NVARCHAR(255) NULL;
GO

SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'PRODUCTOS' AND COLUMN_NAME = 'Imagen';
GO

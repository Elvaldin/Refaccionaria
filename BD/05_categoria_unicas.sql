/* ==========================================================
   Refaccionaria - Actualización: nombres de categoría únicos
   Solo es necesario en bases creadas ANTES de que existiera la
   regla UQ_CATEGORIAS_NOMBRE (no se pueden repetir nombres).
   Se puede correr varias veces sin problema.
   ========================================================== */

USE Refaccionaria;
GO

-- 1) Se borra la categoría que dejó la prueba automática (solo si no tiene productos)
DELETE FROM CATEGORIAS
WHERE Nombre = 'PRUEBA AUTOMATICA'
  AND NOT EXISTS (SELECT 1 FROM PRODUCTOS p WHERE p.Id_categoria = CATEGORIAS.Id_categoria);
GO

-- 2) La regla: dos categorías no pueden tener el mismo nombre
IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE name = 'UQ_CATEGORIAS_NOMBRE')
    ALTER TABLE CATEGORIAS ADD CONSTRAINT UQ_CATEGORIAS_NOMBRE UNIQUE (Nombre);
GO

-- Revisión: debe salir UQ_CATEGORIAS_NOMBRE
SELECT name AS regla FROM sys.objects WHERE name = 'UQ_CATEGORIAS_NOMBRE';
GO
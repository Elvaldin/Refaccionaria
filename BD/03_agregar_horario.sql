/* ==========================================================
   Refaccionaria - Actualización: horario de atención en SOPORTE
   Solo es necesario en bases creadas ANTES de que existiera la
   columna Horario. Se puede correr varias veces sin problema.
   ========================================================== */

USE Refaccionaria;
GO

IF COL_LENGTH('dbo.SOPORTE', 'Horario') IS NULL
    ALTER TABLE SOPORTE ADD Horario VARCHAR(100) NULL;
GO

UPDATE SOPORTE
SET Horario = 'Lunes a sábado, 9:00 a 19:00'
WHERE Horario IS NULL;
GO

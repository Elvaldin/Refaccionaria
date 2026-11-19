/* ==========================================================
   Refaccionaria - Índices para que las consultas sean rápidas
   Solo hace falta si tu base se creó antes de que 01_crear_base.sql
   los incluyera. No cambia ni borra ningún dato.
   Se puede correr varias veces: solo crea los que faltan.

   Un índice es como el índice de un libro: SQL Server encuentra
   las filas de una orden, un producto o una conversación sin leer
   la tabla completa. Las llaves primarias ya tienen el suyo; aquí
   van las columnas que se usan para buscar y para unir tablas.
   ========================================================== */

USE Refaccionaria;
GO

-- productos de una categoría
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_PRODUCTOS_Id_categoria' AND object_id = OBJECT_ID(N'dbo.PRODUCTOS'))
    CREATE INDEX IX_PRODUCTOS_Id_categoria ON dbo.PRODUCTOS (Id_categoria);
-- promociones que no han vencido
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_PROMOCION_Fecha_fin' AND object_id = OBJECT_ID(N'dbo.PROMOCION'))
    CREATE INDEX IX_PROMOCION_Fecha_fin ON dbo.PROMOCION (Fecha_fin);
-- el descuento de un producto al vender
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_PROMOCIONPRODUCTO_Id_producto' AND object_id = OBJECT_ID(N'dbo.PROMOCIONPRODUCTO'))
    CREATE INDEX IX_PROMOCIONPRODUCTO_Id_producto ON dbo.PROMOCIONPRODUCTO (Id_producto);
-- la lista de órdenes, las más nuevas primero
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_ORDENES_Fecha' AND object_id = OBJECT_ID(N'dbo.ORDENES'))
    CREATE INDEX IX_ORDENES_Fecha ON dbo.ORDENES (Fecha DESC);
-- los pedidos de un cliente
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_ORDENES_Id_login' AND object_id = OBJECT_ID(N'dbo.ORDENES'))
    CREATE INDEX IX_ORDENES_Id_login ON dbo.ORDENES (Id_login, Fecha DESC);
-- los productos de cada orden
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_DETALLEORDEN_Id_orden' AND object_id = OBJECT_ID(N'dbo.DETALLEORDEN'))
    CREATE INDEX IX_DETALLEORDEN_Id_orden ON dbo.DETALLEORDEN (Id_orden);
-- revisar si un producto ya se vendió antes de borrarlo
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_DETALLEORDEN_Id_producto' AND object_id = OBJECT_ID(N'dbo.DETALLEORDEN'))
    CREATE INDEX IX_DETALLEORDEN_Id_producto ON dbo.DETALLEORDEN (Id_producto);
-- el historial de un producto en el Almacén
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_MOVIMIENTOS_Id_producto' AND object_id = OBJECT_ID(N'dbo.MOVIMIENTOS_INVENTARIO'))
    CREATE INDEX IX_MOVIMIENTOS_Id_producto ON dbo.MOVIMIENTOS_INVENTARIO (Id_producto, Fecha DESC);
-- los movimientos de una orden
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_MOVIMIENTOS_Id_orden' AND object_id = OBJECT_ID(N'dbo.MOVIMIENTOS_INVENTARIO'))
    CREATE INDEX IX_MOVIMIENTOS_Id_orden ON dbo.MOVIMIENTOS_INVENTARIO (Id_orden);
-- las conversaciones de un cliente
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_CONVERSACION_Id_login' AND object_id = OBJECT_ID(N'dbo.CONVERSACION'))
    CREATE INDEX IX_CONVERSACION_Id_login ON dbo.CONVERSACION (Id_login);
-- los mensajes de cada conversación
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_MENSAJE_Id_conversacion' AND object_id = OBJECT_ID(N'dbo.MENSAJE'))
    CREATE INDEX IX_MENSAJE_Id_conversacion ON dbo.MENSAJE (Id_conversacion);
-- revisar si un usuario escribió en el chat
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_MENSAJE_Id_login' AND object_id = OBJECT_ID(N'dbo.MENSAJE'))
    CREATE INDEX IX_MENSAJE_Id_login ON dbo.MENSAJE (Id_login);
GO

-- Revisión: deben salir los 12 índices
SELECT OBJECT_NAME(object_id) AS tabla, name AS indice
FROM sys.indexes
WHERE name LIKE N'IX[_]%' AND OBJECTPROPERTY(object_id, 'IsUserTable') = 1
ORDER BY tabla, indice;
GO

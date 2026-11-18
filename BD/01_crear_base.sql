/* ==========================================================
   Refaccionaria - Base de datos
   Crea la base y todas las tablas desde cero.
   Se puede correr varias veces: solo crea lo que todavía no existe.
   Ejecútalo primero. Después ejecuta 02_datos_ejemplo.sql
   ========================================================== */

IF DB_ID('Refaccionaria') IS NULL
    CREATE DATABASE Refaccionaria;
GO

USE Refaccionaria;
GO

-- Sin esto, SQL Server se brinca 1000 números cada vez que se reinicia
-- (el siguiente producto saldría REF-1011 en vez de REF-011)
ALTER DATABASE SCOPED CONFIGURATION SET IDENTITY_CACHE = OFF;
GO

/* ---------- Usuarios del sistema ---------- */
IF OBJECT_ID('dbo.LOGIN', 'U') IS NULL
CREATE TABLE LOGIN (
    Id_login   INT PRIMARY KEY IDENTITY(1,1),
    Username   VARCHAR(50)  NOT NULL,
    Email      VARCHAR(100) NOT NULL,
    Password   VARCHAR(MAX) NOT NULL,          -- hash bcrypt, nunca la contraseña real
    Rol VARCHAR(20) NOT NULL CONSTRAINT DF_LOGIN_ROL DEFAULT 'Empleado',
    CREATE_at  DATETIME DEFAULT GETDATE(),

    CONSTRAINT UQ_LOGIN_USERNAME UNIQUE (Username),
    CONSTRAINT UQ_LOGIN_EMAIL    UNIQUE (Email),
    CONSTRAINT CK_LOGIN_ROL      CHECK (Rol IN ('Administrador', 'Empleado', 'Almacenista', 'Cliente'))
);
GO

/* ---------- Catálogo ---------- */
IF OBJECT_ID('dbo.CATEGORIAS', 'U') IS NULL
CREATE TABLE CATEGORIAS (
    Id_categoria INT PRIMARY KEY IDENTITY(1,1),
    Nombre       NVARCHAR(100) NOT NULL,
    Descripcion  NVARCHAR(255),
    CREATE_at    DATETIME DEFAULT GETDATE(),

    CONSTRAINT UQ_CATEGORIAS_NOMBRE UNIQUE (Nombre)
);
GO

IF OBJECT_ID('dbo.PRODUCTOS', 'U') IS NULL
CREATE TABLE PRODUCTOS (
    Id_producto  INT PRIMARY KEY IDENTITY(1,1),
    Nombre       NVARCHAR(100)  NOT NULL,
    Descripcion  NVARCHAR(255),
    Precio       DECIMAL(10, 2) NOT NULL,
    Stock        INT            NOT NULL DEFAULT 0,
    Id_categoria INT            NOT NULL,
    Imagen       NVARCHAR(255),          -- ruta de la foto, ej. img/productos/bujia.jpg
    CREATE_at    DATETIME DEFAULT GETDATE(),

    CONSTRAINT FK_PRODUCTOS_CATEGORIAS FOREIGN KEY (Id_categoria) REFERENCES CATEGORIAS(Id_categoria),
    CONSTRAINT CK_PRODUCTOS_PRECIO CHECK (Precio >= 0),
    CONSTRAINT CK_PRODUCTOS_STOCK  CHECK (Stock >= 0)
);
GO

/* ---------- Promociones ---------- */
IF OBJECT_ID('dbo.PROMOCION', 'U') IS NULL
CREATE TABLE PROMOCION (
    Id_promocion INT PRIMARY KEY IDENTITY(1,1),
    Nombre       NVARCHAR(100) NOT NULL,
    Descripcion  NVARCHAR(255),
    Descuento    DECIMAL(5, 2) NOT NULL,         -- porcentaje: 15 = 15%
    Fecha_inicio DATETIME      NOT NULL,
    Fecha_fin    DATETIME      NOT NULL,
    Activa       BIT           NOT NULL DEFAULT 1,

    CONSTRAINT CK_PROMOCION_DESCUENTO CHECK (Descuento >= 0 AND Descuento <= 100),
    CONSTRAINT CK_PROMOCION_FECHAS    CHECK (Fecha_inicio <= Fecha_fin)
);
GO

-- Qué productos entran en cada promoción (relación muchos a muchos)
IF OBJECT_ID('dbo.PROMOCIONPRODUCTO', 'U') IS NULL
CREATE TABLE PROMOCIONPRODUCTO (
    Id_promocion INT,
    Id_producto  INT,

    CONSTRAINT PK_PROMOCIONPRODUCTO PRIMARY KEY (Id_promocion, Id_producto),
    CONSTRAINT FK_PROMOCIONPRODUCTO_PROMOCION FOREIGN KEY (Id_promocion) REFERENCES PROMOCION(Id_promocion),
    CONSTRAINT FK_PROMOCIONPRODUCTO_PRODUCTOS FOREIGN KEY (Id_producto)  REFERENCES PRODUCTOS(Id_producto)
);
GO

/* ---------- Órdenes: Compra = entra mercancía, Venta = sale ---------- */
IF OBJECT_ID('dbo.ORDENES', 'U') IS NULL
CREATE TABLE ORDENES (
    Id_orden      INT PRIMARY KEY IDENTITY(1,1),
    Id_login      INT          NOT NULL,         -- quién registró la orden
    Tipo          VARCHAR(50)  NOT NULL,
    Observaciones NVARCHAR(255),
    Estado        VARCHAR(50)  NOT NULL DEFAULT 'Pendiente',
    Fecha         DATETIME DEFAULT GETDATE(),

    CONSTRAINT FK_ORDENES_LOGIN  FOREIGN KEY (Id_login) REFERENCES LOGIN(Id_login),
    CONSTRAINT CK_ORDENES_ESTADO CHECK (Estado IN ('Pendiente', 'En Proceso', 'Completada', 'Cancelada')),
    CONSTRAINT CK_ORDENES_TIPO   CHECK (Tipo IN ('Compra', 'Venta'))
);
GO

-- Los productos de cada orden
IF OBJECT_ID('dbo.DETALLEORDEN', 'U') IS NULL
CREATE TABLE DETALLEORDEN (
    Id_detalle      INT PRIMARY KEY IDENTITY(1,1),
    Id_orden        INT            NOT NULL,
    Id_producto     INT            NOT NULL,
    Cantidad        INT            NOT NULL,
    precio_unitario DECIMAL(10, 2) NOT NULL,

    CONSTRAINT FK_DETALLEORDEN_ORDENES   FOREIGN KEY (Id_orden)    REFERENCES ORDENES(Id_orden),
    CONSTRAINT FK_DETALLEORDEN_PRODUCTOS FOREIGN KEY (Id_producto) REFERENCES PRODUCTOS(Id_producto),
    CONSTRAINT CK_DETALLEORDEN_CANTIDAD CHECK (Cantidad > 0),
    CONSTRAINT CK_DETALLEORDEN_PRECIO   CHECK (precio_unitario >= 0)
);
GO

-- Cada entrada o salida de stock que provoca una orden completada
IF OBJECT_ID('dbo.MOVIMIENTOS_INVENTARIO', 'U') IS NULL
CREATE TABLE MOVIMIENTOS_INVENTARIO (
    Id_movimiento INT PRIMARY KEY IDENTITY(1,1),
    Id_producto   INT         NOT NULL,
    Id_orden      INT,
    Tipo          VARCHAR(10) NOT NULL,
    Cantidad      INT         NOT NULL,
    Observaciones NVARCHAR(255),
    Fecha         DATETIME DEFAULT GETDATE(),

    CONSTRAINT FK_MOVIMIENTOS_INVENTARIO_PRODUCTOS FOREIGN KEY (Id_producto) REFERENCES PRODUCTOS(Id_producto),
    CONSTRAINT FK_MOVIMIENTOS_INVENTARIO_ORDENES   FOREIGN KEY (Id_orden)    REFERENCES ORDENES(Id_orden),
    CONSTRAINT CK_MOVIMIENTOS_INVENTARIO_TIPO     CHECK (Tipo IN ('Entrada', 'Salida')),
    CONSTRAINT CK_MOVIMIENTOS_INVENTARIO_CANTIDAD CHECK (Cantidad > 0)
);
GO

/* ---------- Datos de contacto de la tienda ---------- */
IF OBJECT_ID('dbo.SOPORTE', 'U') IS NULL
CREATE TABLE SOPORTE (
    Id_soporte INT PRIMARY KEY IDENTITY(1,1),
    Correo     VARCHAR(100),
    Telefono   VARCHAR(20),
    Direccion  NVARCHAR(255),
    Horario    NVARCHAR(100),
    CREATE_at  DATETIME DEFAULT GETDATE()
);
GO


/* ---------- Chat de soporte ---------- */
-- Una conversación la empieza un Cliente; la contestan el Administrador y los Empleados
IF OBJECT_ID('dbo.CONVERSACION', 'U') IS NULL
CREATE TABLE CONVERSACION (
    Id_conversacion INT PRIMARY KEY IDENTITY(1,1),
    Id_login        INT          NOT NULL,          -- el cliente que la empezó
    Asunto          NVARCHAR(100) NOT NULL,
    Estado          VARCHAR(20)  NOT NULL CONSTRAINT DF_CONVERSACION_ESTADO DEFAULT 'Abierta',
    CREATE_at       DATETIME     DEFAULT GETDATE(),

    CONSTRAINT FK_CONVERSACION_LOGIN  FOREIGN KEY (Id_login) REFERENCES LOGIN(Id_login),
    CONSTRAINT CK_CONVERSACION_ESTADO CHECK (Estado IN ('Abierta', 'Cerrada'))
);
GO

IF OBJECT_ID('dbo.MENSAJE', 'U') IS NULL
CREATE TABLE MENSAJE (
    Id_mensaje      INT PRIMARY KEY IDENTITY(1,1),
    Id_conversacion INT           NOT NULL,
    Id_login        INT           NOT NULL,         -- quién lo escribió (el cliente o alguien del personal)
    Texto           NVARCHAR(1000) NOT NULL,
    CREATE_at       DATETIME      DEFAULT GETDATE(),

    CONSTRAINT FK_MENSAJE_CONVERSACION FOREIGN KEY (Id_conversacion) REFERENCES CONVERSACION(Id_conversacion),
    CONSTRAINT FK_MENSAJE_LOGIN        FOREIGN KEY (Id_login)        REFERENCES LOGIN(Id_login)
);
GO
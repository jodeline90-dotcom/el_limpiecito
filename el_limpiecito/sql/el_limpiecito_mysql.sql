-- ============================================================
-- Base de Datos MySQL: El Limpiecito
-- Archivo de migración compatible con phpMyAdmin / XAMPP
-- ============================================================

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

-- --------------------------------------------------------

-- Tabla: Usuario
CREATE TABLE `Usuario` (
  `id` VARCHAR(36) NOT NULL,
  `nombre` VARCHAR(100) NOT NULL,
  `email` VARCHAR(100) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `telefono` VARCHAR(20) DEFAULT NULL,
  `foto_url` VARCHAR(255) DEFAULT NULL,
  `rol` VARCHAR(20) NOT NULL DEFAULT 'cliente',
  `activo` TINYINT(1) NOT NULL DEFAULT 1,
  `nivel` VARCHAR(20) DEFAULT 'Nuevo',
  `fecha_creacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insertar usuario admin inicial por defecto (password: admin123)
-- Hash generado usando password_hash('admin123', PASSWORD_DEFAULT)
INSERT INTO `Usuario` (`id`, `nombre`, `email`, `password_hash`, `telefono`, `rol`, `activo`, `nivel`) VALUES
(UUID(), 'Administrador Principal', 'admin@ellimpiecito.com', '$2y$10$wE0p7M1gO1A0h2F6t.dJTu/91BqzqR2XqZ5O5c5l2nB0n4a9jCgP2', '5551234567', 'admin', 1, 'VIP');

-- --------------------------------------------------------

-- Tabla: Categoria
CREATE TABLE `Categoria` (
  `id` VARCHAR(36) NOT NULL,
  `nombre` VARCHAR(100) NOT NULL,
  `slug` VARCHAR(100) NOT NULL,
  `descripcion` TEXT DEFAULT NULL,
  `icono` VARCHAR(50) DEFAULT NULL,
  `fecha_creacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `slug` (`slug`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Categorías por defecto
INSERT INTO `Categoria` (`id`, `nombre`, `slug`, `icono`) VALUES
(UUID(), 'Limpieza del Hogar', 'limpieza-hogar', '🏠'),
(UUID(), 'Lavandería', 'lavanderia', '🧺'),
(UUID(), 'Desinfectantes', 'desinfectantes', '🛡️'),
(UUID(), 'Cuidado Personal', 'cuidado-personal', '🧼');

-- --------------------------------------------------------

-- Tabla: Proveedor
CREATE TABLE `Proveedor` (
  `id` VARCHAR(36) NOT NULL,
  `nombre` VARCHAR(200) NOT NULL,
  `contacto_nombre` VARCHAR(150) DEFAULT NULL,
  `email` VARCHAR(100) DEFAULT NULL,
  `telefono` VARCHAR(20) DEFAULT NULL,
  `direccion` TEXT DEFAULT NULL,
  `notas` TEXT DEFAULT NULL,
  `fecha_creacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

-- Tabla: Producto
CREATE TABLE `Producto` (
  `id` VARCHAR(36) NOT NULL,
  `nombre` VARCHAR(200) NOT NULL,
  `descripcion` TEXT DEFAULT NULL,
  `precio` DECIMAL(10,2) NOT NULL,
  `precio_comparacion` DECIMAL(10,2) DEFAULT NULL,
  `stock` INT(11) NOT NULL DEFAULT 0,
  `stock_minimo` INT(11) NOT NULL DEFAULT 5,
  `sku` VARCHAR(50) DEFAULT NULL,
  `categoria_id` VARCHAR(36) DEFAULT NULL,
  `proveedor_id` VARCHAR(36) DEFAULT NULL,
  `activo` TINYINT(1) NOT NULL DEFAULT 1,
  `destacado` TINYINT(1) NOT NULL DEFAULT 0,
  `peso_gramos` INT(11) DEFAULT NULL,
  `unidad_medida` VARCHAR(20) DEFAULT NULL,
  `contador_visitas` INT(11) NOT NULL DEFAULT 0,
  `contador_ventas` INT(11) NOT NULL DEFAULT 0,
  `fecha_creacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `fecha_actualizacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `categoria_id` (`categoria_id`),
  KEY `proveedor_id` (`proveedor_id`),
  KEY `idx_producto_activo` (`activo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `Producto`
  ADD CONSTRAINT `fk_producto_categoria` FOREIGN KEY (`categoria_id`) REFERENCES `Categoria` (`id`) ON DELETE SET NULL,
  ADD CONSTRAINT `fk_producto_proveedor` FOREIGN KEY (`proveedor_id`) REFERENCES `Proveedor` (`id`) ON DELETE SET NULL;

-- --------------------------------------------------------

-- Tabla: Carrito
CREATE TABLE `Carrito` (
  `id` VARCHAR(36) NOT NULL,
  `usuario_id` VARCHAR(36) NOT NULL,
  `cupon_codigo` VARCHAR(50) DEFAULT NULL,
  `cupon_descuento_porcentaje` INT(11) DEFAULT NULL,
  `cupon_descuento_fijo` DECIMAL(10,2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `usuario_id` (`usuario_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `Carrito`
  ADD CONSTRAINT `fk_carrito_usuario` FOREIGN KEY (`usuario_id`) REFERENCES `Usuario` (`id`) ON DELETE CASCADE;

-- --------------------------------------------------------

-- Tabla: ItemCarrito
CREATE TABLE `ItemCarrito` (
  `id` VARCHAR(36) NOT NULL,
  `carrito_id` VARCHAR(36) NOT NULL,
  `producto_id` VARCHAR(36) NOT NULL,
  `cantidad` INT(11) NOT NULL,
  `precio_unitario` DECIMAL(10,2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `carrito_id` (`carrito_id`),
  KEY `producto_id` (`producto_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `ItemCarrito`
  ADD CONSTRAINT `fk_itemcarrito_carrito` FOREIGN KEY (`carrito_id`) REFERENCES `Carrito` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `fk_itemcarrito_producto` FOREIGN KEY (`producto_id`) REFERENCES `Producto` (`id`) ON DELETE CASCADE;

-- --------------------------------------------------------

-- Tabla: Direccion
CREATE TABLE `Direccion` (
  `id` VARCHAR(36) NOT NULL,
  `usuario_id` VARCHAR(36) NOT NULL,
  `calle` VARCHAR(200) NOT NULL,
  `ciudad` VARCHAR(100) NOT NULL,
  `estado` VARCHAR(100) NOT NULL,
  `codigo_postal` VARCHAR(10) NOT NULL,
  `pais` VARCHAR(100) NOT NULL DEFAULT 'México',
  `es_predeterminada` TINYINT(1) NOT NULL DEFAULT 0,
  `referencia` VARCHAR(200) DEFAULT NULL,
  `fecha_creacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `usuario_id` (`usuario_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `Direccion`
  ADD CONSTRAINT `fk_direccion_usuario` FOREIGN KEY (`usuario_id`) REFERENCES `Usuario` (`id`) ON DELETE CASCADE;

-- --------------------------------------------------------

-- Tabla: Pedido
CREATE TABLE `Pedido` (
  `id` VARCHAR(36) NOT NULL,
  `usuario_id` VARCHAR(36) DEFAULT NULL,
  `estado` VARCHAR(50) NOT NULL DEFAULT 'pendiente',
  `subtotal` DECIMAL(10,2) NOT NULL,
  `descuento` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `total` DECIMAL(10,2) NOT NULL,
  `costo_envio` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `direccion_id` VARCHAR(36) DEFAULT NULL,
  `metodo_pago_id` VARCHAR(100) DEFAULT NULL,
  `notas` TEXT DEFAULT NULL,
  `stripe_payment_intent_id` VARCHAR(255) DEFAULT NULL,
  `cupon_codigo` VARCHAR(50) DEFAULT NULL,
  `fecha_creacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `fecha_actualizacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `usuario_id` (`usuario_id`),
  KEY `direccion_id` (`direccion_id`),
  KEY `idx_pedido_estado` (`estado`),
  KEY `idx_pedido_fecha` (`fecha_creacion` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `Pedido`
  ADD CONSTRAINT `fk_pedido_usuario` FOREIGN KEY (`usuario_id`) REFERENCES `Usuario` (`id`) ON DELETE SET NULL,
  ADD CONSTRAINT `fk_pedido_direccion` FOREIGN KEY (`direccion_id`) REFERENCES `Direccion` (`id`) ON DELETE SET NULL;

-- --------------------------------------------------------

-- Tabla: ItemPedido
CREATE TABLE `ItemPedido` (
  `id` VARCHAR(36) NOT NULL,
  `pedido_id` VARCHAR(36) NOT NULL,
  `producto_id` VARCHAR(36) DEFAULT NULL,
  `nombre_producto` VARCHAR(200) NOT NULL,
  `precio_unitario` DECIMAL(10,2) NOT NULL,
  `cantidad` INT(11) NOT NULL,
  `subtotal` DECIMAL(10,2) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `pedido_id` (`pedido_id`),
  KEY `producto_id` (`producto_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `ItemPedido`
  ADD CONSTRAINT `fk_itempedido_pedido` FOREIGN KEY (`pedido_id`) REFERENCES `Pedido` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `fk_itempedido_producto` FOREIGN KEY (`producto_id`) REFERENCES `Producto` (`id`) ON DELETE SET NULL;

-- --------------------------------------------------------

-- Tabla: HistorialEstadoPedido
CREATE TABLE `HistorialEstadoPedido` (
  `id` VARCHAR(36) NOT NULL,
  `pedido_id` VARCHAR(36) NOT NULL,
  `estado` VARCHAR(50) NOT NULL,
  `notas` TEXT DEFAULT NULL,
  `cambiado_por` VARCHAR(36) DEFAULT NULL,
  `fecha` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `pedido_id` (`pedido_id`),
  KEY `cambiado_por` (`cambiado_por`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `HistorialEstadoPedido`
  ADD CONSTRAINT `fk_historial_pedido` FOREIGN KEY (`pedido_id`) REFERENCES `Pedido` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `fk_historial_usuario` FOREIGN KEY (`cambiado_por`) REFERENCES `Usuario` (`id`) ON DELETE SET NULL;

-- --------------------------------------------------------

-- Tabla: Cupon
CREATE TABLE `Cupon` (
  `id` VARCHAR(36) NOT NULL,
  `codigo` VARCHAR(50) NOT NULL,
  `descuento_porcentaje` INT(11) DEFAULT NULL,
  `descuento_fijo` DECIMAL(10,2) DEFAULT NULL,
  `maximo_usos` INT(11) DEFAULT NULL,
  `usos_actuales` INT(11) NOT NULL DEFAULT 0,
  `fecha_vencimiento` DATETIME DEFAULT NULL,
  `monto_minimo` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `activo` TINYINT(1) NOT NULL DEFAULT 1,
  `fecha_creacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `codigo` (`codigo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

-- Tabla: Notificacion
CREATE TABLE `Notificacion` (
  `id` VARCHAR(36) NOT NULL,
  `usuario_id` VARCHAR(36) NOT NULL,
  `tipo` VARCHAR(50) NOT NULL,
  `mensaje` TEXT NOT NULL,
  `referencia_id` VARCHAR(36) DEFAULT NULL,
  `referencia_tipo` VARCHAR(50) DEFAULT NULL,
  `leida` TINYINT(1) NOT NULL DEFAULT 0,
  `fecha_creacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `usuario_id` (`usuario_id`),
  KEY `idx_notificacion_leida` (`usuario_id`, `leida`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `Notificacion`
  ADD CONSTRAINT `fk_notificacion_usuario` FOREIGN KEY (`usuario_id`) REFERENCES `Usuario` (`id`) ON DELETE CASCADE;

-- --------------------------------------------------------

-- Tabla: Favorito
CREATE TABLE `Favorito` (
  `id` VARCHAR(36) NOT NULL,
  `usuario_id` VARCHAR(36) NOT NULL,
  `producto_id` VARCHAR(36) NOT NULL,
  `fecha_agregado` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_favorito_usuario_producto` (`usuario_id`, `producto_id`),
  KEY `producto_id` (`producto_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `Favorito`
  ADD CONSTRAINT `fk_favorito_usuario` FOREIGN KEY (`usuario_id`) REFERENCES `Usuario` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `fk_favorito_producto` FOREIGN KEY (`producto_id`) REFERENCES `Producto` (`id`) ON DELETE CASCADE;

-- --------------------------------------------------------

-- Tabla: Resena
CREATE TABLE `Resena` (
  `id` VARCHAR(36) NOT NULL,
  `usuario_id` VARCHAR(36) NOT NULL,
  `producto_id` VARCHAR(36) NOT NULL,
  `estrellas` INT(11) NOT NULL,
  `comentario` TEXT DEFAULT NULL,
  `fecha_creacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_resena_usuario_producto` (`usuario_id`, `producto_id`),
  KEY `producto_id` (`producto_id`),
  CONSTRAINT `chk_resena_estrellas` CHECK (`estrellas` >= 1 AND `estrellas` <= 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `Resena`
  ADD CONSTRAINT `fk_resena_usuario` FOREIGN KEY (`usuario_id`) REFERENCES `Usuario` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `fk_resena_producto` FOREIGN KEY (`producto_id`) REFERENCES `Producto` (`id`) ON DELETE CASCADE;

-- --------------------------------------------------------

-- Tabla: Newsletter
CREATE TABLE `Newsletter` (
  `email` VARCHAR(255) NOT NULL,
  `fecha_registro` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

-- Tabla: CoberturaJerez
CREATE TABLE `CoberturaJerez` (
  `id` VARCHAR(36) NOT NULL,
  `colonia` VARCHAR(150) NOT NULL,
  `codigo_postal` VARCHAR(10) NOT NULL DEFAULT '99300',
  `costo_envio` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `tiempo_estimado` VARCHAR(50) NOT NULL DEFAULT 'Mismo día (1-3 horas)',
  `activo` TINYINT(1) NOT NULL DEFAULT 1,
  `fecha_creacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `colonia` (`colonia`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Coberturas por defecto (desde 002_cobertura_jerez.sql)
INSERT INTO `CoberturaJerez` (`id`, `colonia`, `codigo_postal`, `costo_envio`, `tiempo_estimado`, `activo`) VALUES
(UUID(), 'Centro', '99300', 0.00, '30-45 minutos', 1),
(UUID(), 'San Isidro', '99320', 15.00, '45-60 minutos', 1),
(UUID(), 'Guadalupe', '99330', 10.00, '40-60 minutos', 1),
(UUID(), 'Mercavilla', '99310', 25.00, '1 hora', 1),
(UUID(), 'Magisterial', '99340', 30.00, '1 - 1.5 horas', 1);

-- --------------------------------------------------------

-- Tabla: IntentoLogin
CREATE TABLE `IntentoLogin` (
  `id` INT(11) NOT NULL AUTO_INCREMENT,
  `ip` VARCHAR(45) NOT NULL,
  `email` VARCHAR(100) NOT NULL,
  `exitoso` TINYINT(1) NOT NULL,
  `fecha` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_intentologin_ip` (`ip`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

-- Trigger: Alerta Stock Bajo
DELIMITER $$
CREATE TRIGGER `alerta_stock_bajo_trigger` AFTER UPDATE ON `Producto` FOR EACH ROW BEGIN
    IF NEW.stock <= NEW.stock_minimo AND NEW.stock < OLD.stock THEN
        INSERT INTO `Notificacion` (`id`, `usuario_id`, `tipo`, `mensaje`, `referencia_id`, `referencia_tipo`, `leida`, `fecha_creacion`)
        SELECT 
            UUID(), 
            u.id, 
            'stock_bajo', 
            CONCAT('⚠️ Stock bajo: ', NEW.nombre, ' tiene solo ', NEW.stock, ' unidades (mín: ', NEW.stock_minimo, ')'), 
            NEW.id, 
            'producto', 
            0, 
            NOW()
        FROM `Usuario` u
        WHERE u.rol = 'admin' AND u.activo = 1;
    END IF;
END
$$
DELIMITER ;

COMMIT;

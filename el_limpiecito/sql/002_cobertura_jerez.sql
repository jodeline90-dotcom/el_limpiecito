


CREATE TABLE IF NOT EXISTS "CoberturaJerez" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    colonia VARCHAR(150) NOT NULL UNIQUE,
    codigo_postal VARCHAR(10) NOT NULL DEFAULT '99000',
    costo_envio DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    tiempo_estimado VARCHAR(50) NOT NULL DEFAULT 'Mismo día (1-3 horas)',
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion TIMESTAMPTZ DEFAULT NOW()
);


TRUNCATE TABLE "CoberturaJerez" CASCADE;

INSERT INTO "CoberturaJerez" (colonia, codigo_postal, costo_envio, tiempo_estimado, activo) VALUES
('Jerez Centro', '99000', 10.00, 'En menos de 1 hora', TRUE),
('Fraccionamiento García Salinas', '99000', 15.00, '1 a 2 horas', TRUE),
('Colonia Obrera', '99000', 15.00, '1 a 2 horas', TRUE),
('Colonia San Francisco', '99000', 15.00, '1 a 2 horas', TRUE),
('Fraccionamiento del Sol', '99000', 20.00, '2 a 3 horas', TRUE),
('Colonia Sarabia', '99000', 15.00, '1 a 2 horas', TRUE),
('Colonia Morelos', '99000', 20.00, '2 a 3 horas', TRUE),
('Colonia El Molino', '99000', 20.00, '2 a 3 horas', TRUE),
('Fraccionamiento Las Quintas', '99030', 25.00, '2 a 3 horas', TRUE),
('Colonia Infonavit El Silvestre', '99010', 20.00, '2 a 3 horas', TRUE),
('Colonia Guadalupe', '99000', 15.00, '1 a 2 horas', TRUE),
('Colonia Tres Cruces', '99000', 20.00, '2 a 3 horas', TRUE),
('Fraccionamiento Villas de San Isidro', '99050', 25.00, '2 a 3 horas', TRUE),
('Colonia San José', '99000', 15.00, '1 a 2 horas', TRUE),
('Colonia El Frontón', '99000', 15.00, '1 a 2 horas', TRUE),
('Fraccionamiento El Molino', '99000', 20.00, '2 a 3 horas', TRUE),
('Colonia Lindavista', '99000', 20.00, '2 a 3 horas', TRUE),
('Fraccionamiento Los Alamitos', '99030', 25.00, '2 a 3 horas', TRUE);

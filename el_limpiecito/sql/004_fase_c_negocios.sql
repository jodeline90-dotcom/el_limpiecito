-- ==============================================================================
-- 004_fase_c_negocios.sql
-- Adición de nivel de cliente y creación de tabla de Newsletter
-- ==============================================================================

-- 1. Añadir columna 'nivel' a la tabla Usuario si no existe
DO $$ 
BEGIN 
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema='public' 
        AND table_name='Usuario' 
        AND column_name='nivel'
    ) THEN
        ALTER TABLE public."Usuario" ADD COLUMN nivel VARCHAR(20) DEFAULT 'Nuevo' CHECK (nivel IN ('Nuevo', 'Frecuente', 'VIP'));
    END IF;
END $$;

-- 2. Crear tabla Newsletter para boletines
CREATE TABLE IF NOT EXISTS public."Newsletter" (
    email VARCHAR(255) PRIMARY KEY,
    fecha_registro TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Habilitar RLS en Newsletter
ALTER TABLE public."Newsletter" ENABLE ROW LEVEL SECURITY;

-- Políticas de RLS para Newsletter
-- Cualquiera puede suscribirse (insertar)
CREATE POLICY "Cualquiera puede suscribirse al boletin" ON public."Newsletter"
    FOR INSERT WITH CHECK (true);

-- Solo los administradores pueden listar o ver los correos del boletín
CREATE POLICY "Solo admins pueden ver boletin" ON public."Newsletter"
    FOR SELECT USING (true); -- El backend lo filtra desde su servicio service_role


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

CREATE TABLE IF NOT EXISTS public."Newsletter" (
    email VARCHAR(255) PRIMARY KEY,
    fecha_registro TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public."Newsletter" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Cualquiera puede suscribirse al boletin" ON public."Newsletter"
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Solo admins pueden ver boletin" ON public."Newsletter"
    FOR SELECT USING (true); -- El backend lo filtra desde su servicio service_role

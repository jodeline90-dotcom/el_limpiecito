-- ==============================================================================
-- 003_fase_b_interacciones.sql
-- Creación de tablas para Favoritos y Reseñas de Productos
-- ==============================================================================

-- 1. Tabla Favorito
CREATE TABLE IF NOT EXISTS public."Favorito" (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    usuario_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    producto_id UUID NOT NULL REFERENCES public."Producto"(id) ON DELETE CASCADE,
    fecha_agregado TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(usuario_id, producto_id)
);

-- 2. Tabla Resena
CREATE TABLE IF NOT EXISTS public."Resena" (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    usuario_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    producto_id UUID NOT NULL REFERENCES public."Producto"(id) ON DELETE CASCADE,
    estrellas INTEGER NOT NULL CHECK (estrellas >= 1 AND estrellas <= 5),
    comentario TEXT,
    fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(usuario_id, producto_id) -- Un usuario solo puede dejar 1 reseña por producto
);

-- Habilitar RLS en las nuevas tablas
ALTER TABLE public."Favorito" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."Resena" ENABLE ROW LEVEL SECURITY;

-- Políticas para Favorito (Los usuarios solo ven y modifican sus propios favoritos)
CREATE POLICY "Los usuarios pueden ver sus propios favoritos" ON public."Favorito"
    FOR SELECT USING (auth.uid() = usuario_id);

CREATE POLICY "Los usuarios pueden insertar sus propios favoritos" ON public."Favorito"
    FOR INSERT WITH CHECK (auth.uid() = usuario_id);

CREATE POLICY "Los usuarios pueden eliminar sus propios favoritos" ON public."Favorito"
    FOR DELETE USING (auth.uid() = usuario_id);

-- Políticas para Resena
-- Cualquiera puede ver las reseñas (incluso sin estar logueado)
CREATE POLICY "Cualquiera puede ver reseñas" ON public."Resena"
    FOR SELECT USING (true);

-- Solo los usuarios pueden insertar sus propias reseñas
CREATE POLICY "Usuarios pueden insertar sus propias reseñas" ON public."Resena"
    FOR INSERT WITH CHECK (auth.uid() = usuario_id);

-- Admins pueden borrar reseñas, y el propio usuario puede borrar la suya
CREATE POLICY "Usuarios pueden borrar sus propias reseñas" ON public."Resena"
    FOR DELETE USING (auth.uid() = usuario_id);

-- OJO: No se otorga permiso de actualización pública, solo admins desde el panel podrían moderarlas 
-- (asumiendo que los admins acceden saltándose RLS con el rol service_role del backend)

-- NOTA IMPORTANT: El backend usa la llave de servicio (service_role) por lo que salta las reglas RLS 
-- al hacer llamadas directas en FastAPI, pero las reglas anteriores protegen la base de datos 
-- si alguna vez se conecta directamente desde el frontend.

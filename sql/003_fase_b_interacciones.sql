


CREATE TABLE IF NOT EXISTS public."Favorito" (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    usuario_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    producto_id UUID NOT NULL REFERENCES public."Producto"(id) ON DELETE CASCADE,
    fecha_agregado TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(usuario_id, producto_id)
);


CREATE TABLE IF NOT EXISTS public."Resena" (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    usuario_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    producto_id UUID NOT NULL REFERENCES public."Producto"(id) ON DELETE CASCADE,
    estrellas INTEGER NOT NULL CHECK (estrellas >= 1 AND estrellas <= 5),
    comentario TEXT,
    fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(usuario_id, producto_id) -- Un usuario solo puede dejar 1 reseña por producto
);


ALTER TABLE public."Favorito" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."Resena" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Los usuarios pueden ver sus propios favoritos" ON public."Favorito"
    FOR SELECT USING (auth.uid() = usuario_id);

CREATE POLICY "Los usuarios pueden insertar sus propios favoritos" ON public."Favorito"
    FOR INSERT WITH CHECK (auth.uid() = usuario_id);

CREATE POLICY "Los usuarios pueden eliminar sus propios favoritos" ON public."Favorito"
    FOR DELETE USING (auth.uid() = usuario_id);


CREATE POLICY "Cualquiera puede ver reseñas" ON public."Resena"
    FOR SELECT USING (true);

CREATE POLICY "Usuarios pueden insertar sus propias reseñas" ON public."Resena"
    FOR INSERT WITH CHECK (auth.uid() = usuario_id);


CREATE POLICY "Usuarios pueden borrar sus propias reseñas" ON public."Resena"
    FOR DELETE USING (auth.uid() = usuario_id);



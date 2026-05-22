
CREATE OR REPLACE FUNCTION incrementar_visitas_producto(p_id UUID)
RETURNS void LANGUAGE sql SECURITY DEFINER AS $$
  UPDATE "Producto"
  SET contador_visitas = COALESCE(contador_visitas, 0) + 1
  WHERE id = p_id;
$$;


CREATE OR REPLACE FUNCTION vaciar_carrito(p_usuario_id UUID)
RETURNS void LANGUAGE sql SECURITY DEFINER AS $$
  DELETE FROM "ItemCarrito"
  WHERE carrito_id = (SELECT id FROM "Carrito" WHERE usuario_id = p_usuario_id LIMIT 1);
  UPDATE "Carrito"
  SET cupon_codigo = NULL, cupon_descuento_porcentaje = NULL, cupon_descuento_fijo = NULL
  WHERE usuario_id = p_usuario_id;
$$;


DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Pedido' AND column_name='stripe_payment_intent_id')
  THEN ALTER TABLE "Pedido" ADD COLUMN stripe_payment_intent_id TEXT; END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Pedido' AND column_name='cupon_codigo')
  THEN ALTER TABLE "Pedido" ADD COLUMN cupon_codigo TEXT; END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Carrito' AND column_name='cupon_codigo')
  THEN
    ALTER TABLE "Carrito"
      ADD COLUMN cupon_codigo TEXT,
      ADD COLUMN cupon_descuento_porcentaje INTEGER,
      ADD COLUMN cupon_descuento_fijo DECIMAL(10,2);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ItemPedido' AND column_name='nombre_producto')
  THEN ALTER TABLE "ItemPedido" ADD COLUMN nombre_producto TEXT; END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ItemCarrito' AND column_name='precio_unitario')
  THEN ALTER TABLE "ItemCarrito" ADD COLUMN precio_unitario DECIMAL(10,2); END IF;
END $$;

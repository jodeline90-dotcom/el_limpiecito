<?php


function handle_carrito_routes($method, $segments, $data) {
    $action = $segments[1] ?? '';
    $pdo = get_db_connection();
    $user = get_authenticated_user(); // requiere auth
    
    // Obtener carrito del usuario
    $stmt = $pdo->prepare("SELECT * FROM Carrito WHERE usuario_id = ?");
    $stmt->execute([$user['id']]);
    $carrito = $stmt->fetch();
    if (!$carrito) {
        send_error_response("Carrito no encontrado para este usuario", 404);
    }

    // GET /carrito
    if ($method === 'GET' && empty($action)) {
        $stmt = $pdo->prepare("SELECT ic.*, p.nombre as producto_nombre, p.stock 
                               FROM ItemCarrito ic 
                               JOIN Producto p ON ic.producto_id = p.id 
                               WHERE ic.carrito_id = ?");
        $stmt->execute([$carrito['id']]);
        $items = $stmt->fetchAll();
        
        $subtotal = 0;
        foreach ($items as &$i) {
            $i['precio_unitario'] = (float)$i['precio_unitario'];
            $i['subtotal'] = $i['precio_unitario'] * $i['cantidad'];
            $subtotal += $i['subtotal'];
        }
        
        $descuento = 0;
        if ($carrito['cupon_codigo']) {
            $descuento_pct = $carrito['cupon_descuento_porcentaje'] ? ($subtotal * $carrito['cupon_descuento_porcentaje'] / 100) : 0;
            $descuento_fijo = $carrito['cupon_descuento_fijo'] ?? 0;
            $descuento = min($descuento_pct + $descuento_fijo, $subtotal);
        }
        
        send_json_response([
            "id" => $carrito['id'],
            "usuario_id" => $user['id'],
            "items" => $items,
            "subtotal" => $subtotal,
            "descuento" => $descuento,
            "total" => $subtotal - $descuento,
            "cupon_codigo" => $carrito['cupon_codigo']
        ]);
    }

    // POST /carrito/items
    if ($method === 'POST' && $action === 'items') {
        $prod_id = $data['producto_id'] ?? null;
        $cantidad = $data['cantidad'] ?? 1;
        
        if (!$prod_id) send_error_response("Falta producto_id");
        
        $stmt = $pdo->prepare("SELECT id, precio, stock FROM Producto WHERE id = ?");
        $stmt->execute([$prod_id]);
        $prod = $stmt->fetch();
        if (!$prod) send_error_response("Producto no encontrado", 404);
        
        // Verificar si ya está en carrito
        $stmt = $pdo->prepare("SELECT id, cantidad FROM ItemCarrito WHERE carrito_id = ? AND producto_id = ?");
        $stmt->execute([$carrito['id'], $prod_id]);
        $item = $stmt->fetch();
        
        if ($item) {
            $nueva_cantidad = $item['cantidad'] + $cantidad;
            if ($nueva_cantidad > $prod['stock']) send_error_response("Stock insuficiente");
            
            $pdo->prepare("UPDATE ItemCarrito SET cantidad = ? WHERE id = ?")
                ->execute([$nueva_cantidad, $item['id']]);
        } else {
            if ($cantidad > $prod['stock']) send_error_response("Stock insuficiente");
            
            $pdo->prepare("INSERT INTO ItemCarrito (id, carrito_id, producto_id, cantidad, precio_unitario) VALUES (?, ?, ?, ?, ?)")
                ->execute([generate_uuid(), $carrito['id'], $prod_id, $cantidad, $prod['precio']]);
        }
        
        send_json_response(["mensaje" => "Producto agregado al carrito"]);
    }
    
    // DELETE /carrito/items/{id}
    if ($method === 'DELETE' && $action === 'items' && !empty($segments[2])) {
        $item_id = $segments[2];
        $pdo->prepare("DELETE FROM ItemCarrito WHERE id = ? AND carrito_id = ?")
            ->execute([$item_id, $carrito['id']]);
        send_json_response(["mensaje" => "Item eliminado"]);
    }
    
    // PUT /carrito/items/{id}
    if ($method === 'PUT' && $action === 'items' && !empty($segments[2])) {
        $item_id = $segments[2];
        $cantidad = $data['cantidad'] ?? 1;
        
        if ($cantidad < 1) {
            $pdo->prepare("DELETE FROM ItemCarrito WHERE id = ? AND carrito_id = ?")->execute([$item_id, $carrito['id']]);
        } else {
            $pdo->prepare("UPDATE ItemCarrito SET cantidad = ? WHERE id = ? AND carrito_id = ?")
                ->execute([$cantidad, $item_id, $carrito['id']]);
        }
        send_json_response(["mensaje" => "Cantidad actualizada"]);
    }
    
    // POST /carrito/cupon
    if ($method === 'POST' && $action === 'cupon') {
        $codigo = strtoupper(trim($data['codigo'] ?? ''));
        if (!$codigo) send_error_response("Código requerido");
        
        $pdo->beginTransaction();
        try {
            $stmt = $pdo->prepare("SELECT * FROM Cupon WHERE codigo = ? AND activo = 1 FOR UPDATE");
            $stmt->execute([$codigo]);
            $cupon = $stmt->fetch();
            
            if (!$cupon || ($cupon['fecha_vencimiento'] && strtotime($cupon['fecha_vencimiento']) < time())) {
                throw new Exception("Cupón inválido o vencido");
            }
            if ($cupon['maximo_usos'] && $cupon['usos_actuales'] >= $cupon['maximo_usos']) {
                throw new Exception("Cupón agotado");
            }
            
            // Se asocia al carrito
            $pdo->prepare("UPDATE Carrito SET cupon_codigo = ?, cupon_descuento_porcentaje = ?, cupon_descuento_fijo = ? WHERE id = ?")
                ->execute([$cupon['codigo'], $cupon['descuento_porcentaje'], $cupon['descuento_fijo'], $carrito['id']]);
                
            $pdo->commit();
            send_json_response([
                "mensaje" => "Cupón aplicado correctamente",
                "descuento_porcentaje" => $cupon['descuento_porcentaje'],
                "descuento_fijo" => $cupon['descuento_fijo']
            ]);
        } catch (Exception $e) {
            $pdo->rollBack();
            send_error_response($e->getMessage());
        }
    }

    send_error_response("Ruta de carrito no encontrada", 404);
}

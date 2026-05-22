<?php


function handle_pedidos_routes($method, $segments, $data) {
    $action = $segments[1] ?? '';
    $pdo = get_db_connection();
    $user = get_authenticated_user();

    // GET /pedidos
    if ($method === 'GET' && empty($action)) {
        $stmt = $pdo->prepare("SELECT p.*, d.calle, d.ciudad, d.estado as dir_estado, d.codigo_postal 
                               FROM Pedido p 
                               LEFT JOIN Direccion d ON p.direccion_id = d.id 
                               WHERE p.usuario_id = ? ORDER BY p.fecha_creacion DESC");
        $stmt->execute([$user['id']]);
        $pedidos = $stmt->fetchAll();
        
        foreach ($pedidos as &$p) {
            $stmt_items = $pdo->prepare("SELECT * FROM ItemPedido WHERE pedido_id = ?");
            $stmt_items->execute([$p['id']]);
            $p['items'] = $stmt_items->fetchAll();
            $p['total'] = (float)$p['total'];
            $p['subtotal'] = (float)$p['subtotal'];
            $p['descuento'] = (float)$p['descuento'];
        }
        
        send_json_response([
            "pedidos" => $pedidos,
            "total" => count($pedidos)
        ]);
    }

    // POST /pedidos (Crear Pedido Atómico)
    if ($method === 'POST' && empty($action)) {
        $direccion_id = $data['direccion_id'] ?? null;
        if (!$direccion_id) send_error_response("Dirección requerida");

        $pdo->beginTransaction();
        try {
            // Verificar dirección
            $stmt = $pdo->prepare("SELECT id FROM Direccion WHERE id = ? AND usuario_id = ?");
            $stmt->execute([$direccion_id, $user['id']]);
            if (!$stmt->fetch()) throw new Exception("Dirección no encontrada");

            // Obtener carrito
            $stmt = $pdo->prepare("SELECT * FROM Carrito WHERE usuario_id = ? FOR UPDATE");
            $stmt->execute([$user['id']]);
            $carrito = $stmt->fetch();
            if (!$carrito) throw new Exception("Carrito no encontrado");

            // Obtener items y stock (bloqueando filas Producto)
            $stmt = $pdo->prepare("SELECT ic.*, p.nombre, p.precio, p.stock 
                                   FROM ItemCarrito ic 
                                   JOIN Producto p ON ic.producto_id = p.id 
                                   WHERE ic.carrito_id = ? FOR UPDATE");
            $stmt->execute([$carrito['id']]);
            $items = $stmt->fetchAll();

            if (empty($items)) throw new Exception("Tu carrito está vacío");

            $subtotal = 0;
            foreach ($items as $item) {
                if ($item['cantidad'] > $item['stock']) {
                    throw new Exception("Stock insuficiente para: " . $item['nombre']);
                }
                $subtotal += ($item['precio'] * $item['cantidad']);
            }

            // Calcular descuento
            $descuento = 0;
            if ($carrito['cupon_codigo']) {
                $descto_pct = $carrito['cupon_descuento_porcentaje'] ? ($subtotal * $carrito['cupon_descuento_porcentaje'] / 100) : 0;
                $descto_fijo = $carrito['cupon_descuento_fijo'] ?? 0;
                $descuento = min($descto_pct + $descto_fijo, $subtotal);
                
                // Marcar uso de cupón
                $pdo->prepare("UPDATE Cupon SET usos_actuales = usos_actuales + 1 WHERE codigo = ?")
                    ->execute([$carrito['cupon_codigo']]);
            }
            $total = $subtotal - $descuento;

            $pedido_id = generate_uuid();
            $notas = $data['notas'] ?? null;

            // Crear Pedido
            $pdo->prepare("INSERT INTO Pedido (id, usuario_id, estado, subtotal, descuento, total, direccion_id, notas, cupon_codigo) 
                           VALUES (?, ?, 'pendiente', ?, ?, ?, ?, ?, ?)")
                ->execute([$pedido_id, $user['id'], $subtotal, $descuento, $total, $direccion_id, $notas, $carrito['cupon_codigo']]);

            // Descontar Stock e insertar ItemsPedido
            foreach ($items as $item) {
                $item_id = generate_uuid();
                $subt_item = $item['precio'] * $item['cantidad'];
                
                $pdo->prepare("INSERT INTO ItemPedido (id, pedido_id, producto_id, nombre_producto, precio_unitario, cantidad, subtotal) 
                               VALUES (?, ?, ?, ?, ?, ?, ?)")
                    ->execute([$item_id, $pedido_id, $item['producto_id'], $item['nombre'], $item['precio'], $item['cantidad'], $subt_item]);
                    
                $pdo->prepare("UPDATE Producto SET stock = stock - ?, contador_ventas = contador_ventas + ? WHERE id = ?")
                    ->execute([$item['cantidad'], $item['cantidad'], $item['producto_id']]);
            }

            // Vaciar carrito
            $pdo->prepare("DELETE FROM ItemCarrito WHERE carrito_id = ?")->execute([$carrito['id']]);
            $pdo->prepare("UPDATE Carrito SET cupon_codigo = NULL, cupon_descuento_porcentaje = NULL, cupon_descuento_fijo = NULL WHERE id = ?")
                ->execute([$carrito['id']]);

            // Historial
            $pdo->prepare("INSERT INTO HistorialEstadoPedido (id, pedido_id, estado) VALUES (?, ?, 'pendiente')")
                ->execute([generate_uuid(), $pedido_id]);

            // Notificación (síncrona en PHP)
            $pdo->prepare("INSERT INTO Notificacion (id, usuario_id, tipo, mensaje, referencia_id, referencia_tipo) VALUES (?, ?, 'pedido_confirmado', ?, ?, 'pedido')")
                ->execute([generate_uuid(), $user['id'], "Tu pedido #".strtoupper(substr($pedido_id,0,8))." fue recibido.", $pedido_id]);

            $pdo->commit();

            send_json_response([
                "id" => $pedido_id,
                "estado" => "pendiente",
                "total" => $total,
                "mensaje" => "Pedido creado correctamente"
            ], 201);

        } catch (Exception $e) {
            $pdo->rollBack();
            send_error_response("Error procesando pedido: " . $e->getMessage(), 400);
        }
    }

    // POST /pedidos/{id}/cancelar
    if ($method === 'POST' && $action && isset($segments[2]) && $segments[2] === 'cancelar') {
        $pedido_id = $action;
        $pdo->beginTransaction();
        try {
            $stmt = $pdo->prepare("SELECT estado FROM Pedido WHERE id = ? AND usuario_id = ? FOR UPDATE");
            $stmt->execute([$pedido_id, $user['id']]);
            $pedido = $stmt->fetch();

            if (!$pedido) throw new Exception("Pedido no encontrado");
            if ($pedido['estado'] !== 'pendiente') throw new Exception("Solo se pueden cancelar pedidos pendientes");

            $pdo->prepare("UPDATE Pedido SET estado = 'cancelado' WHERE id = ?")->execute([$pedido_id]);
            $pdo->prepare("INSERT INTO HistorialEstadoPedido (id, pedido_id, estado) VALUES (?, ?, 'cancelado')")
                ->execute([generate_uuid(), $pedido_id]);

            // Restaurar stock
            $stmt_items = $pdo->prepare("SELECT producto_id, cantidad FROM ItemPedido WHERE pedido_id = ?");
            $stmt_items->execute([$pedido_id]);
            foreach ($stmt_items->fetchAll() as $item) {
                if ($item['producto_id']) {
                    $pdo->prepare("UPDATE Producto SET stock = stock + ?, contador_ventas = GREATEST(0, contador_ventas - ?) WHERE id = ?")
                        ->execute([$item['cantidad'], $item['cantidad'], $item['producto_id']]);
                }
            }

            $pdo->commit();
            send_json_response(["mensaje" => "Pedido cancelado. El stock ha sido restaurado."]);

        } catch (Exception $e) {
            $pdo->rollBack();
            send_error_response("Error cancelando pedido: " . $e->getMessage());
        }
    }

    send_error_response("Ruta de pedidos no encontrada", 404);
}

<?php


function handle_admin_routes($method, $segments, $data) {
    $action = $segments[1] ?? '';
    $pdo = get_db_connection();
    $admin = get_authenticated_user(true); 

    // GET /admin/dashboard
    if ($method === 'GET' && $action === 'dashboard') {
        $hoy = date('Y-m-d');
        
        $stmt = $pdo->query("SELECT SUM(total) FROM Pedido WHERE DATE(fecha_creacion) = '$hoy' AND estado IN ('confirmado', 'en_preparacion', 'enviado', 'entregado')");
        $ventas_hoy = $stmt->fetchColumn() ?: 0;
        
        $stmt = $pdo->query("SELECT COUNT(*) FROM Pedido WHERE estado = 'pendiente'");
        $pedidos_pendientes = $stmt->fetchColumn();
        
        $stmt = $pdo->query("SELECT COUNT(*) FROM Producto WHERE stock <= stock_minimo");
        $alertas_stock = $stmt->fetchColumn();
        
        $stmt = $pdo->query("SELECT COUNT(*) FROM Usuario WHERE rol = 'cliente'");
        $clientes_totales = $stmt->fetchColumn();

        send_json_response([
            "ventas_hoy" => (float)$ventas_hoy,
            "pedidos_pendientes" => (int)$pedidos_pendientes,
            "alertas_stock" => (int)$alertas_stock,
            "clientes_totales" => (int)$clientes_totales
        ]);
    }

    // GET /admin/pedidos
    if ($method === 'GET' && $action === 'pedidos') {
        $stmt = $pdo->query("SELECT p.*, u.nombre as cliente_nombre FROM Pedido p LEFT JOIN Usuario u ON p.usuario_id = u.id ORDER BY p.fecha_creacion DESC LIMIT 100");
        send_json_response($stmt->fetchAll());
    }

    // GET /admin/inventario
    if ($method === 'GET' && $action === 'inventario') {
        $stmt = $pdo->query("SELECT id, nombre, stock, stock_minimo, precio FROM Producto ORDER BY stock ASC");
        send_json_response($stmt->fetchAll());
    }

    // GET /admin/clientes
    if ($method === 'GET' && $action === 'clientes') {
        $stmt = $pdo->query("SELECT id, nombre, email, telefono, activo, nivel, fecha_creacion FROM Usuario WHERE rol = 'cliente' ORDER BY fecha_creacion DESC");
        send_json_response($stmt->fetchAll());
    }

    // PATCH /admin/clientes/{id}/estado
    if ($method === 'PATCH' && $action === 'clientes' && !empty($segments[2])) {
        $cliente_id = $segments[2];
        $activo = isset($data['activo']) ? ($data['activo'] ? 1 : 0) : 1;
        $pdo->prepare("UPDATE Usuario SET activo = ? WHERE id = ? AND rol = 'cliente'")->execute([$activo, $cliente_id]);
        send_json_response(["mensaje" => "Estado actualizado"]);
    }
    
    
    if ($method === 'POST' && $action === 'usuarios' && ($segments[2] ?? '') === 'recalcular-niveles') {
        $stmt = $pdo->query("SELECT u.id, SUM(p.total) as gastado FROM Usuario u LEFT JOIN Pedido p ON u.id = p.usuario_id AND p.estado = 'entregado' WHERE u.rol = 'cliente' GROUP BY u.id");
        $clientes = $stmt->fetchAll();
        
        $actualizados = 0;
        foreach($clientes as $c) {
            $gastado = (float)($c['gastado'] ?? 0);
            $nivel = 'Nuevo';
            if ($gastado >= 5000.0) $nivel = 'VIP';
            elseif ($gastado >= 1000.0) $nivel = 'Frecuente';
            
            $pdo->prepare("UPDATE Usuario SET nivel = ? WHERE id = ?")->execute([$nivel, $c['id']]);
            $actualizados++;
        }
        send_json_response(["mensaje" => "Niveles recalculados para $actualizados clientes"]);
    }

    send_error_response("Ruta de admin no encontrada", 404);
}

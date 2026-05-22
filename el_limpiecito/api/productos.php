<?php


function handle_productos_routes($method, $segments, $data) {
    $action = $segments[1] ?? '';
    $subaction = $segments[2] ?? '';
    $pdo = get_db_connection();

    // GET /productos
    if ($method === 'GET' && empty($action)) {
        $categoria = $data['categoria'] ?? null;
        $precio_min = isset($data['precio_min']) ? (float)$data['precio_min'] : null;
        $precio_max = isset($data['precio_max']) ? (float)$data['precio_max'] : null;
        $orden = $data['orden'] ?? 'mas_nuevo';
        $busqueda = $data['busqueda'] ?? null;
        $pagina = isset($data['pagina']) ? max(1, (int)$data['pagina']) : 1;
        $limite = isset($data['limite']) ? min(100, max(1, (int)$data['limite'])) : 20;
        
        $where = ["p.activo = 1"];
        $params = [];
        
        if ($categoria) {
            $where[] = "p.categoria_id = ?";
            $params[] = $categoria;
        }
        if ($precio_min !== null) {
            $where[] = "p.precio >= ?";
            $params[] = $precio_min;
        }
        if ($precio_max !== null) {
            $where[] = "p.precio <= ?";
            $params[] = $precio_max;
        }
        if ($busqueda) {
            $where[] = "p.nombre LIKE ?";
            $params[] = "%$busqueda%";
        }
        
        $where_sql = implode(' AND ', $where);
        
        $order_sql = "p.fecha_creacion DESC";
        if ($orden === 'precio_asc') $order_sql = "p.precio ASC";
        if ($orden === 'precio_desc') $order_sql = "p.precio DESC";
        if ($orden === 'nombre') $order_sql = "p.nombre ASC";
        if ($orden === 'mas_vendido') $order_sql = "p.contador_ventas DESC";
        
        // Contar totales
        $count_stmt = $pdo->prepare("SELECT COUNT(*) FROM Producto p WHERE $where_sql");
        $count_stmt->execute($params);
        $total = $count_stmt->fetchColumn();
        
        // Paginar
        $offset = ($pagina - 1) * $limite;
        $sql = "SELECT p.*, c.nombre as categoria_nombre 
                FROM Producto p 
                LEFT JOIN Categoria c ON p.categoria_id = c.id 
                WHERE $where_sql 
                ORDER BY $order_sql 
                LIMIT $limite OFFSET $offset";
                
        $stmt = $pdo->prepare($sql);
        $stmt->execute($params);
        $productos = $stmt->fetchAll();
        
        // Mapeo 
        foreach ($productos as &$p) {
            $p['imagenes'] = []; 
            // Ratings mock o calculado 
            $stmt_r = $pdo->prepare("SELECT AVG(estrellas) as prom, COUNT(*) as tot FROM Resena WHERE producto_id = ?");
            $stmt_r->execute([$p['id']]);
            $res = $stmt_r->fetch();
            $p['promedio_estrellas'] = round($res['prom'] ?? 0, 1);
            $p['total_resenas'] = $res['tot'] ?? 0;
            
            // Forzar float
            $p['precio'] = (float)$p['precio'];
            $p['precio_comparacion'] = $p['precio_comparacion'] ? (float)$p['precio_comparacion'] : null;
        }
        
        send_json_response([
            "productos" => $productos,
            "total" => $total,
            "pagina" => $pagina,
            "total_paginas" => max(1, ceil($total / $limite))
        ]);
    }
    
    // POST /productos/{id}/resenas
    if ($method === 'POST' && $subaction === 'resenas') {
        $user = get_authenticated_user();
        $producto_id = $action;
        
        if (empty($data['estrellas']) || !is_numeric($data['estrellas'])) {
            send_error_response("Se requiere calificación de estrellas (1-5)");
        }
        
        // Insert o Update en MySQL (ON DUPLICATE KEY UPDATE)
        $sql = "INSERT INTO Resena (id, usuario_id, producto_id, estrellas, comentario, fecha_creacion) 
                VALUES (?, ?, ?, ?, ?, NOW()) 
                ON DUPLICATE KEY UPDATE estrellas = VALUES(estrellas), comentario = VALUES(comentario)";
        $pdo->prepare($sql)->execute([
            generate_uuid(), $user['id'], $producto_id, $data['estrellas'], $data['comentario'] ?? null
        ]);
        
        send_json_response(["mensaje" => "Reseña guardada exitosamente."]);
    }
    
    // GET /productos/{id}/resenas
    if ($method === 'GET' && $subaction === 'resenas') {
        $producto_id = $action;
        $stmt = $pdo->prepare("SELECT r.*, u.nombre as usuario_nombre, u.foto_url as usuario_foto 
                               FROM Resena r JOIN Usuario u ON r.usuario_id = u.id 
                               WHERE r.producto_id = ? ORDER BY r.fecha_creacion DESC");
        $stmt->execute([$producto_id]);
        send_json_response($stmt->fetchAll());
    }

    // GET /productos/{id}/relacionados
    if ($method === 'GET' && $subaction === 'relacionados') {
        $producto_id = $action;
        $stmt = $pdo->prepare("SELECT categoria_id FROM Producto WHERE id = ?");
        $stmt->execute([$producto_id]);
        $cat_id = $stmt->fetchColumn();
        
        if (!$cat_id) send_json_response([]);
        
        $stmt = $pdo->prepare("SELECT * FROM Producto WHERE categoria_id = ? AND id != ? AND activo = 1 LIMIT 4");
        $stmt->execute([$cat_id, $producto_id]);
        $relacionados = $stmt->fetchAll();
        foreach ($relacionados as &$p) {
            $p['imagenes'] = [];
            $p['precio'] = (float)$p['precio'];
        }
        send_json_response($relacionados);
    }

    // GET /productos/{id}
    if ($method === 'GET' && !empty($action) && empty($subaction)) {
        $stmt = $pdo->prepare("SELECT p.*, c.nombre as categoria_nombre FROM Producto p LEFT JOIN Categoria c ON p.categoria_id = c.id WHERE p.id = ?");
        $stmt->execute([$action]);
        $p = $stmt->fetch();
        
        if (!$p) send_error_response("Producto no encontrado", 404);
        
        // Incrementar visitas
        $pdo->prepare("UPDATE Producto SET contador_visitas = contador_visitas + 1 WHERE id = ?")->execute([$action]);
        
        // Formatear
        $p['imagenes'] = [];
        $stmt_r = $pdo->prepare("SELECT AVG(estrellas) as prom, COUNT(*) as tot FROM Resena WHERE producto_id = ?");
        $stmt_r->execute([$p['id']]);
        $res = $stmt_r->fetch();
        $p['promedio_estrellas'] = round($res['prom'] ?? 0, 1);
        $p['total_resenas'] = $res['tot'] ?? 0;
        
        $p['precio'] = (float)$p['precio'];
        $p['precio_comparacion'] = $p['precio_comparacion'] ? (float)$p['precio_comparacion'] : null;
        
        send_json_response($p);
    }
    
    send_error_response("Ruta de productos no encontrada", 404);
}

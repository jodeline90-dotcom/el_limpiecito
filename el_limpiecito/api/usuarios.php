<?php
// ============================================================
// api/usuarios.php - Endpoints de Perfil y Usuario
// ============================================================

function handle_usuarios_routes($method, $segments, $data) {
    $action = $segments[1] ?? '';
    $pdo = get_db_connection();

    // Cobertura (Público)
    if ($method === 'GET' && $action === 'cobertura') {
        $stmt = $pdo->query("SELECT * FROM CoberturaJerez WHERE activo = 1 ORDER BY colonia ASC");
        send_json_response($stmt->fetchAll());
    }

    // A partir de aquí requieren sesión
    $user = get_authenticated_user();

    // GET /usuarios/perfil
    if ($method === 'GET' && $action === 'perfil') {
        $stmt = $pdo->prepare("SELECT id, nombre, email, telefono, foto_url, rol, nivel, fecha_creacion FROM Usuario WHERE id = ?");
        $stmt->execute([$user['id']]);
        send_json_response($stmt->fetch());
    }

    // PUT /usuarios/perfil
    if ($method === 'PUT' && $action === 'perfil') {
        $nombre = $data['nombre'] ?? $user['nombre'];
        $telefono = $data['telefono'] ?? null;
        $pdo->prepare("UPDATE Usuario SET nombre = ?, telefono = ? WHERE id = ?")->execute([$nombre, $telefono, $user['id']]);
        send_json_response(["mensaje" => "Perfil actualizado"]);
    }

    // GET /usuarios/direcciones
    if ($method === 'GET' && $action === 'direcciones') {
        $stmt = $pdo->prepare("SELECT * FROM Direccion WHERE usuario_id = ? ORDER BY es_predeterminada DESC, fecha_creacion DESC");
        $stmt->execute([$user['id']]);
        send_json_response($stmt->fetchAll());
    }

    // POST /usuarios/direcciones
    if ($method === 'POST' && $action === 'direcciones') {
        if (empty($data['calle']) || empty($data['ciudad']) || empty($data['estado']) || empty($data['codigo_postal'])) {
            send_error_response("Datos de dirección incompletos");
        }
        
        $id = generate_uuid();
        if (!empty($data['es_predeterminada'])) {
            $pdo->prepare("UPDATE Direccion SET es_predeterminada = 0 WHERE usuario_id = ?")->execute([$user['id']]);
        }
        
        $stmt = $pdo->prepare("INSERT INTO Direccion (id, usuario_id, calle, ciudad, estado, codigo_postal, referencia, es_predeterminada) VALUES (?, ?, ?, ?, ?, ?, ?, ?)");
        $stmt->execute([$id, $user['id'], $data['calle'], $data['ciudad'], $data['estado'], $data['codigo_postal'], $data['referencia'] ?? null, empty($data['es_predeterminada']) ? 0 : 1]);
        
        send_json_response(["id" => $id, "mensaje" => "Dirección agregada"]);
    }

    // DELETE /usuarios/direcciones/{id}
    if ($method === 'DELETE' && $action === 'direcciones' && !empty($segments[2])) {
        $pdo->prepare("DELETE FROM Direccion WHERE id = ? AND usuario_id = ?")->execute([$segments[2], $user['id']]);
        send_json_response(["mensaje" => "Dirección eliminada"]);
    }

    // GET /usuarios/notificaciones
    if ($method === 'GET' && $action === 'notificaciones') {
        $stmt = $pdo->prepare("SELECT * FROM Notificacion WHERE usuario_id = ? ORDER BY fecha_creacion DESC LIMIT 50");
        $stmt->execute([$user['id']]);
        send_json_response($stmt->fetchAll());
    }

    // PATCH /usuarios/notificaciones/leer
    if ($method === 'PATCH' && $action === 'notificaciones' && ($segments[2] ?? '') === 'leer') {
        $pdo->prepare("UPDATE Notificacion SET leida = 1 WHERE usuario_id = ?")->execute([$user['id']]);
        send_json_response(["mensaje" => "Notificaciones marcadas como leídas"]);
    }

    send_error_response("Ruta de usuario no encontrada", 404);
}

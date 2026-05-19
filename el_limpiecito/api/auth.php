<?php
// ============================================================
// api/auth.php - Endpoints de Autenticación
// ============================================================

function handle_auth_routes($method, $segments, $data) {
    $action = $segments[1] ?? '';
    $pdo = get_db_connection();

    if ($method === 'POST' && $action === 'registro') {
        // Validar campos
        if (empty($data['nombre']) || empty($data['email']) || empty($data['password'])) {
            send_error_response("Nombre, email y contraseña son obligatorios");
        }
        
        $email = trim(strtolower($data['email']));
        $telefono = $data['telefono'] ?? null;
        
        // Comprobar si el correo existe
        $stmt = $pdo->prepare("SELECT id FROM Usuario WHERE email = ?");
        $stmt->execute([$email]);
        if ($stmt->fetch()) {
            send_error_response("El correo electrónico ya está registrado");
        }
        
        // Crear usuario
        $id = generate_uuid();
        $password_hash = password_hash($data['password'], PASSWORD_DEFAULT);
        
        $pdo->beginTransaction();
        try {
            $stmt = $pdo->prepare("INSERT INTO Usuario (id, nombre, email, password_hash, telefono) VALUES (?, ?, ?, ?, ?)");
            $stmt->execute([$id, $data['nombre'], $email, $password_hash, $telefono]);
            
            // Crear carrito enlazado
            $carrito_id = generate_uuid();
            $stmt = $pdo->prepare("INSERT INTO Carrito (id, usuario_id) VALUES (?, ?)");
            $stmt->execute([$carrito_id, $id]);
            
            // Crear notificación de bienvenida
            $notif_id = generate_uuid();
            $stmt = $pdo->prepare("INSERT INTO Notificacion (id, usuario_id, tipo, mensaje) VALUES (?, ?, 'bienvenida', '¡Bienvenido a El Limpiecito! Explora nuestro catálogo.')");
            $stmt->execute([$notif_id, $id]);
            
            $pdo->commit();
            
            // Enviar email de bienvenida (background o síncrono simple)
            $contenido = "
                <h2>¡Bienvenido, {$data['nombre']}! 🎉</h2>
                <p>Tu cuenta en <strong>El Limpiecito</strong> ha sido creada exitosamente.</p>
                <div class='info-box'>
                    <strong>¿Qué puedes hacer ahora?</strong>
                    <ul>
                        <li>Explorar nuestro catálogo de productos</li>
                        <li>Agregar artículos a tu carrito</li>
                        <li>Gestionar tus direcciones de envío</li>
                    </ul>
                </div>
                <p>¡Gracias por elegirnos!</p>";
            send_email($email, "¡Bienvenido a El Limpiecito! 🧹", email_base_template($contenido, "Bienvenida"));
            
            send_json_response([
                "mensaje" => "Registro exitoso. Ya puedes iniciar sesión.",
                "usuario" => ["id" => $id, "nombre" => $data['nombre'], "email" => $email]
            ], 201);
            
        } catch (Exception $e) {
            $pdo->rollBack();
            send_error_response("Error al registrar: " . $e->getMessage(), 500);
        }
    }
    
    if ($method === 'POST' && $action === 'login') {
        if (empty($data['email']) || empty($data['password'])) {
            send_error_response("Email y contraseña obligatorios");
        }
        
        $email = trim(strtolower($data['email']));
        $ip = $_SERVER['REMOTE_ADDR'];
        
        // Control de Rate Limiting (Brute Force)
        $stmt = $pdo->prepare("SELECT COUNT(*) FROM IntentoLogin WHERE ip = ? AND exitoso = 0 AND fecha > (NOW() - INTERVAL ? MINUTE)");
        $stmt->execute([$ip, RATE_LIMIT_LOGIN_VENTANA_MINUTOS]);
        $intentos = $stmt->fetchColumn();
        
        if ($intentos >= RATE_LIMIT_LOGIN_INTENTOS) {
            send_error_response("Demasiados intentos fallidos. Intenta más tarde.", 429);
        }
        
        $stmt = $pdo->prepare("SELECT * FROM Usuario WHERE email = ?");
        $stmt->execute([$email]);
        $user = $stmt->fetch();
        
        if ($user && password_verify($data['password'], $user['password_hash'])) {
            if (!$user['activo']) {
                send_error_response("Cuenta desactivada. Contacta soporte.", 403);
            }
            
            // Log successful attempt
            $pdo->prepare("INSERT INTO IntentoLogin (ip, email, exitoso) VALUES (?, ?, 1)")->execute([$ip, $email]);
            
            // Configurar Sesión en PHP y regresar el session_id como token
            if (session_status() === PHP_SESSION_NONE) {
                session_start();
            }
            $_SESSION['usuario'] = [
                'id' => $user['id'],
                'nombre' => $user['nombre'],
                'email' => $user['email'],
                'rol' => $user['rol'],
                'nivel' => $user['nivel']
            ];
            
            // Retornamos la respuesta tal cual lo espera el frontend
            send_json_response([
                "access_token" => session_id(),
                "token_type" => "bearer",
                "usuario" => $_SESSION['usuario']
            ]);
            
        } else {
            // Log failed attempt
            $pdo->prepare("INSERT INTO IntentoLogin (ip, email, exitoso) VALUES (?, ?, 0)")->execute([$ip, $email]);
            send_error_response("Credenciales incorrectas", 401);
        }
    }
    
    if ($method === 'POST' && $action === 'recuperar-password') {
        // En producción real, se insertaría un token en la DB
        // Por ahora simulamos la misma respuesta del FastAPI para UX
        send_json_response(["mensaje" => "Si el correo está registrado, recibirás un enlace."]);
    }
    
    if ($method === 'PUT' && $action === 'cambiar-password') {
        $user = get_authenticated_user();
        if (empty($data['password_actual']) || empty($data['password_nueva'])) {
            send_error_response("Contraseñas requeridas");
        }
        
        $stmt = $pdo->prepare("SELECT password_hash FROM Usuario WHERE id = ?");
        $stmt->execute([$user['id']]);
        $db_hash = $stmt->fetchColumn();
        
        if (!password_verify($data['password_actual'], $db_hash)) {
            send_error_response("La contraseña actual es incorrecta");
        }
        
        $new_hash = password_hash($data['password_nueva'], PASSWORD_DEFAULT);
        $pdo->prepare("UPDATE Usuario SET password_hash = ? WHERE id = ?")->execute([$new_hash, $user['id']]);
        
        send_json_response(["mensaje" => "Contraseña actualizada correctamente"]);
    }
    
    send_error_response("Ruta de autenticación no encontrada", 404);
}

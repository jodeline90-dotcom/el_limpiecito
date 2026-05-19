<?php
// ============================================================
// api/helpers.php - Funciones útiles y de seguridad
// ============================================================

require_once __DIR__ . '/config.php';
require_once __DIR__ . '/db.php';

// ─── Respuestas HTTP ────────────────────────────────────────────────────────

function send_json_response($data, $status_code = 200) {
    http_response_code($status_code);
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}

function send_error_response($message, $status_code = 400) {
    send_json_response(["detail" => $message], $status_code);
}

// ─── Generación UUID ───────────────────────────────────────────────────────

function generate_uuid() {
    // Genera un UUID v4 seguro
    $data = random_bytes(16);
    $data[6] = chr(ord($data[6]) & 0x0f | 0x40); // set version to 0100
    $data[8] = chr(ord($data[8]) & 0x3f | 0x80); // set bits 6-7 to 10
    return vsprintf('%s%s-%s-%s-%s-%s%s%s', str_split(bin2hex($data), 4));
}

// ─── Bridge de Autenticación ───────────────────────────────────────────────

/**
 * Retorna la información del usuario autenticado leyendo el Session ID 
 * desde el header de 'Authorization' (mantiene compatibilidad con el frontend).
 */
function get_authenticated_user($require_admin = false) {
    $headers = getallheaders();
    $token = null;
    
    // El frontend de "El Limpiecito" manda Authorization: Bearer <token>
    if (isset($headers['Authorization'])) {
        if (preg_match('/Bearer\s(\S+)/', $headers['Authorization'], $matches)) {
            $token = $matches[1];
        }
    }
    
    // Si tenemos un token, usamos ese ID para reanudar la sesión de PHP
    if ($token && preg_match('/^[a-zA-Z0-9,-]{22,64}$/', $token)) {
        session_id($token);
    }
    
    if (session_status() === PHP_SESSION_NONE) {
        session_start();
    }
    
    $user = isset($_SESSION['usuario']) ? $_SESSION['usuario'] : null;
    
    if (!$user) {
        send_error_response("No autorizado. Sesión inválida o expirada.", 401);
    }
    
    // Verificamos si la cuenta sigue activa
    $pdo = get_db_connection();
    $stmt = $pdo->prepare("SELECT activo, rol, nivel FROM Usuario WHERE id = ?");
    $stmt->execute([$user['id']]);
    $db_user = $stmt->fetch();
    
    if (!$db_user || !$db_user['activo']) {
        send_error_response("Cuenta desactivada", 403);
    }
    
    // Actualizar datos en sesión por si cambiaron (nivel, etc)
    $_SESSION['usuario']['rol'] = $db_user['rol'];
    $_SESSION['usuario']['nivel'] = $db_user['nivel'];
    $user['rol'] = $db_user['rol'];
    $user['nivel'] = $db_user['nivel'];
    
    if ($require_admin && $user['rol'] !== 'admin') {
        send_error_response("No tienes permisos de administrador", 403);
    }
    
    return $user;
}

// Obtener usuario opcional (por ejemplo, para visitas de carrito anónimas vs logueadas)
function get_optional_user() {
    $headers = getallheaders();
    $token = null;
    if (isset($headers['Authorization'])) {
        if (preg_match('/Bearer\s(\S+)/', $headers['Authorization'], $matches)) {
            $token = $matches[1];
        }
    }
    if ($token && preg_match('/^[a-zA-Z0-9,-]{22,64}$/', $token)) {
        session_id($token);
    }
    if (session_status() === PHP_SESSION_NONE) {
        session_start();
    }
    return isset($_SESSION['usuario']) ? $_SESSION['usuario'] : null;
}

// ─── Envíos de Correo Electrónico (Resend API Nativa) ──────────────────────

function send_email($to, $subject, $html_body) {
    if (empty(RESEND_API_KEY)) {
        error_log("Simulando envío de email a $to (API_KEY no configurada)");
        return true;
    }
    
    $url = 'https://api.resend.com/emails';
    $data = [
        "from" => EMAIL_FROM_NAME . " <" . EMAIL_FROM . ">",
        "to" => is_array($to) ? $to : [$to],
        "subject" => $subject,
        "html" => $html_body
    ];
    
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'Authorization: Bearer ' . RESEND_API_KEY,
        'Content-Type: application/json'
    ]);
    
    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    if ($http_code >= 200 && $http_code < 300) {
        return true;
    } else {
        error_log("Error Resend: " . $response);
        return false;
    }
}

function email_base_template($contenido, $titulo) {
    return "
    <!DOCTYPE html>
    <html lang='es'>
    <head>
        <meta charset='UTF-8'>
        <meta name='viewport' content='width=device-width, initial-scale=1.0'>
        <title>$titulo</title>
        <style>
            body { font-family: 'Segoe UI', Arial, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; }
            .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .header { background: linear-gradient(135deg, #0ea5e9, #0284c7); padding: 30px; text-align: center; }
            .header h1 { color: white; margin: 0; font-size: 24px; }
            .header p { color: rgba(255,255,255,0.85); margin: 5px 0 0; }
            .body { padding: 30px; color: #374151; line-height: 1.6; }
            .footer { background: #f8fafc; padding: 20px; text-align: center; color: #9ca3af; font-size: 13px; }
            .btn { display: inline-block; background: #0ea5e9; color: white !important; padding: 12px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 16px 0; }
            .info-box { background: #f0f9ff; border-left: 4px solid #0ea5e9; padding: 15px; border-radius: 0 8px 8px 0; margin: 15px 0; }
            table { width: 100%; border-collapse: collapse; margin: 15px 0; }
            th { background: #f1f5f9; padding: 10px; text-align: left; font-size: 13px; color: #6b7280; }
            td { padding: 10px; border-bottom: 1px solid #f1f5f9; }
            .total-row { font-weight: bold; background: #f8fafc; }
        </style>
    </head>
    <body>
        <div class='container'>
            <div class='header'>
                <h1>🧹 El Limpiecito</h1>
                <p>Tu tienda de productos de limpieza</p>
            </div>
            <div class='body'>
                $contenido
            </div>
            <div class='footer'>
                <p>© 2024 El Limpiecito. Todos los derechos reservados.</p>
                <p>Si no realizaste esta acción, ignora este correo.</p>
            </div>
        </div>
    </body>
    </html>
    ";
}

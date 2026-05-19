<?php
// ============================================================
// api/index.php - Controlador Frontal (Router de la API PHP)
// ============================================================

// Habilitar CORS
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, POST, PUT, DELETE, PATCH, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type, Authorization, X-Requested-With");
header("Content-Type: application/json; charset=UTF-8");

// Respuesta rápida a OPTIONS (Preflight)
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}

// Configurar manejo de errores en desarrollo
require_once __DIR__ . '/config.php';
if (APP_ENV === 'development') {
    ini_set('display_errors', 1);
    error_reporting(E_ALL);
} else {
    ini_set('display_errors', 0);
}

// Leer cuerpo JSON
$json_body = json_decode(file_get_contents('php://input'), true);
if (json_last_error() !== JSON_ERROR_NONE) {
    $json_body = []; // Fallback si no hay JSON
}
// Unimos GET params y JSON body (dando prioridad al body si chocan)
$request_data = array_merge($_GET, $json_body);

// Determinar el Path o Route
$request_uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$script_name = $_SERVER['SCRIPT_NAME'];
$base_path = dirname($script_name); // Esto normalmente será '/el_limpiecito/api'
$route = substr($request_uri, strlen($base_path));
$route = trim($route, '/'); // Ej: "productos/123"

$method = $_SERVER['REQUEST_METHOD'];

// Parseamos segmentos de la ruta
$segments = explode('/', $route);
$resource = $segments[0] ?? '';

// Dependencias base
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';

// Enrutamiento modular
try {
    switch ($resource) {
        case 'auth':
            require_once __DIR__ . '/auth.php';
            handle_auth_routes($method, $segments, $request_data);
            break;
            
        case 'productos':
            require_once __DIR__ . '/productos.php';
            handle_productos_routes($method, $segments, $request_data);
            break;
            
        case 'carrito':
            require_once __DIR__ . '/carrito.php';
            handle_carrito_routes($method, $segments, $request_data);
            break;
            
        case 'pedidos':
            require_once __DIR__ . '/pedidos.php';
            handle_pedidos_routes($method, $segments, $request_data);
            break;
            
        case 'pagos':
            require_once __DIR__ . '/pagos.php';
            handle_pagos_routes($method, $segments, $request_data);
            break;
            
        case 'usuarios':
            require_once __DIR__ . '/usuarios.php';
            handle_usuarios_routes($method, $segments, $request_data);
            break;
            
        case 'admin':
            require_once __DIR__ . '/admin.php';
            handle_admin_routes($method, $segments, $request_data);
            break;
            
        case '':
            send_json_response(["message" => "API El Limpiecito v1.0", "status" => "online"]);
            break;
            
        default:
            send_error_response("Ruta no encontrada: $route", 404);
            break;
    }
} catch (Exception $e) {
    error_log("Error no controlado: " . $e->getMessage());
    send_error_response("Error interno en el servidor", 500);
}

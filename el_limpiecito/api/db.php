<?php
// ============================================================
// api/db.php - Conexión PDO a MySQL (Singleton)
// ============================================================

require_once __DIR__ . '/config.php';

class DB {
    private static $instance = null;
    private $pdo;

    private function __construct() {
        $dsn = "mysql:host=" . DB_HOST . ";dbname=" . DB_NAME . ";charset=utf8mb4";
        $options = [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES   => false, // Usa sentencias preparadas reales
        ];
        
        try {
            $this->pdo = new PDO($dsn, DB_USER, DB_PASS, $options);
        } catch (PDOException $e) {
            http_response_code(500);
            echo json_encode(["detail" => "Error de conexión a la base de datos."]);
            error_log("Connection failed: " . $e->getMessage());
            exit;
        }
    }

    public static function getInstance() {
        if (self::$instance == null) {
            self::$instance = new DB();
        }
        return self::$instance;
    }

    public function getConnection() {
        return $this->pdo;
    }
}

// Helper para uso rápido
function get_db_connection() {
    return DB::getInstance()->getConnection();
}

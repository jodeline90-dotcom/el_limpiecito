<?php
// ============================================================
// api/config.example.php - Configuraciones base de El Limpiecito
// Copia este archivo como config.php e ingresa tus valores reales
// ============================================================

// --- Base de Datos (MySQL) ---
define('DB_HOST', 'localhost');
define('DB_USER', 'root');
define('DB_PASS', '');
define('DB_NAME', 'el_limpiecito');

// --- Entorno ---
define('APP_ENV', 'development'); // 'development' o 'production'

// --- Stripe ---
define('STRIPE_SECRET_KEY', 'sk_test_...');
define('STRIPE_WEBHOOK_SECRET', 'whsec_...');

// --- Resend (Correos Electrónicos) ---
define('RESEND_API_KEY', 're_...');
define('EMAIL_FROM', 'noreply@ellimpiecito.com');
define('EMAIL_FROM_NAME', 'El Limpiecito');

// --- Límite de Peticiones (Rate Limiting) ---
define('RATE_LIMIT_LOGIN_INTENTOS', 5);
define('RATE_LIMIT_LOGIN_VENTANA_MINUTOS', 15);

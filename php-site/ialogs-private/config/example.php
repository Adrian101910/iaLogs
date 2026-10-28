<?php
declare(strict_types=1);

// Copia a local.php FUERA de public_html y sustituye los valores del hosting.
return [
    'environment' => getenv('APP_ENV') ?: 'production',
    'base_path' => getenv('APP_BASE_PATH') ?: '',
    'secret' => getenv('APP_SECRET') ?: '', // mínimo 32 caracteres aleatorios
    'timezone' => 'Europe/Madrid',
    'session_secure' => getenv('SESSION_SECURE') !== '0',
    'db' => [
        'host' => getenv('DB_HOST') ?: 'localhost',
        'port' => (int)(getenv('DB_PORT') ?: 3306),
        'name' => getenv('DB_NAME') ?: 'ialogs_web',
        'user' => getenv('DB_USER') ?: 'ialogs_web',
        'password' => getenv('DB_PASSWORD') ?: '',
    ],
    'engine_url' => getenv('IALOGS_API_URL') ?: '', // HTTPS del motor, accesible desde el hosting
    'engine_key' => getenv('IALOGS_API_KEY') ?: '', // nunca llega al navegador
    'engine_timeout' => 130,
    'install_token_hash' => getenv('APP_INSTALL_TOKEN_HASH') ?: '', // SHA-256 del token temporal
];

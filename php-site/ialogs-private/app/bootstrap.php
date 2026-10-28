<?php
declare(strict_types=1);

const PRIVATE_ROOT = __DIR__ . '/..';
ini_set('display_errors', '0');
ini_set('log_errors', '1');
ini_set('session.use_strict_mode', '1');
ini_set('session.use_only_cookies', '1');
ini_set('session.use_trans_sid', '0');

require_once __DIR__ . '/functions.php';
require_once __DIR__ . '/database.php';
require_once __DIR__ . '/auth.php';
require_once __DIR__ . '/engine.php';
require_once __DIR__ . '/views.php';

set_exception_handler(function (Throwable $error): void {
    $status = $error instanceof WebError ? $error->status : 503;
    http_response_code($status);
    header('Content-Type: text/html; charset=utf-8');
    error_log('iaLogs PHP: ' . get_class($error)); // sin mensajes, consultas, claves ni credenciales
    $message = $error instanceof WebError ? $error->getMessage() : 'No se pudo completar la operación. Revisa la configuración privada y la conexión con MySQL.';
    echo '<!doctype html><html lang="es"><meta charset="utf-8"><title>iaLogs · Aviso</title><body><h1>iaLogs</h1><p>' . e($message) . '</p><p><a href="' . e(url('index.php')) . '">Volver al inicio</a></p></body></html>';
});

if (PHP_SAPI !== 'cli') {
    header('Content-Type: text/html; charset=utf-8');
    header('X-Content-Type-Options: nosniff');
    header('X-Frame-Options: DENY');
    header('Referrer-Policy: no-referrer');
    header("Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'");
    header('Cache-Control: no-store');
    $length = $_SERVER['CONTENT_LENGTH'] ?? '0';
    if (!ctype_digit((string)$length) || (int)$length > 2097152) {
        throw new WebError(413, 'La petición supera el límite de 2 MiB.');
    }
    session_name('ialogs_portal');
    session_set_cookie_params(['lifetime' => 0, 'path' => (config()['base_path'] ?: '') . '/',
        'secure' => config()['session_secure'], 'httponly' => true, 'samesite' => 'Lax']);
    session_start();
}
date_default_timezone_set(config()['timezone']);

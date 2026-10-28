<?php
declare(strict_types=1);
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
require __DIR__ . '/../app/bootstrap.php';
db()->exec(file_get_contents(__DIR__ . '/../database/001_initial.sql'));
echo "Migración MySQL 001 aplicada.\n";
if ((int)db()->query('SELECT COUNT(*) FROM users')->fetchColumn() === 0) {
    create_admin(getenv('APP_ADMIN_EMAIL') ?: '', getenv('APP_ADMIN_PASSWORD') ?: '');
    echo "Administrador creado. Las credenciales no se muestran.\n";
} else {
    echo "Administrador existente conservado.\n";
}

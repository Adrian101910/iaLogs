<?php
declare(strict_types=1);

function db(): PDO
{
    static $connection;
    if ($connection === null) {
        $settings = config()['db'];
        foreach (['host', 'name', 'user'] as $key) {
            if (!is_string($settings[$key]) || str_contains($settings[$key], ';') || str_contains($settings[$key], "\0")) {
                throw new RuntimeException('Invalid database configuration');
            }
        }
        $dsn = sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4', $settings['host'], $settings['port'], $settings['name']);
        $connection = new PDO($dsn, $settings['user'], $settings['password'], [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES => false,
        ]);
        $connection->exec("SET time_zone = '+00:00'");
    }
    return $connection;
}

function throttle(string $scope, string $identity, int $maximum, int $window): void
{
    if (strlen(config()['secret']) < 32) { throw new RuntimeException('APP_SECRET missing'); }
    $bucket = hash_hmac('sha256', $scope . ':' . $identity, config()['secret']);
    $now = time();
    $pdo = db();
    $pdo->beginTransaction();
    try {
        $pdo->prepare('INSERT IGNORE INTO rate_limits (bucket, window_start, hits) VALUES (?, ?, 0)')->execute([$bucket, $now]);
        $query = $pdo->prepare('SELECT window_start, hits FROM rate_limits WHERE bucket = ? FOR UPDATE');
        $query->execute([$bucket]);
        $row = $query->fetch();
        $reset = $now - (int)$row['window_start'] >= $window;
        $start = $reset ? $now : (int)$row['window_start'];
        $hits = $reset ? 1 : (int)$row['hits'] + 1;
        $pdo->prepare('UPDATE rate_limits SET window_start = ?, hits = ? WHERE bucket = ?')->execute([$start, $hits, $bucket]);
        $pdo->commit();
    } catch (Throwable $error) { if ($pdo->inTransaction()) { $pdo->rollBack(); } throw $error; }
    if ($hits > $maximum) { header('Retry-After: ' . $window); throw new WebError(429, 'Demasiados intentos. Espera antes de volver a intentarlo.'); }
}

function create_admin(string $email, string $password, string $name = 'Administrador'): void
{
    $email = strtolower(trim($email));
    if (!filter_var($email, FILTER_VALIDATE_EMAIL) || strlen($email) > 254 || strlen($password) < 12 || strlen($password) > 72) {
        throw new WebError(422, 'Introduce un email válido y una contraseña de entre 12 y 72 bytes.');
    }
    $pdo = db();
    $pdo->beginTransaction();
    try {
        $pdo->query("SELECT setting_value FROM app_settings WHERE setting_name = 'install_lock' FOR UPDATE")->fetch();
        if ((int)$pdo->query('SELECT COUNT(*) FROM users')->fetchColumn() > 0) { throw new WebError(409, 'La instalación ya tiene administrador.'); }
        $pdo->prepare('INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)')->execute([$email, $name, password_hash($password, PASSWORD_DEFAULT)]);
        $pdo->prepare("UPDATE app_settings SET setting_value = ? WHERE setting_name = 'install_lock'")->execute(['installed']);
        $pdo->commit();
    } catch (Throwable $error) { if ($pdo->inTransaction()) { $pdo->rollBack(); } throw $error; }
}

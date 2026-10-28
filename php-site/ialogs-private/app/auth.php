<?php
declare(strict_types=1);

function user(): ?array
{
    if (empty($_SESSION['user_id'])) { return null; }
    $now = time();
    if ($now - ($_SESSION['last_seen'] ?? 0) > 1800 || $now - ($_SESSION['login_at'] ?? 0) > 28800) {
        $_SESSION = [];
        session_regenerate_id(true);
        return null;
    }
    if ($now - ($_SESSION['rotated_at'] ?? 0) > 900) { session_regenerate_id(true); $_SESSION['rotated_at'] = $now; }
    $_SESSION['last_seen'] = $now;
    $query = db()->prepare('SELECT id, email, name FROM users WHERE id = ? AND active = 1');
    $query->execute([$_SESSION['user_id']]);
    return $query->fetch() ?: null;
}

function require_user(): array
{
    require_https();
    $current = user();
    if (!$current) { redirect('login.php'); }
    return $current;
}

function sign_in(string $email, string $password): bool
{
    $email = strtolower(trim($email));
    throttle('login-ip', $_SERVER['REMOTE_ADDR'] ?? 'cli', 30, 900);
    throttle('login-email', $email, 8, 900);
    $query = db()->prepare('SELECT id, password_hash, active FROM users WHERE email = ?');
    $query->execute([$email]);
    $row = $query->fetch();
    $dummy = '$2y$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi';
    $verified = password_verify($password, $row['password_hash'] ?? $dummy);
    if (!$row || !$verified || !(int)$row['active']) { return false; }
    session_regenerate_id(true);
    $_SESSION = ['user_id' => (int)$row['id'], 'login_at' => time(), 'last_seen' => time(), 'rotated_at' => time()];
    return true;
}

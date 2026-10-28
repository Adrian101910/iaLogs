<?php
require __DIR__ . '/_init.php';
require_https();
$hash = config()['install_token_hash'];
if (!preg_match('/^[a-f0-9]{64}$/D', $hash) || (int)db()->query('SELECT COUNT(*) FROM users')->fetchColumn() > 0) { throw new WebError(404, 'Página no disponible.'); }
$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    try {
        verify_csrf();
        throttle('install', $_SERVER['REMOTE_ADDR'] ?? '', 5, 3600);
        if (!hash_equals($hash, hash('sha256', field($_POST, 'token', 256)))) { throw new WebError(403, 'Token de instalación no válido.'); }
        $password = $_POST['password'] ?? null;
        if (!is_string($password)) { throw new WebError(422, 'Contraseña no válida.'); }
        create_admin(field($_POST, 'email', 254), $password, field($_POST, 'name', 120, 'Administrador'));
        redirect('login.php');
    } catch (WebError $exception) { http_response_code($exception->status); $error = $exception->getMessage(); }
}
public_header('Primer administrador');
?><main id="contenido" class="container install-page"><section class="form-card"><span class="eyebrow">INSTALACIÓN PRIVADA</span><h1>Crear administrador</h1><p>La base debe estar preparada con la migración SQL. Esta pantalla se desactiva en cuanto existe un administrador.</p><?php if ($error) { notice($error); } ?><form method="post" class="stack-form"><?= csrf_field() ?><label>Token temporal<input type="password" name="token" autocomplete="off" required maxlength="256"></label><label>Nombre<input name="name" required maxlength="120" autocomplete="name"></label><label>Email<input name="email" type="email" autocomplete="username" required maxlength="254"></label><label>Contraseña nueva<input name="password" type="password" autocomplete="new-password" minlength="12" maxlength="72" required></label><button class="button primary" type="submit">Crear administrador ↗</button></form></section></main><?php public_footer(); ?>

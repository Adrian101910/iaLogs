<?php
require __DIR__ . '/_init.php';
require_https();
if (user()) { redirect('eventos.php'); }
$error = ''; $email = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    try {
        verify_csrf();
        $email = field($_POST, 'email', 254);
        $password = $_POST['password'] ?? '';
        if (!is_string($password) || strlen($password) > 72 || !filter_var($email, FILTER_VALIDATE_EMAIL)) { throw new WebError(422, 'Introduce un email y una contraseña válidos.'); }
        if (!sign_in($email, $password)) { throw new WebError(401, 'El email o la contraseña no son correctos.'); }
        redirect('eventos.php');
    } catch (WebError $exception) { http_response_code($exception->status); $error = $exception->getMessage(); }
}
public_header('Acceso al panel');
?><main id="contenido" class="login-layout container"><section class="login-intro"><span class="pill">TU ESPACIO DE TRABAJO</span><h1>El contexto<br><em>te está esperando.</em></h1><p>Accede al explorador, revisa las evidencias y recupera tus diagnósticos.</p><div class="login-lines" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></div><span class="login-caption">Un solo recorrido. De los eventos al diagnóstico.</span></section><section class="form-card login-card"><span class="feature-icon">↗</span><span class="eyebrow">PANEL PRIVADO</span><h2>Bienvenido de nuevo.</h2><p>Utiliza la cuenta administrativa creada durante la instalación.</p><?php if ($error) { notice($error); } ?><form method="post" action="<?= e(url('login.php')) ?>" class="stack-form"><?= csrf_field() ?><label>Email<input name="email" type="email" autocomplete="username" required maxlength="254" value="<?= e($email) ?>"></label><label>Contraseña<input name="password" type="password" autocomplete="current-password" required maxlength="72"></label><button type="submit" class="button primary">Entrar al panel ↗</button></form><p class="form-footnote">El acceso corresponde a los administradores de esta instalación. Para recuperar una cuenta, contacta con su responsable.</p></section></main><?php public_footer(); ?>

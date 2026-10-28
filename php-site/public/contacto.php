<?php
require __DIR__ . '/_init.php';
$error = '';
$values = ['name' => '', 'email' => '', 'company' => '', 'message' => '', 'plan' => field($_GET, 'plan', 32, 'equipo')];
if (!isset(plans()[$values['plan']])) { $values['plan'] = 'equipo'; }
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    try {
        verify_csrf();
        foreach (['name' => 120, 'email' => 254, 'company' => 160, 'message' => 5000, 'plan' => 32] as $name => $max) { $values[$name] = field($_POST, $name, $max); }
        if ($values['name'] === '' || !filter_var($values['email'], FILTER_VALIDATE_EMAIL) || $values['message'] === '' || !isset(plans()[$values['plan']]) || ($_POST['privacy'] ?? '') !== '1' || field($_POST, 'website') !== '') {
            throw new WebError(422, 'Completa los campos y acepta el tratamiento de los datos para tramitar la solicitud.');
        }
        throttle('contact', $_SERVER['REMOTE_ADDR'] ?? '', 5, 3600);
        db()->prepare('INSERT INTO enquiries (name, email, company, plan, message) VALUES (?, ?, ?, ?, ?)')->execute([$values['name'], $values['email'], $values['company'], $values['plan'], $values['message']]);
        $_SESSION['enquiry_saved'] = true;
        redirect('contacto.php?guardado=1');
    } catch (WebError $exception) { http_response_code($exception->status); $error = $exception->getMessage(); }
}
public_header('Hablemos de tu instalación');
?><main id="contenido" class="container contact-grid"><section><span class="eyebrow">TU PRÓXIMO PASO</span><h1>Cuéntanos qué<br><em>quieres conectar.</em></h1><p>Describe tus fuentes, el volumen aproximado y dónde quieres instalar el motor. Define el alcance antes de empezar.</p><div class="contact-note"><span>↗</span><p>La solicitud quedará guardada para el administrador de esta web. No se envían correos automáticamente ni se activa una contratación.</p></div></section><section class="form-card">
<?php if (!empty($_GET['guardado']) && !empty($_SESSION['enquiry_saved'])) { unset($_SESSION['enquiry_saved']); notice('Solicitud guardada. El administrador puede consultarla desde el panel privado.', true); } ?>
<?php if ($error) { notice($error); } ?>
<form method="post" action="<?= e(url('contacto.php')) ?>" class="stack-form"><?= csrf_field() ?><label>Nombre<input name="name" required maxlength="120" autocomplete="name" value="<?= e($values['name']) ?>"></label><label>Email<input type="email" name="email" required maxlength="254" autocomplete="email" value="<?= e($values['email']) ?>"></label><label>Equipo o empresa <span class="optional">opcional</span><input name="company" maxlength="160" autocomplete="organization" value="<?= e($values['company']) ?>"></label><label>Opción de implantación<select name="plan"><?php foreach (plans() as $id => $plan) { ?><option value="<?= e($id) ?>" <?= $values['plan'] === $id ? 'selected' : '' ?>><?= e($plan['name']) ?></option><?php } ?></select></label><label>Qué necesitas conectar<textarea name="message" required rows="5" maxlength="5000" placeholder="Fuentes de logs, infraestructura y objetivo de la instalación…"><?= e($values['message']) ?></textarea></label><label class="honeypot" aria-hidden="true">Sitio web<input name="website" tabindex="-1" autocomplete="off"></label><label class="checkbox-label"><input type="checkbox" name="privacy" value="1" required> <span>Acepto que se guarden estos datos para tramitar esta solicitud. <a href="<?= e(url('privacidad.php')) ?>">Ver privacidad</a>.</span></label><button class="button primary" type="submit">Guardar solicitud ↗</button></form></section></main><?php public_footer(); ?>

<?php
declare(strict_types=1);

final class WebError extends RuntimeException
{
    public function __construct(public readonly int $status, string $message) { parent::__construct($message); }
}

function config(): array
{
    static $configuration;
    if ($configuration === null) {
        $configuration = require PRIVATE_ROOT . '/config/example.php';
        $local = PRIVATE_ROOT . '/config/local.php';
        if (is_file($local)) {
            $configuration = array_replace_recursive($configuration, require $local);
        }
        $base = $configuration['base_path'];
        if (!is_string($base) || ($base !== '' && !preg_match('#^/[a-zA-Z0-9/_-]+$#D', $base))) {
            throw new RuntimeException('Invalid base path');
        }
        $configuration['base_path'] = rtrim($base, '/');
    }
    return $configuration;
}

function e(mixed $value): string { return htmlspecialchars((string)$value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function url(string $path = ''): string { return config()['base_path'] . '/' . ltrim($path, '/'); }
function redirect(string $path): never { header('Location: ' . url($path), true, 303); exit; }
function post_only(): void
{
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') { header('Allow: POST'); throw new WebError(405, 'Esta acción requiere POST.'); }
}
function csrf(): string
{
    if (empty($_SESSION['csrf'])) { $_SESSION['csrf'] = bin2hex(random_bytes(32)); }
    return $_SESSION['csrf'];
}
function csrf_field(): string { return '<input type="hidden" name="csrf" value="' . e(csrf()) . '">'; }
function verify_csrf(): void
{
    $value = $_POST['csrf'] ?? null;
    if (!is_string($value) || !isset($_SESSION['csrf']) || !hash_equals($_SESSION['csrf'], $value)) {
        throw new WebError(403, 'El formulario ha caducado. Recarga la página y vuelve a intentarlo.');
    }
}
function field(array $input, string $key, int $max = 255, string $default = ''): string
{
    $value = $input[$key] ?? $default;
    if (!is_string($value) || strlen($value) > $max || !preg_match('//u', $value) || str_contains($value, "\0")) {
        throw new WebError(422, 'El campo ' . $key . ' no tiene un formato válido.');
    }
    return trim($value);
}
function uuid(string $value): string
{
    if (!preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/iD', $value)) {
        throw new WebError(422, 'El identificador no es válido.');
    }
    return strtolower($value);
}
function page_offset(): int
{
    $offset = $_GET['offset'] ?? '0';
    if (!is_string($offset) || !ctype_digit($offset) || (int)$offset > 1000000) { throw new WebError(422, 'Página no válida.'); }
    return (int)$offset;
}
function date_label(string $value): string
{
    if (preg_match('/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/D', $value)) { $value .= '+00:00'; }
    try { return (new DateTimeImmutable($value))->setTimezone(new DateTimeZone(config()['timezone']))->format('d/m/Y H:i:s'); }
    catch (Exception) { return $value; }
}
function require_https(): void
{
    $https = strtolower((string)($_SERVER['HTTPS'] ?? ''));
    if (config()['environment'] !== 'local' && !in_array($https, ['on', '1'], true) && ($_SERVER['SERVER_PORT'] ?? '') !== '443') {
        throw new WebError(400, 'Accede a esta página mediante HTTPS.');
    }
}
function plans(): array
{
    return [
        'local' => ['name' => 'Local', 'subtitle' => 'Empieza en tu infraestructura', 'price' => 'Tu infraestructura', 'description' => 'Una instalación propia para explorar tus eventos y probar el diagnóstico local.', 'features' => ['Explorador y filtros', 'Análisis con Ollama', 'API JSON, archivos y Docker'], 'cta' => 'Conocer la instalación'],
        'equipo' => ['name' => 'Equipo', 'subtitle' => 'Un espacio de trabajo compartido', 'price' => 'Consultar', 'description' => 'Planifica una instalación de iaLogs para los sistemas de tu equipo.', 'features' => ['Portal privado en PHP', 'Panel administrativo', 'Definición de fuentes y capacidad'], 'cta' => 'Solicitar información'],
        'integracion' => ['name' => 'Integración', 'subtitle' => 'Adapta el recorrido a tus sistemas', 'price' => 'A medida', 'description' => 'Define qué necesitas conectar y acuerda el alcance antes de empezar.', 'features' => ['Revisión de formatos', 'Plan de despliegue', 'Alcance y mantenimiento por definir'], 'cta' => 'Hablar de mi proyecto'],
    ];
}

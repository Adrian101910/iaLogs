<?php
declare(strict_types=1);
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
if (($argv[1] ?? '') === '--production-check') { putenv('APP_ENV=production'); }
require __DIR__ . '/../ialogs-private/app/bootstrap.php';

function check(bool $condition, string $message = 'La comprobación falló'): void { if (!$condition) { throw new RuntimeException($message); } }
function rejects(callable $action, int $status): void
{
    try { $action(); } catch (WebError $error) { check($error->status === $status, 'Estado de error incorrecto'); return; }
    throw new RuntimeException('La operación debía rechazarse');
}

if (($argv[1] ?? '') === '--production-check') {
    $_SERVER['HTTPS'] = 'off'; $_SERVER['SERVER_PORT'] = '80';
    rejects(fn() => require_https(), 400);
    try { engine('GET', '/health'); } catch (WebError $error) {
        check(str_contains($error->getMessage(), 'HTTPS'), 'La producción debe rechazar un motor HTTP');
        echo "production OK\n"; exit(0);
    }
    exit(1);
}
if (config()['db']['name'] !== 'ialogs_web_test') { throw new RuntimeException('Solo se permite la base aislada de pruebas.'); }
session_start();
db()->exec(file_get_contents(__DIR__ . '/../ialogs-private/database/001_initial.sql'));
// Únicamente la base temporal de pruebas, nunca la base del portal.
foreach (['users', 'enquiries', 'rate_limits'] as $table) { db()->exec('DELETE FROM ' . $table); }
$results = []; $failures = 0;
function test(string $name, callable $action): void
{
    global $results, $failures;
    try { $action(); $results[] = 'OK ' . $name; }
    catch (Throwable $error) { $failures++; $results[] = 'FAIL ' . $name . ': ' . get_class($error); }
}

test('migración idempotente en MySQL real', function (): void {
    db()->exec(file_get_contents(__DIR__ . '/../ialogs-private/database/001_initial.sql'));
    check((int)db()->query('SELECT COUNT(*) FROM schema_migrations WHERE version = 1')->fetchColumn() === 1);
    check(count(db()->query('SHOW INDEX FROM enquiries')->fetchAll()) >= 2);
});
test('escape de HTML y texto no confiable', function (): void {
    $html = e('<script>alert("x")</script>');
    check(!str_contains($html, '<script>') && str_contains($html, '&lt;script&gt;'));
});
test('validación de campos y UUID', function (): void {
    rejects(fn() => field(['name' => ['bad']], 'name'), 422);
    rejects(fn() => field(['name' => str_repeat('x', 256)], 'name'), 422);
    rejects(fn() => field(['name' => "bad\0text"], 'name'), 422);
    rejects(fn() => uuid('../../secrets'), 422);
    check(uuid('AA45CFF0-BC2D-4311-80A9-35C72C12196F') === 'aa45cff0-bc2d-4311-80a9-35c72c12196f');
});
test('formularios protegidos por CSRF', function (): void {
    $_POST = []; rejects(fn() => verify_csrf(), 403);
    $_POST['csrf'] = ['bad']; rejects(fn() => verify_csrf(), 403);
    $_POST['csrf'] = csrf(); verify_csrf();
});
test('acciones de escritura requieren POST', function (): void {
    $_SERVER['REQUEST_METHOD'] = 'GET'; rejects(fn() => post_only(), 405);
    $_SERVER['REQUEST_METHOD'] = 'POST'; post_only();
});
test('contraseñas cortas rechazadas', fn() => rejects(fn() => create_admin('admin@example.test', 'short'), 422));
test('alta administrativa y hash de contraseña', function (): void {
    create_admin('admin@example.test', 'Strong-test-password-123');
    $row = db()->query('SELECT * FROM users')->fetch();
    check($row['password_hash'] !== 'Strong-test-password-123');
    check(password_verify('Strong-test-password-123', $row['password_hash']));
});
test('el instalador no reemplaza al administrador', function (): void {
    rejects(fn() => create_admin('other@example.test', 'Another-password-123'), 409);
    check((int)db()->query('SELECT COUNT(*) FROM users')->fetchColumn() === 1);
});
test('autenticación y consultas parametrizadas', function (): void {
    check(!sign_in("x' OR 1=1 --", 'invalid'));
    check(!sign_in('admin@example.test', 'wrong-password'));
    check(empty($_SESSION['user_id']));
    $old = session_id(); check(sign_in('admin@example.test', 'Strong-test-password-123'));
    check(session_id() !== $old, 'La sesión debe regenerarse al autenticar');
    check(user()['email'] === 'admin@example.test');
});
test('caducidad por inactividad', function (): void {
    $_SESSION['last_seen'] = time() - 1801;
    check(user() === null && empty($_SESSION['user_id']));
});
test('límite de intentos incluso dentro del mismo segundo', function (): void {
    $identity = bin2hex(random_bytes(16));
    throttle('test', $identity, 2, 60); throttle('test', $identity, 2, 60);
    rejects(fn() => throttle('test', $identity, 2, 60), 429);
    $bucket = hash_hmac('sha256', 'test:' . $identity, config()['secret']);
    $query = db()->prepare('SELECT hits FROM rate_limits WHERE bucket = ?'); $query->execute([$bucket]);
    check((int)$query->fetchColumn() === 3);
});
test('solicitudes persistidas con Unicode y SQL no ejecutable', function (): void {
    $message = "'; DROP TABLE users; -- <script>literal</script>";
    db()->prepare('INSERT INTO enquiries (name,email,company,plan,message) VALUES (?,?,?,?,?)')->execute(['Equipo 🛠', 'example@example.test', '', 'equipo', $message]);
    check(db()->query('SELECT message FROM enquiries')->fetchColumn() === $message);
    check((int)db()->query('SELECT COUNT(*) FROM users')->fetchColumn() === 1);
});
test('fechas UTC de MySQL y del motor', function (): void {
    check(date_label('2026-10-28 12:00:00') === '28/10/2026 13:00:00');
    check(date_label('2026-10-28T12:00:00Z') === '28/10/2026 13:00:00');
});
test('motor desconectado y rutas restringidas', function (): void {
    try { engine('GET', '/health'); } catch (WebError $error) {
        check($error->status === 503 && !str_contains($error->getMessage(), config()['engine_key']));
        return;
    }
    throw new RuntimeException('El puerto de prueba debe estar desconectado');
});
test('producción exige HTTPS para acceso y conexión al motor', function (): void {
    $process = proc_open([PHP_BINARY, __FILE__, '--production-check'], [1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
    check(is_resource($process)); $output = stream_get_contents($pipes[1]); $errors = stream_get_contents($pipes[2]);
    fclose($pipes[1]); fclose($pipes[2]);
    check(proc_close($process) === 0 && str_contains($output, 'production OK') && $errors === '');
});
test('instalador web real: token, primer administrador y bloqueo posterior', function (): void {
    // Solamente la base temporal verificada al inicio de este archivo.
    db()->exec('DELETE FROM users');
    $probe = stream_socket_server('tcp://127.0.0.1:0', $errno, $message);
    check(is_resource($probe)); $address = stream_socket_get_name($probe, false); fclose($probe);
    $log = tempnam(sys_get_temp_dir(), 'ialogs-install-');
    $jar = tempnam(sys_get_temp_dir(), 'ialogs-cookie-');
    $environment = [...getenv(), 'APP_ENV' => 'local', 'APP_INSTALL_TOKEN_HASH' => hash('sha256', 'isolated-install-test-token')];
    $server = proc_open([PHP_BINARY, '-S', $address, '-t', dirname(__DIR__) . '/public'], [1 => ['file', $log, 'a'], 2 => ['file', $log, 'a']], $pipes, null, $environment);
    check(is_resource($server));
    $curl = curl_init('http://' . $address . '/instalar.php');
    curl_setopt_array($curl, [CURLOPT_RETURNTRANSFER => true, CURLOPT_CONNECTTIMEOUT => 1, CURLOPT_TIMEOUT => 2,
        CURLOPT_FOLLOWLOCATION => false, CURLOPT_COOKIEJAR => $jar, CURLOPT_COOKIEFILE => $jar, CURLOPT_PROXY => '']);
    try {
        $html = false;
        for ($attempt = 0; $attempt < 30; $attempt++) {
            $html = curl_exec($curl);
            if ($html !== false) { break; }
            usleep(100000);
        }
        check(is_string($html) && curl_getinfo($curl, CURLINFO_RESPONSE_CODE) === 200);
        check((bool)preg_match('/name="csrf" value="([a-f0-9]{64})"/', $html, $match));
        $form = ['csrf' => $match[1], 'token' => 'wrong-token', 'name' => 'Installer test', 'email' => 'installer@example.test', 'password' => 'Installer-password-123'];
        curl_setopt($curl, CURLOPT_POST, true); curl_setopt($curl, CURLOPT_POSTFIELDS, http_build_query($form));
        curl_exec($curl); check(curl_getinfo($curl, CURLINFO_RESPONSE_CODE) === 403);
        check((int)db()->query('SELECT COUNT(*) FROM users')->fetchColumn() === 0);
        $form['token'] = 'isolated-install-test-token'; curl_setopt($curl, CURLOPT_POSTFIELDS, http_build_query($form));
        curl_exec($curl); check(curl_getinfo($curl, CURLINFO_RESPONSE_CODE) === 303);
        check(db()->query('SELECT email FROM users')->fetchColumn() === 'installer@example.test');
        curl_setopt($curl, CURLOPT_HTTPGET, true); curl_exec($curl);
        check(curl_getinfo($curl, CURLINFO_RESPONSE_CODE) === 404);
    } finally {
        curl_close($curl); proc_terminate($server); proc_close($server);
        unlink($log); unlink($jar);
    }
});
session_write_close();
echo implode("\n", $results) . "\n";
echo (count($results) - $failures) . '/' . count($results) . " pruebas PHP correctas.\n";
exit($failures ? 1 : 0);

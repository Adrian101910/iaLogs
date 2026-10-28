<?php
declare(strict_types=1);

function engine(string $method, string $path, array $query = [], ?array $body = null): array
{
    $settings = config();
    $base = rtrim($settings['engine_url'], '/');
    $parts = parse_url($base);
    if (!$parts || empty($parts['host']) || !in_array($parts['scheme'] ?? '', ['http', 'https'], true)
        || isset($parts['user']) || isset($parts['pass']) || isset($parts['query']) || isset($parts['fragment'])
        || ($settings['environment'] !== 'local' && $parts['scheme'] !== 'https') || strlen($settings['engine_key']) < 32) {
        throw new WebError(503, 'El motor de iaLogs todavía no está conectado. Configura su URL HTTPS y su clave en el servidor.');
    }
    if (!preg_match('#^/(health|v1/(logs|analyses)(/[a-f0-9-]{36})?)$#D', $path)) { throw new RuntimeException('Invalid engine path'); }
    $handle = curl_init($base . $path . ($query ? '?' . http_build_query($query) : ''));
    $raw = '';
    $headers = ['Accept: application/json', 'X-API-Key: ' . $settings['engine_key']];
    if ($body !== null) { $headers[] = 'Content-Type: application/json'; }
    curl_setopt_array($handle, [
        CURLOPT_CUSTOMREQUEST => $method,
        CURLOPT_HTTPHEADER => $headers,
        CURLOPT_FOLLOWLOCATION => false,
        CURLOPT_PROXY => '',
        CURLOPT_SSL_VERIFYPEER => true,
        CURLOPT_SSL_VERIFYHOST => 2,
        CURLOPT_CONNECTTIMEOUT => 5,
        CURLOPT_TIMEOUT => $method === 'POST' ? min(150, (int)$settings['engine_timeout']) : 15,
        CURLOPT_WRITEFUNCTION => static function ($curl, string $chunk) use (&$raw): int {
            if (strlen($raw) + strlen($chunk) > 8388608) { return 0; }
            $raw .= $chunk;
            return strlen($chunk);
        },
    ]);
    if ($body !== null) { curl_setopt($handle, CURLOPT_POSTFIELDS, json_encode($body, JSON_THROW_ON_ERROR)); }
    $result = curl_exec($handle);
    $status = (int)curl_getinfo($handle, CURLINFO_RESPONSE_CODE);
    $errno = curl_errno($handle);
    curl_close($handle);
    if ($result === false) {
        throw new WebError(503, $errno === CURLE_OPERATION_TIMEDOUT ? 'El motor ha tardado demasiado. Consulta el historial antes de repetir el análisis.' : 'No se puede conectar con el motor de iaLogs. La web sigue disponible.');
    }
    if ($status < 200 || $status >= 300) {
        $messages = [401 => 'La clave del motor configurada en el servidor no es válida.', 404 => 'No se encontró el evento o análisis.',
            413 => 'La selección supera el contexto permitido. Selecciona menos eventos.', 422 => 'Revisa los filtros o la selección de eventos.',
            429 => 'El motor está ocupado. Vuelve a intentarlo en unos segundos.', 502 => 'El modelo devolvió un diagnóstico no válido.',
            503 => 'El motor, PostgreSQL o el modelo no están disponibles.', 504 => 'El modelo superó el tiempo límite. Consulta el historial antes de repetir.'];
        throw new WebError(in_array($status, [404, 413, 422, 429], true) ? $status : 503, $messages[$status] ?? 'El motor no pudo completar la operación.');
    }
    try { $data = json_decode($raw, true, 64, JSON_THROW_ON_ERROR); }
    catch (JsonException) { throw new WebError(502, 'El motor devolvió una respuesta no válida.'); }
    if (!is_array($data)) { throw new WebError(502, 'El motor devolvió una respuesta no válida.'); }
    return $data;
}

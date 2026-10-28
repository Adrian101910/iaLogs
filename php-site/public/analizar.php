<?php
require __DIR__ . '/_init.php'; $current = require_user(); post_only(); verify_csrf();
$ids = $_POST['log_ids'] ?? [];
if (!is_array($ids) || count($ids) < 1 || count($ids) > 50) { throw new WebError(422, 'Selecciona entre 1 y 50 eventos.'); }
$ids = array_map(static function ($value): string { if (!is_string($value)) { throw new WebError(422, 'Selección no válida.'); } return uuid($value); }, $ids);
if (count(array_unique($ids)) !== count($ids)) { throw new WebError(422, 'La selección contiene eventos repetidos.'); }
try {
    @set_time_limit(160);
    $result = engine('POST', '/v1/analyses', [], ['log_ids' => $ids]);
    redirect('analisis.php?id=' . rawurlencode(uuid($result['id'])));
} catch (WebError $error) {
    http_response_code($error->status);
    panel_header('No se pudo completar el análisis', 'analisis', $current);
    notice($error->getMessage());
    echo '<a class="button outline" href="' . e(url('analisis.php')) . '">Consultar historial</a> <a class="button primary" href="' . e(url('eventos.php')) . '">Volver a los eventos</a>';
    panel_footer();
}

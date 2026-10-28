<?php
require __DIR__ . '/_init.php'; $current = require_user();
$filters = []; $inputs = []; $error = ''; $page = ['items' => [], 'total' => 0]; $offset = page_offset();
try {
    foreach (['source' => 255, 'service' => 255, 'severity' => 16, 'text' => 500, 'start' => 32, 'end' => 32] as $key => $max) {
        $inputs[$key] = field($_GET, $key, $max);
        if ($inputs[$key] !== '') { $filters[$key] = $inputs[$key]; }
    }
    foreach (['start', 'end'] as $key) {
        if (!empty($filters[$key])) {
            $date = DateTimeImmutable::createFromFormat('!Y-m-d\TH:i', $filters[$key], new DateTimeZone(config()['timezone']));
            $problems = DateTimeImmutable::getLastErrors();
            if (!$date || ($problems && ($problems['warning_count'] || $problems['error_count']))) { throw new WebError(422, 'Revisa el intervalo temporal.'); }
            $filters[$key] = $date->format(DateTimeInterface::ATOM);
        }
    }
    $page = engine('GET', '/v1/logs', [...$filters, 'limit' => 25, 'offset' => $offset]);
} catch (WebError $exception) { $error = $exception->getMessage(); }
panel_header('Explorador de eventos', 'eventos', $current);
?><div class="panel-overview"><div><span class="feature-icon">≡</span><div><strong><?= $error ? '—' : number_format((int)$page['total'], 0, ',', '.') ?></strong><small>Eventos encontrados</small></div></div><div><i class="dot"></i><p><?= $error ? 'El motor necesita atención.' : 'Conectado al motor de iaLogs.' ?><br>Fechas en <?= e(config()['timezone']) ?>.</p></div></div>
<section class="card filter-card"><h2>Filtrar eventos</h2><form method="get" action="<?= e(url('eventos.php')) ?>"><div class="filter-grid"><label>Buscar en el mensaje<input name="text" maxlength="500" placeholder="Error, conexión, timeout…" value="<?= e($inputs['text'] ?? '') ?>"></label><label>Origen<input name="source" maxlength="255" placeholder="Todos los orígenes" value="<?= e($inputs['source'] ?? '') ?>"></label><label>Servicio<input name="service" maxlength="255" placeholder="Todos los servicios" value="<?= e($inputs['service'] ?? '') ?>"></label><label>Severidad<select name="severity"><option value="">Todas</option><?php foreach (['TRACE','DEBUG','INFO','WARNING','ERROR','CRITICAL'] as $value) { ?><option <?= ($inputs['severity'] ?? '') === $value ? 'selected' : '' ?>><?= e($value) ?></option><?php } ?></select></label><label>Desde<input name="start" type="datetime-local" value="<?= e($inputs['start'] ?? '') ?>"></label><label>Hasta<input name="end" type="datetime-local" value="<?= e($inputs['end'] ?? '') ?>"></label></div><div class="filter-actions"><a href="<?= e(url('eventos.php')) ?>">Limpiar filtros</a><button class="button outline small" type="submit">Aplicar filtros ↗</button></div></form></section>
<?php if ($error) { notice($error); } ?>
<section class="card events-card"><div class="card-heading"><div><h2>Flujo de eventos</h2><p>Más recientes primero · 25 por página</p></div><span class="tag">EVENTOS ORIGINALES</span></div>
<?php if ($page['items']) { ?><form method="post" action="<?= e(url('analizar.php')) ?>" data-analysis-form><?= csrf_field() ?><div class="table-scroll"><table><thead><tr><th><span class="sr-only">Seleccionar</span></th><th>FECHA / HORA</th><th>SEVERIDAD</th><th>ORIGEN / SERVICIO</th><th>MENSAJE</th><th></th></tr></thead><tbody><?php foreach ($page['items'] as $event) { ?><tr><td><input type="checkbox" name="log_ids[]" value="<?= e($event['id']) ?>" aria-label="Seleccionar evento <?= e($event['id']) ?>"></td><td class="date-cell"><?= e(date_label($event['timestamp'])) ?></td><td><?= badge($event['severity']) ?></td><td class="source-cell"><strong><?= e($event['source']) ?></strong><small><?= e($event['service'] ?? 'Sin servicio') ?></small></td><td class="message-cell"><a href="<?= e(url('evento.php?id=' . rawurlencode($event['id']))) ?>"><?= e(substr($event['message'], 0, 240)) ?></a></td><td><a class="detail-arrow" href="<?= e(url('evento.php?id=' . rawurlencode($event['id']))) ?>" aria-label="Ver detalle del evento">↗</a></td></tr><?php } ?></tbody></table></div><div class="selection-bar"><div><strong data-selection-count>Selecciona los eventos relevantes</strong><p>El diagnóstico utilizará solo tu selección.</p></div><button class="button primary" type="submit">✧ Analizar selección</button></div><p role="status" class="analysis-progress" hidden>El motor está preparando el diagnóstico. Mantén esta página abierta.</p></form><?php } else { empty_state($error ? 'No se han podido cargar los eventos' : 'Sin eventos para estos filtros', $error ? 'Comprueba la conexión del motor y vuelve a cargar.' : 'Envía logs a la API o prueba otra búsqueda.'); } ?>
<?php pager((int)$page['total'], $offset, 'eventos.php', $inputs); ?></section><?php panel_footer(); ?>

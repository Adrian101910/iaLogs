<?php
require __DIR__ . '/_init.php'; $current = require_user(); $offset = page_offset();
$total = (int)db()->query('SELECT COUNT(*) FROM enquiries')->fetchColumn();
$query = db()->prepare('SELECT * FROM enquiries ORDER BY created_at DESC, id DESC LIMIT 25 OFFSET ?');
$query->bindValue(1, $offset, PDO::PARAM_INT); $query->execute(); $items = $query->fetchAll();
panel_header('Solicitudes de información', 'solicitudes', $current);
?><section class="card"><div class="card-heading"><div><h2>Contactos desde la web</h2><p>Solicitudes guardadas. No se han enviado correos automáticamente.</p></div><span class="tag"><?= $total ?> EN TOTAL</span></div><?php if (!$items) { empty_state('Todavía no hay solicitudes', 'Las consultas del formulario público aparecerán aquí.'); } foreach ($items as $item) { ?><article class="enquiry"><div><h3><?= e($item['name']) ?></h3><span class="tag purple"><?= e(plans()[$item['plan']]['name'] ?? $item['plan']) ?></span></div><p><?= e($item['email']) ?> · <?= e($item['company']) ?> · <?= e(date_label($item['created_at'])) ?></p><pre><?= e($item['message']) ?></pre></article><?php } pager($total, $offset, 'solicitudes.php'); ?></section><?php panel_footer(); ?>

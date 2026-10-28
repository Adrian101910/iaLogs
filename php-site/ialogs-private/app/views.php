<?php
declare(strict_types=1);

function logo(): string
{
    return '<span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span><span>ia<span class="brand-light">Logs</span></span>';
}
function page_head(string $title, string $description = 'Centraliza tus logs y encuentra evidencias con inteligencia artificial local.'): void
{
    echo '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>' . e($title) . ' · iaLogs</title><meta name="description" content="' . e($description) . '"><link rel="icon" href="' . e(url('assets/favicon.svg')) . '" type="image/svg+xml"><link rel="stylesheet" href="' . e(url('assets/site.css')) . '"><script src="' . e(url('assets/site.js')) . '" defer></script></head><body>';
}
function public_header(string $title, string $active = ''): void
{
    page_head($title);
    echo '<a class="skip-link" href="#contenido">Saltar al contenido</a><header class="public-header"><div class="container header-inner"><a class="brand" href="' . e(url()) . '" aria-label="iaLogs, inicio">' . logo() . '</a><nav aria-label="Navegación principal"><a class="' . ($active === 'producto' ? 'current' : '') . '" href="' . e(url('productos.php')) . '">Producto</a><a class="' . ($active === 'planes' ? 'current' : '') . '" href="' . e(url('planes.php')) . '">Planes</a><a href="' . e(url('index.php#como-funciona')) . '">Cómo funciona</a></nav><a class="button small dark" href="' . e(url('login.php')) . '">Acceder al panel <span aria-hidden="true">↗</span></a></div></header>';
}
function public_footer(): void
{
    echo '<footer class="public-footer"><div class="container footer-grid"><div><a class="brand" href="' . e(url()) . '">' . logo() . '</a><p>Menos ruido. Más contexto.<br>Observabilidad bajo tu control.</p></div><div><strong>Explora</strong><a href="' . e(url('productos.php')) . '">Producto</a><a href="' . e(url('planes.php')) . '">Planes</a><a href="' . e(url('contacto.php')) . '">Solicitar información</a></div><div><strong>Tu espacio</strong><a href="' . e(url('login.php')) . '">Panel privado</a><a href="' . e(url('privacidad.php')) . '">Privacidad</a><span>API JSON · Archivos · Docker</span></div></div><div class="container footer-bottom"><span>© ' . date('Y') . ' iaLogs</span><span>Hecho para entender lo que ocurre.</span></div></footer></body></html>';
}
function panel_header(string $title, string $active, array $user): void
{
    page_head($title);
    echo '<a class="skip-link" href="#contenido">Saltar al contenido</a><div class="panel-shell"><aside class="panel-sidebar"><a class="brand" href="' . e(url()) . '">' . logo() . '</a><span class="eyebrow">ESPACIO PRIVADO</span><nav aria-label="Panel"><a class="' . ($active === 'eventos' ? 'current' : '') . '" href="' . e(url('eventos.php')) . '"><span>≡</span> Eventos</a><a class="' . ($active === 'analisis' ? 'current' : '') . '" href="' . e(url('analisis.php')) . '"><span>✧</span> Análisis</a><a class="' . ($active === 'solicitudes' ? 'current' : '') . '" href="' . e(url('solicitudes.php')) . '"><span>↗</span> Solicitudes</a></nav><div class="sidebar-note"><span class="tag purple">TU CONTEXTO</span><p>Selecciona los eventos relevantes y explora las evidencias.</p></div><div class="account"><strong>' . e($user['name']) . '</strong><small>' . e($user['email']) . '</small><form method="post" action="' . e(url('logout.php')) . '">' . csrf_field() . '<button class="text-button" type="submit">Cerrar sesión ↗</button></form></div></aside><div class="panel-workspace"><header class="panel-topbar"><span>iaLogs / <strong>' . e($title) . '</strong></span><a href="' . e(url()) . '">Volver a la web ↗</a></header><main id="contenido" class="panel-content"><div class="page-title"><span class="eyebrow">OBSERVA. SELECCIONA. COMPRENDE.</span><h1>' . e($title) . '</h1></div>';
}
function panel_footer(): void
{
    echo '<footer class="panel-footer">iaLogs · Espacio administrativo compartido <span>Los diagnósticos requieren revisión humana.</span></footer></main></div></div></body></html>';
}
function notice(string $message, bool $success = false): void
{
    echo '<div class="notice ' . ($success ? 'success' : 'error') . '" role="' . ($success ? 'status' : 'alert') . '">' . e($message) . '</div>';
}
function badge(string $severity): string
{
    $valid = in_array($severity, ['TRACE','DEBUG','INFO','WARNING','ERROR','CRITICAL'], true) ? strtolower($severity) : 'info';
    return '<span class="severity ' . $valid . '"><i></i>' . e($severity) . '</span>';
}
function pager(int $total, int $offset, string $page, array $filters = []): void
{
    echo '<div class="pager"><span>' . ($total ? ($offset + 1) . '–' . min($offset + 25, $total) : '0') . ' de ' . number_format($total, 0, ',', '.') . '</span><div>';
    if ($offset > 0) { echo '<a class="button outline small" href="' . e(url($page . '?' . http_build_query([...$filters, 'offset' => max(0, $offset - 25)]))) . '">← Anterior</a>'; }
    if ($offset + 25 < $total) { echo '<a class="button outline small" href="' . e(url($page . '?' . http_build_query([...$filters, 'offset' => $offset + 25]))) . '">Siguiente →</a>'; }
    echo '</div></div>';
}
function empty_state(string $title, string $message): void
{
    echo '<div class="empty-state"><span aria-hidden="true">◇</span><h2>' . e($title) . '</h2><p>' . e($message) . '</p></div>';
}
function plan_cards(): void
{
    echo '<div class="plan-grid">';
    foreach (plans() as $id => $plan) {
        echo '<article class="plan-card ' . ($id === 'equipo' ? 'featured' : '') . '">' . ($id === 'equipo' ? '<span class="plan-ribbon">PARA TU EQUIPO</span>' : '') . '<span class="eyebrow">' . e($plan['subtitle']) . '</span><h3>' . e($plan['name']) . '</h3><p>' . e($plan['description']) . '</p><div class="plan-price">' . e($plan['price']) . '</div><a class="button ' . ($id === 'equipo' ? 'primary' : 'outline') . '" href="' . e(url('contacto.php?plan=' . $id)) . '">' . e($plan['cta']) . ' ↗</a><ul class="feature-list">';
        foreach ($plan['features'] as $feature) { echo '<li>✓ <span>' . e($feature) . '</span></li>'; }
        echo '</ul></article>';
    }
    echo '</div>';
}

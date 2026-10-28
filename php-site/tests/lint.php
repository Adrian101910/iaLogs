<?php
declare(strict_types=1);
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
$files = new RecursiveIteratorIterator(new RecursiveDirectoryIterator(dirname(__DIR__)));
$count = 0;
foreach ($files as $file) {
    if ($file->getExtension() !== 'php') { continue; }
    $process = proc_open([PHP_BINARY, '-l', $file->getPathname()], [1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
    if (!is_resource($process)) { exit(1); }
    $output = stream_get_contents($pipes[1]); $error = stream_get_contents($pipes[2]);
    fclose($pipes[1]); fclose($pipes[2]);
    if (proc_close($process) !== 0) { fwrite(STDERR, 'Sintaxis no válida: ' . basename($file->getPathname()) . "\n"); exit(1); }
    $count++;
}
echo 'PHP syntax OK: ' . $count . " archivos.\n";

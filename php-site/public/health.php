<?php
require __DIR__ . '/_init.php';
db()->query('SELECT 1')->fetchColumn();
header('Content-Type: application/json; charset=utf-8');
echo json_encode(['status' => 'ok', 'database' => 'ok']);

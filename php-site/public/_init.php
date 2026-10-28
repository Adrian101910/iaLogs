<?php
declare(strict_types=1);
$privateRoot = getenv('IALOGS_PHP_PRIVATE') ?: dirname(__DIR__) . '/ialogs-private';
require $privateRoot . '/app/bootstrap.php';

<?php
require __DIR__ . '/_init.php';
post_only(); verify_csrf();
$_SESSION = [];
$cookie = session_get_cookie_params();
setcookie(session_name(), '', ['expires' => time() - 3600, 'path' => $cookie['path'], 'secure' => $cookie['secure'], 'httponly' => true, 'samesite' => 'Lax']);
session_destroy();
redirect('login.php');

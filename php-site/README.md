# Web PHP de iaLogs para hosting compartido

Portal en PHP con presentación, productos, planes de implantación, solicitudes y panel privado. No requiere React, Node, Composer ni Docker en el hosting. El panel se renderiza en PHP y consulta el motor de iaLogs desde el servidor.

La web guarda en MySQL el administrador, las solicitudes y los límites de intentos. Los eventos y diagnósticos siguen en el motor existente (FastAPI + PostgreSQL + Ollama). **El hosting compartido no ejecuta Ollama, Docker ni el backend Python.** Para utilizar el panel desde el hosting se necesita una URL HTTPS del motor accesible desde ese hosting. No basta con subir la web para trasladar el motor a PHP/MySQL.

## Probar en tu equipo

Para una instalación nueva desde GitHub utiliza el [arranque común](../README.md): `python3 scripts/quickstart.py` (Windows: `py -3.12 scripts/quickstart.py`). Conecta el portal y el motor mediante una red privada y funciona también en Linux. Los comandos siguientes son la variante por componentes para Docker Desktop.

Con Docker Desktop iniciado y el motor de iaLogs arrancado:

```powershell
py -3.12 scripts/setup_php_web.py
docker compose --env-file .local/php-web.env -f compose.php.yaml up -d --build web
```

Abre **http://127.0.0.1:8090**. El administrador local y su contraseña están en **`.local/php-admin.txt`**. La configuración está en `.local/php-web.env`. El script genera secretos aleatorios una sola vez y conserva los archivos existentes. No se imprimen claves. Si cambias la API key del motor, actualiza `IALOGS_API_KEY` en este archivo privado y recrea el servicio web.

La web pública está en `/`; el panel, en `/login.php`. El MySQL del portal tiene un volumen independiente y no publica ningún puerto. El proyecto original permanece en los puertos 8000/8080.

## Qué incluye

- Inicio, producto, planes y privacidad en español, con diseño adaptable y recursos locales.
- Planes informativos Local, Equipo e Integración. No hay pagos ni suscripciones automáticas. Los precios y condiciones deben definirse antes de comercializar.
- Formulario que guarda solicitudes en MySQL; se consultan en el panel. No envía email automáticamente.
- Acceso administrativo con contraseñas mediante `password_hash`, sesiones HttpOnly/SameSite, regeneración, caducidad, CSRF y límites de intentos en MySQL.
- Panel PHP: filtros y paginación, detalle JSON, selección de eventos, diagnóstico, enlaces a evidencias e historial.
- API key del motor solo en configuración privada del servidor. El navegador usa la sesión PHP; no recibe la API key.
- Consultas parametrizadas y renderizado de logs/respuestas como texto escapado.

Es un espacio administrativo para una instalación. No hay registro público, facturación, recuperación por email ni aislamiento de datos por cliente. No vendas cuentas de clientes con acceso a este panel como si fuera un SaaS multiempresa: ese aislamiento necesita implementación adicional.

## Requisitos del hosting

- PHP **8.4 actualizado**, con `pdo_mysql`, `curl`, `json`, `openssl` y sesiones disponibles. Probado con PHP 8.4.27.
- MySQL 8.x con InnoDB y `utf8mb4`, probado con MySQL 8.4. MariaDB no se ha verificado en esta entrega.
- HTTPS válido en el dominio y salida HTTPS desde PHP hacia el motor.
- Capacidad de guardar archivos **fuera de todos los directorios públicos**. Apache/LiteSpeed con `.htaccess`, o reglas equivalentes del proveedor.
- Para análisis síncronos, tiempo de ejecución del hosting suficiente: PHP utiliza hasta 160 s y cURL hasta 130 s. Algunos hostings cortan peticiones antes; confirma ese límite con el proveedor. Si se corta, consulta el historial antes de repetir. Esta versión no incorpora una cola asíncrona.

## Preparar el paquete

```powershell
py -3.12 scripts/package_php_web.py
```

Se genera `php-site/dist/ialogs-php-hosting.zip` con estas carpetas:

```text
public_html/           → archivos públicos de la web
ialogs-private/        → aplicación, SQL y configuración de ejemplo
INSTALACION.md
SHA256SUMS
```

El empaquetador utiliza una lista permitida, verifica hashes/ZIP y comprueba que las credenciales locales no estén incluidas. No copia `.env`, configuración `local.php`, datos, sesiones ni contraseñas. No subas el repositorio entero ni `.local` al hosting.

## Instalación sin terminal: cPanel / gestor de archivos / FTP

1. Haz una copia de la web existente del dominio antes de sustituir archivos. Crea una base MySQL y un usuario con permisos para esa base desde el panel del hosting.
2. Importa `ialogs-private/database/001_initial.sql` en esa base mediante phpMyAdmin. Crea las tablas y el registro de migración; no contiene datos del administrador ni modifica las tablas de PostgreSQL.
3. Sube el **contenido** de `public_html/` al directorio público de tu dominio. Incluye `.htaccess`; algunos clientes FTP ocultan los archivos que empiezan por punto.
4. Sube `ialogs-private/` **fuera del directorio público**. El esquema predeterminado es `/home/TU_USUARIO/public_html` y `/home/TU_USUARIO/ialogs-private`. Nunca debe poder descargarse la configuración desde la web.
5. Si el proveedor utiliza otra estructura, configura `IALOGS_PHP_PRIVATE` con la ruta absoluta privada, o adapta la ruta `$privateRoot` de `public_html/_init.php`. Para instalar en una subcarpeta, configura además `base_path`, por ejemplo `/ialogs`.
6. Copia `ialogs-private/config/example.php` como `ialogs-private/config/local.php`. Edita este último con los valores del hosting. Un ejemplo de estructura, **sin credenciales reales**, es:

```php
<?php
return [
    'environment' => 'production',
    'base_path' => '',
    'secret' => 'SUSTITUYE_POR_UN_SECRETO_ALEATORIO_DE_AL_MENOS_32_CARACTERES',
    'session_secure' => true,
    'db' => [
        'host' => 'localhost',
        'port' => 3306,
        'name' => 'BASE_CREADA_EN_EL_HOSTING',
        'user' => 'USUARIO_DE_LA_BASE',
        'password' => 'CONTRASENA_DE_LA_BASE',
    ],
    'engine_url' => 'https://API_DE_TU_MOTOR',
    'engine_key' => 'API_KEY_DEL_MOTOR',
    'engine_timeout' => 130,
    'install_token_hash' => 'SHA256_DEL_TOKEN_TEMPORAL',
];
```

7. Utiliza secretos aleatorios propios de esta instalación. Para la primera configuración puedes consultar el secreto y el hash generados en `.local/php-web.env`, y el token temporal en `.local/php-admin.txt`; copia únicamente los valores necesarios **a la configuración privada**, nunca al HTML, una URL o el formulario de contacto. Las credenciales MySQL locales de Docker no son las del hosting.
8. Fuerza HTTPS desde el panel del proveedor. Abre `https://TU_DOMINIO/instalar.php`, introduce el token temporal, tu email y una contraseña nueva de 12–72 bytes. El instalador solo funciona con hash configurado, tablas preparadas y ningún administrador existente. Una transacción bloquea instalaciones simultáneas.
9. El instalador se desactiva cuando existe el administrador. Vacía `install_token_hash` en `local.php` tras terminar y accede por `/login.php`. El administrador local de Docker no se copia al hosting.
10. Comprueba la portada, login, `/health.php`, listado de eventos, detalle, un análisis pequeño e historial. La página `health.php` comprueba MySQL; el listado prueba además el motor.

La configuración del hosting debe ser `production`, con cookies seguras y conexión HTTPS al motor. No utilices `APP_ENV=local` ni desactives validaciones TLS para resolver errores de conexión. Si las reglas `Options` de `.htaccess` están restringidas por el proveedor, pídele la configuración equivalente; no muevas la carpeta privada al directorio público.

### Con terminal o SSH

También puedes aplicar la migración y crear el primer administrador ejecutando `php ./ialogs-private/bin/setup.php` desde la carpeta de la instalación, con `APP_ADMIN_EMAIL` y `APP_ADMIN_PASSWORD` definidos en su entorno privado. El comando no imprime la contraseña y conserva un administrador existente.

## Conectar con el motor actual

En Docker Desktop local se usa `http://host.docker.internal:8000`. Ese nombre **no funciona en un hosting compartido**. Allí `engine_url` debe apuntar a un endpoint HTTPS del motor que el hosting pueda alcanzar y autorizar.

El motor puede seguir en el equipo con GPU o en otro servidor con capacidad suficiente. La conexión remota requiere su propio despliegue: dominio/certificado, acceso de red restringido cuando sea posible y API key. Ollama se mantiene en la red local del motor; **no publiques el puerto 11434**. PostgreSQL tampoco necesita un puerto público para este portal.

Esta entrega no abre puertos en tu equipo ni crea túneles, DNS o servicios públicos. No se ha realizado una instalación en un proveedor real porque todavía no hay dominio, acceso al hosting ni URL HTTPS del motor configurados. El ZIP está preparado; esas conexiones deben configurarse en tu entorno.

## Pruebas

```powershell
docker compose --env-file .local/php-web.env -f compose.php.yaml run --rm tests
docker compose --env-file .local/php-web.env -f compose.php.yaml exec -T web php tests/lint.php
py -3.12 scripts/php_web_smoke.py --with-model
```

Las pruebas PHP utilizan `mysql-test`, una base temporal aislada con migraciones reales. Solo limpian las tablas de esa base de pruebas. Comprueban hashing/autenticación, regeneración/caducidad de sesión, CSRF, límites, consultas parametrizadas, Unicode, persistencia, HTTPS de producción y errores de motor desconectado.

La prueba HTTP utiliza la web real: portada, recursos, MySQL, login/logout, CSRF, rutas privadas, formulario y escape de HTML. Crea una solicitud de prueba visible en Solicitudes. Con `--with-model`, solicita y recupera un análisis real a través de PHP → FastAPI → Ollama → PostgreSQL, y abre las evidencias. No descarga modelos. Omite esa opción si solo quieres comprobar web y acceso al motor.

Resultados de desarrollo del 28 de octubre de 2026: **16 pruebas PHP correctas y 39 peticiones HTTP correctas**, incluido el instalador web con token y bloqueo posterior, y un análisis real con `qwen2.5-coder:14b` (`b697bf52-54fa-4054-ac46-3c01a59442a3`). La inspección visual automatizada está pendiente: el host de acceso al navegador no estaba disponible. Se comprobaron por HTTP el HTML, CSS, JavaScript y las rutas.

## Datos, mantenimiento y publicación

```powershell
docker compose --env-file .local/php-web.env -f compose.php.yaml stop
```

Conserva el volumen MySQL y la configuración. `down` también conserva el volumen; `down -v` lo elimina permanentemente y **no debe usarse para una parada normal**. El motor original tiene su propia parada y su propio volumen PostgreSQL.

No hay borrado automático de solicitudes ni retención de eventos. Establece conservación y copias de seguridad antes de usar datos sensibles. Los límites de intentos se guardan como hashes HMAC; el proveedor puede mantener sus propios logs de acceso. Puedes limpiar los contadores antiguos de `rate_limits` con una tarea administrativa acorde con su ventana máxima de una hora, sin borrar usuarios ni solicitudes.

Antes de publicar, adapta la identidad y contacto del responsable en `privacidad.php`, los precios/alcances de los planes y la política de conservación. No se ha definido una oferta comercial real ni un texto legal específico para tu actividad. Los planes se editan en `ialogs-private/app/functions.php`; el contenido público, en `public/*.php`; el diseño, en `public/assets/site.css`.

No hay cuentas de cliente con aislamiento de datos, pagos, MFA ni recuperación de contraseña por correo. El primer administrador se provisiona durante la instalación; cualquier gestión adicional de administradores requiere una ampliación o una operación administrativa controlada. Los diagnósticos son recomendaciones, no ejecuciones automáticas ni garantías de exactitud.

Referencias técnicas: [sesiones PHP](https://www.php.net/manual/en/features.session.security.management.php), [password_hash](https://www.php.net/manual/en/function.password-hash.php), [PDO](https://www.php.net/manual/en/pdo.prepared-statements.php).

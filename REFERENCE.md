# iaLogs

Referencia técnica del motor y los colectores. Para una instalación nueva desde GitHub, sigue primero el [README](README.md), que incluye el arranque conjunto y la opción de Ollama en un contenedor privado.

Se ha añadido una **web pública y panel privado en PHP/MySQL para hosting compartido**, con producto, planes, solicitudes y acceso a este motor. Se prueba localmente en **http://127.0.0.1:8090**. Instalación, paquete ZIP y configuración: [guía del portal PHP](php-site/README.md). El motor FastAPI/PostgreSQL/Ollama descrito a continuación se conserva y se conecta al portal desde el servidor.

Centraliza eventos en PostgreSQL, permite explorarlos desde una interfaz en español y genera diagnósticos con un modelo local de Ollama. El recorrido implementado es **enviar → guardar → filtrar → seleccionar → analizar → consultar evidencias e historial**.

Stack: Python 3.12, FastAPI, SQLAlchemy, PostgreSQL 17, Alembic, React, TypeScript y Vite. Docker Compose ejecuta la aplicación; Ollama se ejecuta por separado en Windows. No se descarga ningún modelo al arrancar los contenedores.

## Arranque en Windows 11

Necesitas Docker Desktop iniciado, con contenedores Linux y backend WSL 2. Comprueba `docker version` y `docker compose version`. No necesitas instalar Python ni Node en Windows para usar los contenedores.

Desde la raíz del repositorio, en PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
docker compose up -d --build
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health
docker compose --profile tools run --rm sender
```

El script crea `.env` con una API key y una contraseña de PostgreSQL aleatorias, y prepara `.local/logs/app.log`. Si `.env` ya existe, conserva sus valores. `-ExecutionPolicy Bypass` se aplica solo al proceso de ese comando y no cambia la política persistente del equipo. Si prefieres usar Python instalado localmente, el equivalente es `py -3.12 scripts/setup_env.py`.

Abre **http://127.0.0.1:8080**, consulta `API_KEY` en tu archivo `.env` e introdúcela en la pantalla de conexión. La interfaz la conserva únicamente en memoria: recargar o cerrar la página elimina la sesión. No se incluye en variables `VITE_*`, almacenamiento del navegador, URL ni imagen del frontend. No compartas `.env`.

Selecciona algunos eventos del origen `demo-windows` y pulsa analizar cuando Ollama esté listo. La tabla permite buscar, filtrar y paginar; el detalle muestra el mensaje y sus atributos JSON. El resultado incluye referencias que abren los eventos citados, y el historial permite recuperar análisis guardados.

Servicios locales:

| Servicio | Dirección |
| --- | --- |
| Interfaz y proxy de API | http://127.0.0.1:8080 |
| API y documentación OpenAPI | http://127.0.0.1:8000/docs |
| Salud de PostgreSQL | http://127.0.0.1:8000/health |
| PostgreSQL | Solo red interna de Compose; sin puerto publicado |

## Arranque desde WSL

Activa la integración de Docker Desktop con tu distribución WSL y ejecuta desde la raíz del repositorio:

```bash
python3 scripts/setup_env.py
docker compose up -d --build
docker compose --profile tools run --rm sender
```

La interfaz sigue estando en `http://127.0.0.1:8080`. `setup_env.py` solo utiliza la biblioteca estándar de Python; genera los secretos locales y no sobrescribe un `.env` existente.

## Preparar Ollama en Windows

Instala e inicia [Ollama para Windows](https://docs.ollama.com/windows). Descarga manualmente el modelo elegido; ocupa varios GB:

Si la aplicación Ollama no está iniciada, ejecuta `ollama serve` en una terminal independiente y mantenla abierta. No inicies una segunda instancia si el puerto ya está ocupado.

```powershell
ollama pull qwen2.5-coder:14b
ollama list
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

La configuración de `.env` conecta el backend de Docker Desktop con Ollama en Windows:

```dotenv
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5-coder:14b
```

Mantén Ollama accesible solo desde el equipo local. No publiques el puerto 11434 en Internet, no configures redirecciones en el router ni añadas reglas de firewall que lo expongan a redes no confiables. Si Windows responde pero Docker no conecta, comprueba la resolución de `host.docker.internal`, la conectividad de Docker Desktop y las reglas locales del firewall antes de cambiar la escucha del servicio. [Docker documenta este acceso al host desde contenedores](https://docs.docker.com/desktop/features/networking/).

Para cambiar variables de `.env`, recrea el backend: `docker compose up -d --force-recreate backend`. La ingesta y las consultas funcionan con Ollama apagado. Un análisis devuelve un error claro si el servicio o modelo no están disponibles, si excede el tiempo o si genera una respuesta inválida.

Opcionalmente, después de instalar el modelo:

```powershell
docker compose --profile tools run --rm sender python /scripts/send_demo.py --analyze
```

Ese comando añade cinco eventos sintéticos y solicita un diagnóstico al **modelo real**. Las respuestas simuladas de las pruebas no sustituyen esta comprobación.

Para comprobar el despliegue y probar el modelo usando hasta dos eventos ya existentes, sin volver a ingerir datos:

```powershell
docker compose --profile tools run --rm sender python /scripts/verify_local.py
```

Comprueba PostgreSQL, la página y sus recursos JS/CSS, el proxy y la autenticación. Solo llama al modelo si Ollama responde y el modelo configurado ya está instalado. Puede guardar un nuevo análisis real; no descarga modelos.

## API JSON

Todos los endpoints de datos requieren la cabecera `X-API-Key`; `/health` no la requiere. Los IDs son UUID generados por el servidor. Cada evento incluye fecha original con zona horaria, recepción del servidor, origen, servicio opcional, severidad normalizada, mensaje y atributos JSONB.

Las fechas se normalizan a UTC en las respuestas y se muestran en la hora local del navegador. Se conserva el instante del evento; no se conserva su desplazamiento horario original por separado.

Ejemplo de cuerpo para `POST /v1/logs`:

```json
{
  "events": [
    {
      "timestamp": "2026-10-28T10:00:00+01:00",
      "source": "equipo-01",
      "service": "orders-api",
      "severity": "ERROR",
      "message": "Timeout al obtener una conexión",
      "attributes": {"request_id": "example-001", "attempt": 2}
    }
  ]
}
```

Ejemplo completo de envío en PowerShell, sin escribir la clave en el historial de comandos:

```powershell
$apiKey = ((Get-Content .env | Where-Object { $_ -like 'API_KEY=*' }) -split '=', 2)[1]
$headers = @{ 'X-API-Key' = $apiKey }
$batch = @{ events = @(@{
  timestamp = (Get-Date).ToUniversalTime().ToString('o')
  source = 'equipo-01'
  service = 'orders-api'
  severity = 'ERROR'
  message = 'Timeout al obtener una conexión'
  attributes = @{ request_id = 'example-001' }
}) } | ConvertTo-Json -Depth 10
$created = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/logs -Headers $headers -ContentType 'application/json' -Body ([Text.Encoding]::UTF8.GetBytes($batch))
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/v1/logs?source=equipo-01&severity=ERROR&limit=20&offset=0' -Headers $headers
```

| Operación | Endpoint |
| --- | --- |
| Comprobar PostgreSQL | `GET /health` |
| Insertar lote completo | `POST /v1/logs` con `{"events": [...]}` |
| Consultar eventos | `GET /v1/logs` |
| Ver evento/evidencia | `GET /v1/logs/{id}` |
| Generar y guardar diagnóstico | `POST /v1/analyses` con `{"log_ids": ["UUID"]}` |
| Consultar historial | `GET /v1/analyses` |
| Recuperar análisis | `GET /v1/analyses/{id}` |

Filtros de eventos: `source`, `service`, `severity`, `start`, `end`, `text`, `limit` y `offset`. Las fechas `start` y `end` requieren zona horaria y son inclusivas. El texto busca una subcadena sin distinguir mayúsculas; `%` y `_` se tratan como caracteres literales. Origen y servicio tienen coincidencia exacta. Las severidades son `TRACE`, `DEBUG`, `INFO`, `WARNING`, `ERROR` y `CRITICAL`; se normalizan alias como `warn`, `err` y `fatal`.

Las consultas ordenan por fecha descendente e ID descendente, con límite máximo de 100 y offset máximo de 1.000.000. El historial ordena por fecha de creación e ID. Es paginación por offset: nuevas inserciones pueden desplazar páginas mientras exploras. Las respuestas de consulta tienen `items`, `total`, `limit` y `offset`.

Los lotes se validan completos antes de insertar; un evento inválido rechaza todo el lote. Las consultas usan parámetros de SQLAlchemy e índices por fecha/ID, origen, servicio y severidad. La búsqueda por subcadena no tiene un índice de texto especializado en esta versión.

Errores principales: `401` clave inválida, `404` recurso/evento inexistente, `413` petición o contexto excesivo, `415` cuerpo comprimido no admitido, `422` datos o límites inválidos, `429` IA ocupada, `502` salida del modelo inválida, `503` PostgreSQL/Ollama no disponible y `504` timeout de Ollama. No se devuelven credenciales, parámetros SQL ni respuestas internas del proveedor en los errores.

## Diagnósticos y límites

El backend solicita [salida estructurada de Ollama](https://docs.ollama.com/capabilities/structured-outputs) y valida el JSON antes de guardarlo. El diagnóstico contiene resumen, hallazgos, causas posibles, evidencias con IDs, próximas comprobaciones, información ausente e incertidumbre cualitativa `low`, `medium` o `high`. Se comprueba que todas las referencias pertenecen a los eventos seleccionados. También se guardan los IDs utilizados, modelo, fecha y versión del prompt; no se almacenan cadenas internas de razonamiento.

Los logs se tratan como datos no confiables. El prompt separa los datos de las instrucciones; el backend no habilita herramientas ni ejecución de comandos y rechaza llamadas a herramientas en la respuesta. Las recomendaciones son texto y requieren revisión humana. Los mensajes y respuestas se renderizan como texto, sin ejecutar HTML. Aun así, un modelo puede equivocarse o seguir instrucciones maliciosas contenidas en datos: los controles de estructura y referencias no prueban la veracidad del diagnóstico.

Valores iniciales configurables en `.env`:

| Variable | Valor inicial | Alcance |
| --- | --- | --- |
| `MAX_REQUEST_BYTES` | 2097152 | 2 MiB por petición, incluso sin Content-Length |
| `MAX_BATCH_EVENTS` | 500 | Eventos por lote |
| `MAX_MESSAGE_CHARS` | 16384 | Caracteres por mensaje |
| `MAX_ANALYSIS_EVENTS` | 50 | Eventos por análisis |
| `MAX_ANALYSIS_INPUT_BYTES` | 10000 | JSON de eventos enviado al modelo |
| `OLLAMA_TIMEOUT_SECONDS` | 120 | Tiempo total máximo de una solicitud |
| `OLLAMA_MAX_CONCURRENCY` | 1 | Análisis simultáneos por proceso |
| `OLLAMA_CONTEXT_TOKENS` | 16384 | Ventana solicitada al modelo |
| `OLLAMA_OUTPUT_TOKENS` | 2048 | Máximo de tokens de salida |
| `MAX_MODEL_RESPONSE_BYTES` | 65536 | Respuesta HTTP máxima del modelo |

Los atributos de cada evento admiten hasta 65536 bytes y 20 niveles JSON. El límite de entrada de IA incluye IDs, fechas y atributos: puede alcanzarse antes de seleccionar 50 eventos. No se truncan silenciosamente los eventos; reduce la selección si recibes `413`. La configuración exige margen para entrada, instrucciones y salida dentro del contexto; no utiliza el tokenizador real del modelo.

El contenedor arranca un único worker Uvicorn: el semáforo de concurrencia pertenece al proceso. No aumentes los workers suponiendo que el límite de IA sigue siendo global. Las solicitudes de análisis son síncronas respecto del cliente; esta versión no incorpora una cola persistente de trabajos.

## Colector de archivos de texto

Se incluye un colector Python mínimo y una configuración en [`collector/example.toml`](collector/example.toml). En Compose lee `.local/logs/app.log` montado como `/logs/app.log`, y guarda el checkpoint en el volumen `collector_state`.

```powershell
docker compose --profile collector up -d collector
Add-Content -LiteralPath .local/logs/app.log -Value 'Nueva línea de prueba' -Encoding UTF8
docker compose logs --tail 20 collector
```

En la interfaz, filtra por origen `text-file-demo`. Para drenar las líneas completas disponibles y salir:

```powershell
docker compose --profile collector run --rm collector python /collector/tail.py --config /collector/example.toml --once
```

Usa solo una instancia del colector por checkpoint; no ejecutes el drenaje puntual mientras el servicio continuo utiliza el mismo archivo de estado. Para detenerlo: `docker compose --profile collector stop collector`.

El archivo debe ser UTF-8 y cada línea terminada en salto de línea se convierte en un evento. Las líneas incompletas esperan su terminador. La fecha del evento es la de **lectura**, no una fecha extraída del texto; la severidad y el servicio proceden del TOML. Los atributos indican archivo, offset y `timestamp_kind=collection_time`.

El checkpoint avanza después de confirmar la ingesta y se escribe mediante reemplazo atómico. La entrega es al menos una vez: una caída después del POST y antes del checkpoint puede duplicar eventos. Detecta cambios de identidad del archivo y truncados; una rotación puede perder líneas pendientes del archivo anterior. No implementa seguimiento de múltiples archivos rotados, parsing multilinea, reconocimiento de formatos, deduplicación ni garantías de agente de producción. UTF-8 inválido, líneas demasiado largas o rechazos `4xx` detienen el colector sin avanzar el checkpoint. Los fallos temporales de conexión/servidor reintentan con espera creciente.

## Logs reales de contenedores Docker

El adaptador [`scripts/collect_docker.py`](scripts/collect_docker.py) utiliza la CLI de Docker del host y Python 3.12, sin dependencias Python adicionales. Recoge stdout/stderr del contenedor indicado y envía lotes a la API. No monta el socket de Docker dentro de la aplicación. Utiliza el contexto activo de tu CLI; para este entorno debe ser Docker Desktop.

Desde la raíz del repositorio, en PowerShell, puedes hacer una primera lectura y repetirla para comprobar el checkpoint:

```powershell
py -3.12 scripts/collect_docker.py --service backend --since 24h --once
py -3.12 scripts/collect_docker.py --service backend --since 24h --once
py -3.12 scripts/collect_docker.py --service frontend --since 24h --once
```

En ausencia de nuevos mensajes, la segunda lectura confirma **0 eventos nuevos**. Para dejar la recogida activa en una terminal:

```powershell
py -3.12 scripts/collect_docker.py --service backend
```

Detén el proceso con Ctrl+C. Para otra aplicación del equipo, sustituye `--service backend` por `--container NOMBRE_DEL_CONTENEDOR`. `--service` selecciona un contenedor del proyecto Compose actual; para servicios con varias réplicas, elige cada contenedor explícitamente. En WSL, el comando equivalente comienza por `python3` (versión 3.12 o posterior).

La API key se lee de `API_KEY` en el entorno o del `.env` del repositorio. Se puede indicar otro archivo con `--env-file`; la clave no se pasa como argumento ni se imprime. La URL por defecto es `http://127.0.0.1:8000`; se cambia mediante `--api-url`.

En la interfaz, filtra por origen `docker/ialogs-backend-1` o `docker/ialogs-frontend-1`. Selecciona unos pocos eventos y pulsa **Analizar selección**. También puedes verificar el recorrido real por consola:

```powershell
docker compose --profile tools run --rm sender python /scripts/verify_local.py --source docker/ialogs-backend-1
```

Los eventos conservan el timestamp RFC3339Nano de Docker en `attributes.docker_timestamp`; la fecha de evento se normaliza a UTC. Incluyen ID y nombre del contenedor, servicio y proyecto Compose. La CLI combina stdout/stderr, por lo que no se atribuye falsamente un stream original a cada mensaje. La severidad se infiere de `level`/`severity` en JSON o de un prefijo conocido; si no existe, se asigna INFO y `severity_method=default`.

Los checkpoints están en `.local/docker-checkpoints`, uno por ID de contenedor y ligados a la URL de la API. Avanzan después de confirmar cada lote, mantienen una ventana temporal solapada y cuentan líneas idénticas. Al recrear un contenedor se detecta su nuevo ID y comienza otro checkpoint. Utiliza solo un proceso por contenedor/checkpoint. La entrega es al menos una vez: una caída tras confirmar la API y antes de guardar el checkpoint puede duplicar el último lote.

El historial inicial es de 15 minutos y `--since` solo se aplica cuando todavía no hay checkpoint. La lectura admite hasta 1000 líneas por consulta (`--max-lines`, máximo 5000), mensajes UTF-8 de hasta 16384 bytes, lotes de hasta 100 y hasta 2 MiB por lectura/petición. Si hay más datos, se detiene esa lectura con un error y conserva el checkpoint; no descarta silenciosamente las líneas excedentes. Los límites configurados en la API también se aplican. En seguimiento, los errores se reintentan; revisa los mensajes que requieren ajustar límites o configuración.

Solo puede leer el historial que el driver exponga a [`docker logs`](https://docs.docker.com/reference/cli/docker/container/logs/). Las rotaciones o la eliminación del contenedor pueden hacer que datos aún no recogidos dejen de estar disponibles. No sigue archivos internos del contenedor ni agrupa stack traces multilinea. No anonimiza ni redacta mensajes. El Docker CLI debe tener acceso al daemon y al contexto elegidos.

## Pruebas y verificación

Construye primero las imágenes y ejecuta:

```powershell
docker compose build
docker compose --profile test run --rm tests
docker compose --profile test run --rm tests python /scripts/http_smoke.py
```

Las pruebas usan un PostgreSQL real independiente (`test-db`), sin puerto publicado y con almacenamiento temporal. Las integraciones crean esquemas aislados, ejecutan Alembic desde cero y eliminan únicamente esos esquemas de prueba. No utilizan SQLite ni borran las tablas de desarrollo. Cubren autenticación, validación atómica, persistencia JSONB, filtros, paginación, límites y respuestas simuladas de Ollama, incluidos desconexión, timeout, salida inválida y referencias ajenas. El recorrido HTTP arranca una API real y un servidor Ollama simulado y atraviesa ingesta, consulta, análisis e historial. El colector también dispone de pruebas con archivos y una API HTTP de prueba.

`docker compose build frontend` ejecuta `npm ci` y `npm run build` dentro de la imagen, incluyendo la comprobación TypeScript. Para verificar el modelo real se utiliza el comando `sender ... --analyze` del apartado Ollama; su resultado debe registrarse por separado.

Verificación ejecutada el **28 de octubre de 2026**, con Docker Desktop y PostgreSQL real:

- **110 pruebas correctas**, sin pruebas omitidas, incluyendo el nuevo adaptador Docker. Queda un aviso de deprecación de `BlockingPortal` en una dependencia de TestClient; no impide la ejecución.
- Migraciones desde esquemas vacíos y reaplicación de `alembic upgrade head` correctas.
- Recorrido por HTTP real con Uvicorn, PostgreSQL y Ollama simulado correcto: ingesta, filtros, análisis, evidencias e historial.
- Colector correcto por HTTP: lotes, checkpoint, reinicio sin duplicados y líneas añadidas; también probado en el volumen real de Compose con el usuario sin privilegios.
- Compilación TypeScript/Vite correcta mediante `npm ci` y `npm run build`.
- Despliegue HTTP correcto: página React, recursos JS/CSS, proxy y rechazo de peticiones sin API key. Nueve eventos sintéticos guardados.
- **Prueba real de `qwen2.5-coder:14b` correcta**, conectado desde Docker a Ollama de Windows: diagnóstico validado y guardado con ID `b27d1a7e-0acf-4f52-98d6-01434b5dff73`.
- Ingesta real de Docker probada con los contenedores de iaLogs: 4 registros iniciales del backend y 66 del frontend; repetir la lectura del backend confirmó 0 eventos nuevos.
- Persistencia comprobada reiniciando PostgreSQL y la API: se conservaron los IDs de los **79 eventos y 4 análisis** existentes antes del reinicio. La recogida posterior añadió los nuevos mensajes de parada/arranque.
- Diagnóstico real de los registros Docker del backend confirmado y recuperado desde PostgreSQL: análisis `aa45cff0-bc2d-4311-80a9-35c72c12196f`, generado por `qwen2.5-coder:14b`.

La inspección visual automatizada de la interfaz queda pendiente porque el host de acceso al navegador no estaba disponible. Los recursos y el proxy se comprobaron por HTTP. La prueba pequeña del modelo demuestra conectividad y validación de una respuesta; no demuestra exactitud de diagnósticos futuros ni resistencia completa a instrucciones maliciosas en logs.

## Migraciones y dependencias

`migrate` aplica `alembic upgrade head` antes de iniciar el backend; la aplicación no depende de `create_all`. Para repetir la migración o consultar su estado:

```powershell
docker compose run --rm migrate
docker compose run --rm migrate alembic current
```

Después de modificar modelos durante el desarrollo:

```powershell
docker compose run --rm -v "${PWD}/backend/migrations:/app/migrations" migrate alembic revision --autogenerate -m "describe el cambio"
docker compose build backend
docker compose run --rm migrate
docker compose up -d backend
```

Revisa siempre la migración generada antes de aplicarla y respalda los datos antes de cambios destructivos. No ejecutes downgrades sobre datos que quieras conservar sin revisar sus operaciones.

Se versionan `backend/requirements.lock` con hashes y `frontend/package-lock.json`; las imágenes instalan mediante `pip --require-hashes` y `npm ci`. Los archivos `.in` definen las dependencias Python directas y las pruebas. Solo para actualizar dependencias de forma deliberada:

```powershell
docker compose -f compose.tools.yaml run --rm lock-backend
docker compose -f compose.tools.yaml run --rm lock-frontend
docker compose build
docker compose --profile test run --rm tests
```

La actualización de locks puede requerir descargar paquetes. No se desactiva TLS ni la comprobación de hashes para instalar.

## Parada, datos y límites de esta versión

Estos comandos **conservan los volúmenes y datos**:

```powershell
docker compose stop
docker compose down
```

El segundo elimina contenedores y red, pero conserva `postgres_data` y `collector_state`. Para reanudar: `docker compose up -d`. El PostgreSQL de pruebas usa un tmpfs separado y no sirve como almacenamiento persistente.

**Solo si quieres eliminar permanentemente todos los datos de desarrollo y checkpoints**, el comando es `docker compose --profile collector --profile test down -v`. No se ejecuta como parte del arranque, las pruebas ni la parada habitual. Cambiar la contraseña de `.env` no cambia automáticamente la contraseña de un PostgreSQL ya inicializado en el volumen.

No hay retención ni purgado automáticos, cuotas de disco ni copias de seguridad programadas: los eventos y análisis crecen hasta que gestiones su almacenamiento. No borres registros utilizados por análisis si quieres conservar las evidencias consultables. Para una copia lógica manual, utiliza las herramientas de PostgreSQL y verifica después su restauración; el volumen por sí solo no es una copia de seguridad.

No hay anonimización, redacción de secretos ni cifrado adicional de datos almacenados. Mensajes y atributos se guardan completos y los seleccionados se envían a Ollama según `OLLAMA_BASE_URL`. Revisa los datos antes de ingerirlos y no apuntes esa variable a un tercero si necesitas mantenerlos locales. `.env`, volumen PostgreSQL, checkpoints y copias contienen información sensible; limita el acceso a tu usuario de Windows.

Esta versión es para uso local y una API key compartida. No ofrece usuarios, RBAC, aislamiento por equipo/tenant, auditoría de acceso ni TLS en el proxy. Compose publica interfaz y API solo en `127.0.0.1`. La exposición remota necesita diseñar autenticación por usuario, autorización, TLS, límites, auditoría y reglas de red antes de cambiar esa configuración.

## Entradas futuras

La API JSON, el colector de texto y el adaptador Docker CLI son los mecanismos de entrada implementados y probados. Los siguientes adaptadores requieren desarrollo y pruebas adicionales:

- **Windows Event Log:** suscripción o lectura incremental con bookmarks, transformación del XML/JSON a eventos, normalización de severidad y checkpoint por canal.
- **Syslog:** receptor dedicado con transporte y límites definidos, parser RFC3164/RFC5424, zona horaria explícita y reintentos para enviar lotes a la API.

Los adaptadores de Windows Event Log y syslog todavía no se han implementado ni probado. Una integración Docker como servicio con seguimiento de rotaciones y mayor capacidad requiere trabajo adicional al colector CLI incluido.

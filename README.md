# iaLogs

[![CI](https://github.com/Adrian101910/iaLogs/actions/workflows/ci.yml/badge.svg)](https://github.com/Adrian101910/iaLogs/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Logs centralizados y diagnósticos con IA local. Código abierto y autohospedado.**

[English](README.en.md) · [Guía técnica](REFERENCE.md) · [Hosting PHP](php-site/README.md) · [Contribuir](CONTRIBUTING.md)

Envía eventos, explóralos, selecciona el contexto y obtén un diagnóstico con enlaces a sus evidencias. Incluye API, explorador React y una web/panel administrativo en PHP.

## Descargar y arrancar

Necesitas **Git, Python 3.12 o posterior, Docker iniciado y Compose 2.30 o posterior**. En Windows/macOS puedes usar Docker Desktop; en Linux, Docker Engine con el plugin Compose. La GPU es opcional. Los requisitos de memoria y la velocidad de inferencia dependen del modelo que elijas.

**Windows (PowerShell):**

```powershell
git clone https://github.com/Adrian101910/iaLogs.git
cd iaLogs
py -3.12 scripts/quickstart.py
```

**Linux / macOS:**

```bash
git clone https://github.com/Adrian101910/iaLogs.git
cd iaLogs
python3 scripts/quickstart.py
```

El instalador genera secretos nuevos, aplica las migraciones, arranca los servicios y añade cinco eventos sintéticos. Conserva la configuración existente. La primera ejecución descarga imágenes de Docker que pueden ocupar varios GB. **No descarga modelos automáticamente.**

| Componente | Dirección | Acceso |
| --- | --- | --- |
| Web y panel PHP | http://127.0.0.1:8090 | Cuenta y contraseña generadas en `.local/php-admin.txt` |
| Explorador React | http://127.0.0.1:8080 | `API_KEY` generada en `.env` |
| API / documentación | http://127.0.0.1:8000/docs | Cabecera `X-API-Key` |
| Salud de PostgreSQL | http://127.0.0.1:8000/health | Sin clave |

Cada instalación tiene sus propias claves y contraseña. No hay una contraseña pública común. No subas `.env`, `.local`, bases de datos o logs privados a GitHub.

## Activar el modelo

El arranque común incluye Ollama en una red privada de Docker, sin puerto publicado. Para descargar manualmente el modelo pequeño predeterminado de una instalación nueva:

```bash
docker compose -f compose.yaml -f compose.ai.yaml exec ollama ollama pull qwen2.5-coder:1.5b
```

Después abre el panel, selecciona unos pocos eventos y pulsa **Analizar selección**. La descarga ocupa espacio en disco y puede tardar. Las consultas e ingesta funcionan aunque todavía no haya modelo.

El modelo pequeño es un punto de partida; revisa sus conclusiones. Si tienes recursos suficientes, en una instalación nueva puedes elegir uno mayor:

```bash
python3 scripts/quickstart.py --model qwen2.5-coder:14b --gpu
```

En Windows sustituye `python3` por `py -3.12`. `--gpu` requiere soporte NVIDIA configurado en Docker. Sin esa opción se usa CPU. Para aprovechar Ollama ya instalado en el host:

```bash
python3 scripts/quickstart.py --ollama host
```

Docker Desktop permite conectar mediante `host.docker.internal`. En Linux utiliza preferentemente el Ollama del contenedor; una dirección de host puede necesitar configuración específica. Un `.env` existente mantiene su modelo: edita `OLLAMA_MODEL` de forma deliberada y recrea los servicios para cambiarlo.

## Qué funciona

- **API FastAPI:** lotes atómicos, API key, límites, filtros, paginación y detalle.
- **PostgreSQL:** eventos JSONB y diagnósticos persistidos, índices y migraciones Alembic.
- **IA:** Ollama, contexto acotado, tiempo/concurrencia limitados, estructura validada y comprobación de IDs citados.
- **Explorador React:** selección, detalle JSON, diagnósticos e historial; clave solo en memoria.
- **Portal PHP/MySQL:** presentación, opciones de implantación, solicitudes y acceso administrativo al motor. Las solicitudes se guardan; no se envían correos ni se cobran pagos.
- **Entradas:** JSON, archivos de texto UTF-8 y logs de contenedores mediante Docker CLI.
- **Distribución:** licencia MIT, dependencias bloqueadas, imágenes de PHP/MySQL/Ollama fijadas y GitHub Actions.

La web PHP se comunica con el backend por una red privada en el arranque común. El motor sigue en Python/PostgreSQL y Ollama; MySQL se utiliza para el portal. Un hosting compartido PHP no puede ejecutar el motor ni el modelo. Consulta la [instalación en hosting](php-site/README.md).

## Recibir logs de Docker

Desde la raíz del repositorio:

```bash
python3 scripts/collect_docker.py --container NOMBRE_DEL_CONTENEDOR --once
python3 scripts/collect_docker.py --container NOMBRE_DEL_CONTENEDOR
```

La segunda variante mantiene la recogida activa hasta Ctrl+C. Guarda checkpoints en `.local/docker-checkpoints`. La entrega es al menos una vez; una caída entre el POST y el checkpoint puede duplicar el último lote. Para otros formatos y límites, consulta la [referencia](REFERENCE.md).

## Pruebas

No hace falta GPU ni descargar un modelo para ejecutar la suite:

```bash
docker compose --profile test run --rm --build tests
docker compose --profile test run --rm tests python /scripts/http_smoke.py
docker compose build frontend
docker compose --env-file .local/php-web.env -f compose.php.yaml run --rm --build tests
python3 scripts/check_public.py
```

Para comprobar el arranque desde una copia limpia, con secretos y volúmenes nuevos:

```bash
python3 scripts/smoke_install.py
```

GitHub Actions ejecuta las suites con PostgreSQL y MySQL reales, compila el frontend, genera el ZIP del hosting y comprueba una instalación limpia. La IA se simula en CI; eso no demuestra la calidad ni disponibilidad de un modelo real.

## Paquete para hosting

```bash
python3 scripts/package_php_web.py
```

Genera `php-site/dist/ialogs-php-hosting.zip`, con licencia, instrucciones y hashes, sin configuración ni credenciales privadas. También se genera como artefacto de GitHub Actions. GitHub Pages no ejecuta este PHP ni el motor: el repositorio contiene una aplicación que se instala en tu infraestructura.

## Parar conservando datos

Con el arranque predeterminado:

```bash
docker compose --env-file .local/php-web.env -f compose.php.yaml -f compose.php.local.yaml stop
docker compose -f compose.yaml -f compose.ai.yaml stop
```

La configuración y los volúmenes se conservan. `down -v` elimina permanentemente los volúmenes: no es un comando de parada normal. El instalador muestra los comandos correspondientes si eliges otro nombre de proyecto.

## Alcance y seguridad

Primera versión funcional para un espacio administrativo de autohospedaje. No es un SaaS multiempresa: no ofrece aislamiento entre clientes, pagos, MFA, anonimización automática, retención ni copias programadas. Windows Event Log y syslog necesitan adaptadores adicionales.

Los logs son datos no confiables. El modelo no tiene herramientas ni ejecuta comandos; sus hipótesis requieren comprobación humana. No publiques Ollama en Internet. La exposición remota necesita HTTPS, autenticación y una configuración de red revisada. Más información en [SECURITY.md](SECURITY.md).

## Licencia y contribuciones

Código bajo [MIT](LICENSE): puedes usarlo, modificarlo y redistribuirlo conservando la licencia. Los modelos y dependencias mantienen sus propias licencias. Reporta errores sin credenciales ni datos sensibles mediante los [issues](https://github.com/Adrian101910/iaLogs/issues), o consulta [CONTRIBUTING.md](CONTRIBUTING.md).

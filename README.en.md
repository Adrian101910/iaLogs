# iaLogs

Open source, self-hosted log exploration and local AI diagnosis. **[Español](README.md)** · [MIT license](LICENSE).

iaLogs includes a FastAPI/PostgreSQL engine, a React explorer, and an optional PHP/MySQL website with an administrative panel. Logs can arrive through JSON, text files, or the Docker CLI collector. Diagnosis is structured, saved, and linked to the selected evidence.

## Quick start

Requirements: Git, Python 3.12+, Docker Engine/Desktop and Docker Compose 2.30+. No GPU is required to browse logs or run the test suite. Inference requirements depend on the chosen model.

```bash
git clone https://github.com/Adrian101910/iaLogs.git
cd iaLogs
python3 scripts/quickstart.py
```

On Windows use `py -3.12 scripts/quickstart.py`. This generates your own secrets, starts the services, applies migrations, and adds synthetic sample events. It does **not** download any model.

- PHP website and panel: http://127.0.0.1:8090 — credentials in `.local/php-admin.txt`.
- React explorer: http://127.0.0.1:8080 — enter the generated `API_KEY` from `.env`.
- API health: http://127.0.0.1:8000/health.

When ready to download the default small model explicitly:

```bash
docker compose -f compose.yaml -f compose.ai.yaml exec ollama ollama pull qwen2.5-coder:1.5b
```

Select a few events and request an analysis. The default small model is a starting point, not a guarantee of diagnostic quality. For larger models, choose one with `--model` on a fresh installation and make sure you have enough memory. Use `--gpu` for a Docker-enabled NVIDIA GPU, or `--ollama host` for an existing Ollama installation. Existing secrets and model settings are preserved.

The PHP portal connects privately to the engine in the local Docker setup. For shared hosting, follow [the PHP deployment guide](php-site/README.md): the engine needs a separate reachable HTTPS endpoint; shared hosting cannot run the local AI model.

## Checks

```bash
docker compose --profile test run --rm --build tests
docker compose --profile test run --rm tests python /scripts/http_smoke.py
docker compose --env-file .local/php-web.env -f compose.php.yaml run --rm --build tests
python3 scripts/check_public.py
```

GitHub Actions checks PostgreSQL, MySQL, frontend builds, the hosting package, and a clean installation. CI simulates Ollama; it does not download a model or claim to verify real inference.

This is a local administrative workspace, not a multi-tenant commercial service. There is no automatic redaction or retention. All recommendations are text for human review. Model weights and third-party dependencies keep their own licenses. See [security](SECURITY.md), [contributing](CONTRIBUTING.md), and the [full technical reference](REFERENCE.md).

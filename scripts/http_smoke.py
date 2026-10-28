"""Recorrido HTTP real con PostgreSQL y Ollama simulado; no descarga modelos.

Ejecutar desde backend o con el servicio Compose ``tests``. Se crea y elimina
solamente un esquema nuevo en TEST_DATABASE_URL, sin tocar datos existentes.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

import httpx
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def available_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class SimulatedOllama(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length < 1_048_576:
            self.send_error(413)
            return
        try:
            payload = json.loads(self.rfile.read(length))
            check("tools" not in payload, "La petición al modelo no debe incluir herramientas")
            check(payload["stream"] is False, "Se espera una respuesta JSON completa")
            check(isinstance(payload["format"], dict), "Falta el esquema JSON de diagnóstico")
            data = payload["messages"][-1]["content"].partition("\n")[2]
            events = json.loads(data)
            ids = [row["id"] for row in events]
            check(bool(ids), "No se enviaron eventos al modelo simulado")
            diagnosis = {
                "summary": "Prueba HTTP: se observó un error de conexión, sin causa confirmada.",
                "findings": [{"description": "El evento registra un timeout.", "log_ids": [ids[0]]}],
                "possible_causes": [{"description": "Podría existir una interrupción de red.", "log_ids": [ids[0]]}],
                "evidence": [{"log_id": ids[0], "explanation": "El mensaje contiene el error de conexión."}],
                "next_checks": ["Comprobar conectividad al servicio remoto."],
                "missing_information": ["No hay registros del servicio remoto."],
                "uncertainty": "high",
            }
            self.server.model_calls += 1
            body = json.dumps({"done": True, "message": {"role": "assistant", "content": json.dumps(diagnosis)}}).encode()
        except (ValueError, KeyError, AssertionError, TypeError):
            self.send_error(400, "Petición de análisis inesperada")
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def load_collector():
    local = Path(__file__).resolve().parents[1] / "collector" / "tail.py"
    path = local if local.exists() else Path("/collector/tail.py")
    spec = importlib.util.spec_from_file_location("ialogs_smoke_collector", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("No se encontró collector/tail.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.collect


def exercise_http(base_url, key, temporary):
    headers = {"X-API-Key": key}
    with httpx.Client(base_url=base_url, timeout=10, trust_env=False) as client:
        check(client.get("/health").status_code == 200, "Falló health/PostgreSQL")
        check(client.get("/v1/logs").status_code == 401, "La consulta sin API key debe rechazarse")
        response = client.post("/v1/logs", headers=headers, json={"events": [{
            "timestamp": "2026-10-28T10:00:00+02:00", "source": "http-smoke-host",
            "service": "example-api", "severity": "err", "message": "Connection timeout; synthetic smoke event",
            "attributes": {"synthetic": True, "nested": {"attempt": 1}},
        }]})
        check(response.status_code == 201, f"Falló la ingesta HTTP: {response.status_code}")
        event = response.json()["items"][0]
        check(event["severity"] == "ERROR", "No se normalizó la severidad")
        response = client.get("/v1/logs", headers=headers, params={"source": "http-smoke-host", "text": "timeout", "limit": 1})
        check(response.status_code == 200, "Falló la consulta de logs")
        check(response.json()["items"][0]["id"] == event["id"], "La consulta no recuperó el evento persistido")
        response = client.post("/v1/analyses", headers=headers, json={"log_ids": [event["id"]]})
        check(response.status_code == 201, f"Falló el análisis HTTP: {response.status_code}")
        analysis = response.json()
        evidence = analysis["diagnosis"]["evidence"][0]["log_id"]
        check(evidence == event["id"], "La evidencia no coincide con el evento seleccionado")
        detail = client.get(f"/v1/logs/{evidence}", headers=headers)
        check(detail.status_code == 200 and detail.json()["id"] == evidence, "No se puede consultar la evidencia")
        detail = client.get(f'/v1/analyses/{analysis["id"]}', headers=headers)
        check(detail.status_code == 200 and detail.json() == analysis, "No se conservó el diagnóstico")
        history = client.get("/v1/analyses", headers=headers)
        check(history.status_code == 200 and history.json()["items"][0]["id"] == analysis["id"], "El historial no contiene el análisis")

        collect = load_collector()
        source = temporary / "synthetic.log"
        checkpoint = temporary / "checkpoint.json"
        source.write_bytes("Primera línea sintética\nSegunda línea sintética\n".encode())
        config = {"file": str(source), "checkpoint": str(checkpoint), "source": "collector-http-smoke",
                  "service": "file-example", "url": base_url, "batch_size": 1, "severity": "INFO"}
        previous_url = os.environ.pop("IALOGS_URL", None)
        try:
            collect(config, key, once=True)
            count = lambda: client.get("/v1/logs", headers=headers, params={"source": config["source"]}).json()["total"]
            check(count() == 2 and checkpoint.exists(), "El colector no persistió sus dos líneas")
            collect(config, key, once=True)
            check(count() == 2, "El reinicio del colector duplicó líneas ya confirmadas")
            with source.open("ab") as target:
                target.write("Tercera línea sintética\n".encode())
            collect(config, key, once=True)
            check(count() == 3, "El colector no recuperó solamente la línea añadida")
        finally:
            if previous_url is not None:
                os.environ["IALOGS_URL"] = previous_url
        print("HTTP OK: health, autenticación, ingesta, filtros, análisis, evidencias e historial.")
        print("Colector HTTP OK: lotes, checkpoint, reinicio sin duplicados y nueva línea.")


def main():
    raw_url = os.environ.get("TEST_DATABASE_URL")
    if not raw_url:
        raise RuntimeError("Define TEST_DATABASE_URL para una base PostgreSQL de pruebas")
    url = make_url(raw_url)
    check(url.drivername == "postgresql+psycopg", "TEST_DATABASE_URL debe usar postgresql+psycopg://")
    schema = "ial_smoke_" + uuid4().hex
    check(re.fullmatch(r"ial_smoke_[0-9a-f]{32}", schema), "Nombre de esquema inesperado")
    admin = create_engine(url)
    backend = Path.cwd() if (Path.cwd() / "alembic.ini").exists() else Path(__file__).resolve().parents[1] / "backend"
    sys.path.insert(0, str(backend))
    scoped_url = url.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    previous_database = os.environ.get("DATABASE_URL")
    process = None
    server = None
    server_thread = None
    schema_created = False
    try:
        with admin.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            schema_created = True
        os.environ["DATABASE_URL"] = scoped_url
        config = Config(str(backend / "alembic.ini"))
        config.set_main_option("script_location", str(backend / "migrations"))
        command.upgrade(config, "head")
        server = ThreadingHTTPServer(("127.0.0.1", 0), SimulatedOllama)
        server.model_calls = 0
        server_thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
        server_thread.start()
        port = available_port()
        key = "http-smoke-" + uuid4().hex
        environment = {**os.environ, "DATABASE_URL": scoped_url, "API_KEY": key,
                       "OLLAMA_BASE_URL": f"http://127.0.0.1:{server.server_port}", "OLLAMA_MODEL": "simulated-smoke-model",
                       "OLLAMA_TIMEOUT_SECONDS": "5", "PYTHONPATH": str(backend)}
        with tempfile.TemporaryDirectory(prefix="ialogs-http-smoke-") as directory:
            temporary = Path(directory)
            with (temporary / "uvicorn.log").open("w+b") as output:
                process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                                            "--port", str(port), "--no-access-log"],
                                           cwd=backend, env=environment, stdout=output, stderr=subprocess.STDOUT)
                try:
                    base_url = f"http://127.0.0.1:{port}"
                    with httpx.Client(timeout=0.5, trust_env=False) as probe:
                        for _ in range(100):
                            if process.poll() is not None:
                                raise RuntimeError("Uvicorn terminó antes de estar disponible")
                            try:
                                if probe.get(base_url + "/health").status_code == 200:
                                    break
                            except httpx.RequestError:
                                pass
                            time.sleep(0.1)
                        else:
                            raise RuntimeError("Uvicorn/PostgreSQL no están disponibles tras el tiempo de espera")
                    exercise_http(base_url, key, temporary)
                    check(server.model_calls == 1, "No se completó exactamente una llamada HTTP a Ollama simulado")
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
                    process = None
        print("Prueba HTTP terminada con Ollama simulado; no demuestra el funcionamiento del modelo real.")
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if server is not None:
            server.shutdown()
            server.server_close()
        if server_thread is not None:
            server_thread.join(timeout=5)
        if previous_database is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database
        if schema_created:
            with admin.begin() as connection:
                connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()


if __name__ == "__main__":
    main()

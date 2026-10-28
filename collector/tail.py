"""Colector UTF-8 mínimo con checkpoint y entrega al menos una vez.

No ejecuta el contenido. Una caída tras confirmar el POST y antes de guardar el
checkpoint puede duplicar el lote. No es un sustituto de un agente de producción.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
import tomllib
from urllib import error, request


class NoRedirect(request.HTTPRedirectHandler):
    """Never forward the API key to a redirected URL, including the same origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


open_request = request.build_opener(NoRedirect()).open


def collect(config, key, once=False):
    path = Path(config['file'])
    checkpoint = Path(config['checkpoint'])
    batch_size = int(config.get('batch_size', 100))
    max_line = int(config.get('max_line_bytes', 16384))
    if not 1 <= batch_size <= 100 or not 1 <= max_line <= 16384:
        raise ValueError('batch_size debe estar entre 1 y 100; max_line_bytes entre 1 y 16384')
    state = json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
    retry_seconds = 1
    while True:
        with path.open('rb') as stream:
            stat = os.fstat(stream.fileno())
            identity = f'{stat.st_dev}:{stat.st_ino}'
            offset = state.get('offset', 0) if state.get('identity') == identity else 0
            if stat.st_size < offset:
                offset = 0
            stream.seek(offset)
            events = []
            for _ in range(batch_size):
                start = stream.tell()
                raw = stream.readline(max_line + 2)
                if not raw or not raw.endswith(b'\n'):
                    if len(raw.rstrip(b'\r\n')) > max_line:
                        raise ValueError('Línea demasiado larga; checkpoint conservado. Revisa el archivo.')
                    stream.seek(start)  # Una línea incompleta se enviará al llegar su salto final.
                    break
                raw = raw.rstrip(b'\r\n')
                if len(raw) > max_line:
                    raise ValueError('Línea demasiado larga; checkpoint conservado. Revisa el archivo.')
                events.append({
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'source': config['source'], 'service': config.get('service'),
                    'severity': config.get('severity', 'INFO'), 'message': raw.decode('utf-8', errors='strict') or '(línea vacía)',
                    'attributes': {'file': str(path), 'byte_offset': start, 'timestamp_kind': 'collection_time'},
                })
            next_offset = stream.tell()
        if events:
            url = os.getenv('IALOGS_URL', config.get('url', 'http://127.0.0.1:8000')).rstrip('/')
            payload = json.dumps({'events': events}).encode('utf-8')
            if len(payload) > 2_097_152:
                raise ValueError('Lote excede 2 MiB; reduce batch_size.')
            req = request.Request(url + '/v1/logs', data=payload,
                                  headers={'X-API-Key': key, 'Content-Type': 'application/json'})
            try:
                with open_request(req, timeout=30) as response:
                    if response.status != 201:
                        raise ValueError(f'Estado inesperado: {response.status}')
                    result = json.load(response)
                    if len(result.get('items', [])) != len(events):
                        raise ValueError('Respuesta incompleta; checkpoint conservado.')
            except error.HTTPError as exc:
                if 300 <= exc.code < 400:
                    raise ValueError(f'Redirección HTTP rechazada (HTTP {exc.code}); revisa IALOGS_URL. Checkpoint conservado.') from None
                if exc.code < 500:
                    raise ValueError(f'La API rechazó el lote (HTTP {exc.code}); checkpoint conservado.') from None
                if once:
                    raise ValueError(f'La API no está disponible (HTTP {exc.code}).') from None
                print('API no disponible; se reintentará sin avanzar el checkpoint.', flush=True)
                time.sleep(retry_seconds)
                retry_seconds = min(retry_seconds * 2, 30)
                continue
            except (error.URLError, TimeoutError):
                if once:
                    raise ValueError('No se pudo conectar con la API; checkpoint conservado.') from None
                print('Sin conexión; se reintentará sin avanzar el checkpoint.', flush=True)
                time.sleep(retry_seconds)
                retry_seconds = min(retry_seconds * 2, 30)
                continue
            state = {'identity': identity, 'offset': next_offset}
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            temporary = checkpoint.with_suffix('.tmp')
            temporary.write_text(json.dumps(state), encoding='utf-8')
            temporary.replace(checkpoint)
            retry_seconds = 1
            print(f'{len(events)} eventos confirmados; offset {next_offset}', flush=True)
            continue  # --once drena todos los lotes completos.
        if once:
            return
        time.sleep(float(config.get('poll_seconds', 1)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    key = os.getenv('API_KEY')
    if not key:
        sys.exit('Define API_KEY en el entorno.')
    try:
        with open(args.config, 'rb') as source:
            collect(tomllib.load(source), key, args.once)
    except (ValueError, OSError, UnicodeError) as exc:
        sys.exit(str(exc))


if __name__ == '__main__':
    main()

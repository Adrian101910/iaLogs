"""Recoge logs de un contenedor mediante la CLI local de Docker (Python 3.12).

API key solo desde API_KEY o .env. Entrega al menos una vez: una caída entre el
POST y el checkpoint puede duplicar el último lote. No ejecuta los mensajes.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parents[1]
SEVERITIES = {'TRACE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
ALIASES = {'WARN': 'WARNING', 'ERR': 'ERROR', 'FATAL': 'CRITICAL'}
TIMESTAMP = re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z (.*)$', re.DOTALL)


class CollectionError(Exception):
    pass


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


open_request = request.build_opener(request.ProxyHandler({}), NoRedirect()).open


def docker_environment():
    # La CLI no necesita la clave de ingesta.
    return {name: value for name, value in os.environ.items() if name != 'API_KEY'}


def docker_output(arguments):
    try:
        result = subprocess.run(['docker', *arguments], capture_output=True, timeout=15,
                                check=False, env=docker_environment())
    except (OSError, subprocess.TimeoutExpired):
        raise CollectionError('No se puede ejecutar Docker. Comprueba Docker Desktop y la CLI.') from None
    if result.returncode:
        raise CollectionError('Docker rechazó la consulta. Comprueba el nombre del contenedor o servicio.')
    try:
        return result.stdout.decode('utf-8')
    except UnicodeError:
        raise CollectionError('Docker devolvió metadatos UTF-8 inválidos.') from None


def inspect_container(container=None, service=None):
    target = container or service
    if not target or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,254}', target):
        raise CollectionError('Nombre de contenedor o servicio no válido.')
    if service:
        ids = docker_output(['compose', 'ps', '--all', '--quiet', '--', service]).split()
        if len(ids) != 1:
            raise CollectionError('El servicio debe tener un contenedor. Usa --container para elegir una réplica.')
        target = ids[0]
    # Solo se consultan estos campos; nunca Config.Env ni credenciales.
    template = '{{json .Id}}\n{{json .Name}}\n{{json .Config.Labels}}'
    try:
        identifier, name, labels = [json.loads(line) for line in docker_output(
            ['inspect', '--type', 'container', '--format', template, '--', target]).splitlines()]
        if not re.fullmatch(r'[0-9a-f]{64}', identifier):
            raise ValueError('ID inválido')
        labels = labels or {}
        return {'id': identifier, 'name': name.lstrip('/'),
                'service': labels.get('com.docker.compose.service'),
                'project': labels.get('com.docker.compose.project')}
    except (ValueError, TypeError, AttributeError):
        raise CollectionError('Los metadatos del contenedor no tienen el formato esperado.') from None


def infer_severity(message):
    try:
        data = json.loads(message)
    except ValueError:
        data = None
    if isinstance(data, dict):
        value = data.get('level', data.get('severity'))
        if isinstance(value, str):
            value = ALIASES.get(value.upper(), value.upper())
            if value in SEVERITIES:
                return value, 'json_level'
    match = re.match(r'^\s*\[?(TRACE|DEBUG|INFO|WARNING|WARN|ERROR|ERR|CRITICAL|FATAL)\b', message, re.IGNORECASE)
    if match:
        value = match[1].upper()
        return ALIASES.get(value, value), 'prefix'
    return 'INFO', 'default'


def parse_line(raw, container, max_line_bytes=16_384):
    try:
        line = raw.decode('utf-8').rstrip('\r\n')
    except UnicodeError:
        raise CollectionError('Log UTF-8 inválido; checkpoint conservado.') from None
    match = TIMESTAMP.fullmatch(line)
    if not match:
        raise CollectionError('Docker devolvió una línea sin timestamp válido; checkpoint conservado.')
    stamp = f'{match[1]}.{(match[2] or "").ljust(9, "0")}Z'
    message = match[3]
    try:
        datetime.fromisoformat(stamp)
    except ValueError:
        raise CollectionError('Timestamp de Docker inválido; checkpoint conservado.') from None
    if len(message.encode('utf-8')) > max_line_bytes or '\x00' in message:
        raise CollectionError('Mensaje demasiado largo o con NUL; checkpoint conservado.')
    severity, method = infer_severity(message)
    event = {
        'timestamp': stamp, 'source': 'docker/' + container['name'][:248],
        'service': (container.get('service') or container['name'])[:255],
        'severity': severity, 'message': message or '(línea vacía)',
        'attributes': {
            'collector': 'docker-cli-v1', 'container_id': container['id'],
            'container_name': container['name'], 'compose_project': container.get('project'),
            'docker_timestamp': stamp, 'stream': 'stdout_stderr_combined', 'severity_method': method,
        },
    }
    digest = hashlib.sha256((stamp + '\x00' + message).encode('utf-8')).hexdigest()
    return {'timestamp': stamp, 'digest': digest, 'event': event}


def read_snapshot(container, since, max_lines=1000, max_line_bytes=16_384):
    until = datetime.now(timezone.utc).isoformat()
    arguments = ['docker', 'logs', '--timestamps', '--since', since, '--until', until,
                 '--tail', str(max_lines + 1), '--', container['id']]
    try:
        process = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   env=docker_environment())
    except OSError:
        raise CollectionError('No se puede ejecutar Docker.') from None
    expired = threading.Event()

    def timeout():
        expired.set()
        process.kill()

    timer = threading.Timer(30, timeout)
    timer.daemon = True
    timer.start()
    records, total_bytes = [], 0
    try:
        while raw := process.stdout.readline(max_line_bytes + 66):
            total_bytes += len(raw)
            if len(raw) > max_line_bytes + 64 or total_bytes > 2_097_152:
                raise CollectionError('La lectura supera los límites; reduce --since o el volumen de logs.')
            records.append(parse_line(raw, container, max_line_bytes))
            if len(records) > max_lines:
                raise CollectionError('Hay más líneas que --max-lines; aumenta el límite o acota --since. No se ha avanzado el checkpoint.')
        process.wait(timeout=5)
        if expired.is_set() or process.returncode:
            raise CollectionError('Docker no pudo completar la lectura. Comprueba el contenedor y su driver de logs.')
    finally:
        timer.cancel()
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()
    return sorted(records, key=lambda item: item['timestamp'])


def load_state(path, container, url):
    if not path.exists():
        return {'version': 1, 'container_id': container['id'], 'url': url, 'seen': {}}
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
        if (state['version'] != 1 or state['container_id'] != container['id'] or state['url'] != url
                or not isinstance(state['seen'], dict)):
            raise ValueError('Checkpoint incompatible')
        for digest, item in state['seen'].items():
            if not re.fullmatch(r'[a-f0-9]{64}', digest) or item['count'] < 1:
                raise ValueError('Checkpoint inválido')
            datetime.fromisoformat(item['timestamp'])
        if 'latest' in state:
            datetime.fromisoformat(state['latest'])
            datetime.fromisoformat(state['since'])
        return state
    except (ValueError, TypeError, KeyError, AttributeError):
        raise CollectionError('Checkpoint inválido o de otra API; revísalo antes de continuar.') from None


def send_batch(url, key, events):
    body = json.dumps({'events': events}, ensure_ascii=False).encode('utf-8')
    if len(body) > 2_097_152:
        raise CollectionError('El lote supera 2 MiB; reduce --batch-size.')
    req = request.Request(url + '/v1/logs', data=body,
                          headers={'X-API-Key': key, 'Content-Type': 'application/json'})
    try:
        with open_request(req, timeout=30) as response:
            result = json.loads(response.read(2_097_153))
            if response.status != 201 or len(result.get('items', [])) != len(events):
                raise ValueError('Confirmación incompleta')
    except error.HTTPError as exc:
        raise CollectionError(f'La API rechazó el lote (HTTP {exc.code}); checkpoint conservado.') from None
    except (error.URLError, TimeoutError):
        raise CollectionError('No se puede conectar con la API; checkpoint conservado.') from None
    except (ValueError, TypeError, AttributeError):
        raise CollectionError('La API devolvió una confirmación inválida; checkpoint conservado.') from None


def collect_once(container, key, url, checkpoint_dir, since='15m', max_lines=1000, batch_size=100):
    checkpoint = Path(checkpoint_dir) / (container['id'] + '.json')
    state = load_state(checkpoint, container, url)
    records = read_snapshot(container, state.get('since', since), max_lines)
    observed = Counter()
    pending = []
    for record in records:
        observed[record['digest']] += 1
        if observed[record['digest']] > state['seen'].get(record['digest'], {}).get('count', 0):
            pending.append(record)
    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        send_batch(url, key, [record['event'] for record in batch])
        for record in batch:
            entry = state['seen'].setdefault(record['digest'], {'timestamp': record['timestamp'], 'count': 0})
            entry['count'] += 1
        state['latest'] = max([state.get('latest', ''), *[record['timestamp'] for record in batch]])
        # Ventana solapada de al menos un segundo: conserva nanosegundos y los
        # recuentos de líneas idénticas; --since no depende de precisión microsegundo.
        boundary = datetime.fromisoformat(state['latest']).replace(microsecond=0) - timedelta(seconds=1)
        state['since'] = boundary.isoformat().replace('+00:00', 'Z')
        state['seen'] = {digest: item for digest, item in state['seen'].items()
                         if datetime.fromisoformat(item['timestamp']) >= boundary}
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        temporary = checkpoint.with_suffix('.tmp')
        temporary.write_text(json.dumps(state), encoding='utf-8')
        temporary.replace(checkpoint)
    return len(pending)


def api_key(env_file):
    key = os.environ.get('API_KEY')
    if key:
        return key
    if Path(env_file).exists():
        for line in Path(env_file).read_text(encoding='utf-8-sig').splitlines():
            name, separator, value = line.partition('=')
            if separator and name.strip() == 'API_KEY':
                key = value.strip().strip('\"\'')
                if key:
                    return key
    raise CollectionError('Define API_KEY o proporciona un .env con --env-file. No pases la clave como argumento.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--container', help='Nombre o ID del contenedor')
    source.add_argument('--service', help='Servicio del proyecto Compose actual')
    parser.add_argument('--api-url', default='http://127.0.0.1:8000')
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    parser.add_argument('--checkpoint-dir', type=Path, default=ROOT / '.local' / 'docker-checkpoints')
    parser.add_argument('--since', default='15m', help='Historial inicial; ignorado cuando hay checkpoint')
    parser.add_argument('--max-lines', type=int, default=1000)
    parser.add_argument('--batch-size', type=int, default=100)
    parser.add_argument('--poll-seconds', type=float, default=2)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    url = args.api_url.rstrip('/')
    parsed = parse.urlsplit(url)
    if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        parser.error('--api-url debe ser HTTP(S), sin credenciales, query ni fragmento')
    if not 1 <= args.max_lines <= 5000 or not 1 <= args.batch_size <= 100 or not 0.2 <= args.poll_seconds <= 60:
        parser.error('Límites: max-lines 1–5000, batch-size 1–100, poll-seconds 0.2–60')
    try:
        key = api_key(args.env_file)
        if not args.once:
            print('Colector Docker iniciado. Ctrl+C para detener; checkpoint persistente.', flush=True)
        while True:
            try:
                container = inspect_container(args.container, args.service)
                total = collect_once(container, key, url, args.checkpoint_dir, args.since, args.max_lines, args.batch_size)
                if total or args.once:
                    print(f'Docker {container["name"]}: {total} eventos nuevos confirmados.', flush=True)
            except CollectionError as exc:
                if args.once:
                    raise
                print(str(exc), flush=True)
            if args.once:
                return
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        print('Colector detenido; checkpoint conservado.')
    except (CollectionError, OSError):
        # Los mensajes controlados no incluyen cuerpo de logs ni claves.
        error_value = sys.exception()
        sys.exit(str(error_value) if isinstance(error_value, CollectionError) else 'Error de acceso a archivos; revisa .env y el directorio de checkpoints.')


if __name__ == '__main__':
    main()

"""Arranque reproducible de iaLogs con credenciales únicas y sin descargar modelos."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

from setup_env import prepare as prepare_engine
from setup_php_web import prepare as prepare_portal, read_env

ROOT = Path(__file__).resolve().parents[1]


def commands(project: str, ollama: str, gpu: bool, portal: bool) -> tuple[list[str], list[str]]:
    engine = ['docker', 'compose', '--project-name', project, '-f', 'compose.yaml']
    if ollama == 'container':
        engine += ['-f', 'compose.ai.yaml']
        if gpu:
            engine += ['-f', 'compose.ai.gpu.yaml']
    web = ['docker', 'compose', '--env-file', '.local/php-web.env', '--project-name', project + '-php',
           '-f', 'compose.php.yaml', '-f', 'compose.php.local.yaml'] if portal else []
    return engine, web


def run(command: list[str], environment: dict[str, str]):
    subprocess.run(command, cwd=ROOT, env=environment, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default='ialogs')
    parser.add_argument('--ollama', choices=['container', 'host'], default='container')
    parser.add_argument('--gpu', action='store_true')
    parser.add_argument('--without-portal', action='store_true')
    parser.add_argument('--no-demo', action='store_true')
    parser.add_argument('--model', help='Solo se aplica al crear .env; por defecto qwen2.5-coder:1.5b')
    parser.add_argument('--api-port', type=int, default=8000)
    parser.add_argument('--frontend-port', type=int, default=8080)
    parser.add_argument('--portal-port', type=int, default=8090)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,39}', args.project):
        parser.error('--project debe contener minúsculas, números, guiones o guiones bajos.')
    if args.gpu and args.ollama != 'container':
        parser.error('--gpu solo corresponde a --ollama container.')
    if args.model and not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,199}', args.model):
        parser.error('Nombre de modelo no válido.')
    ports = [args.api_port, args.frontend_port, args.portal_port]
    if any(not 1 <= port <= 65535 for port in ports) or len(set(ports)) != 3:
        parser.error('Utiliza tres puertos distintos entre 1 y 65535.')
    environment = {**os.environ, 'API_PORT': str(args.api_port), 'FRONTEND_PORT': str(args.frontend_port),
                   'PHP_PORT': str(args.portal_port), 'ENGINE_NETWORK': args.project + '_default'}
    try:
        run(['docker', 'info', '--format', '{{.ServerVersion}}'], environment)
        prepare_engine(ROOT, args.model or 'qwen2.5-coder:1.5b')
        settings = read_env(ROOT / '.env')
        if args.model and settings.get('OLLAMA_MODEL') != args.model:
            raise SystemExit('.env ya existe con otro modelo. Se conserva; edítalo expresamente para cambiar OLLAMA_MODEL.')
        if not args.without_portal:
            prepare_portal(ROOT, 'http://backend:8000')
        engine, portal = commands(args.project, args.ollama, args.gpu, not args.without_portal)
        run(engine + ['up', '-d', '--build', '--wait', '--wait-timeout', '180'], environment)
        marker = ROOT / '.local' / ('demo-' + args.project + '.seeded')
        if not args.no_demo and not marker.exists():
            run(engine + ['--profile', 'tools', 'run', '--rm', 'sender'], environment)
            marker.write_text('demo synthetic events\n', encoding='utf-8')
        if portal:
            run(portal + ['up', '-d', '--build', '--wait', '--wait-timeout', '180', 'web'], environment)
        state = {'project': args.project, 'ollama': args.ollama, 'gpu': args.gpu, 'portal': bool(portal),
                 'api_port': args.api_port, 'frontend_port': args.frontend_port, 'portal_port': args.portal_port}
        (ROOT / '.local' / 'start-options.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
        print(f'\nExplorador: http://127.0.0.1:{args.frontend_port} (API_KEY en .env)')
        if portal:
            print(f'Web PHP: http://127.0.0.1:{args.portal_port} (credenciales en .local/php-admin.txt)')
        print('No se ha descargado ningún modelo. Para hacerlo cuando quieras:')
        if args.ollama == 'container':
            print(' '.join(engine + ['exec', 'ollama', 'ollama', 'pull', settings['OLLAMA_MODEL']]))
        else:
            print('ollama pull ' + settings['OLLAMA_MODEL'])
        print('Parada que conserva los datos:')
        if portal:
            print(' '.join(portal + ['stop']))
        print(' '.join(engine + ['stop']))
    except FileNotFoundError:
        raise SystemExit('Instala Docker con Compose y arranca su motor antes de ejecutar este comando.') from None
    except subprocess.CalledProcessError:
        raise SystemExit('El arranque no se completó. Revisa el error de Docker anterior; los datos existentes se conservan.') from None


if __name__ == '__main__':
    main()

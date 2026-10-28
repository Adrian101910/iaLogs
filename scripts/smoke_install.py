"""Arranca una copia limpia aislada, prueba HTTP y conserva sus volúmenes al parar."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from uuid import uuid4

from check_public import public_files

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def main():
    project = 'ialogs-check-' + uuid4().hex[:8]
    copy = ROOT / '.local' / project
    copy.mkdir(parents=True)
    for source in public_files():
        relative = source.relative_to(ROOT)
        if source.is_symlink() or any(part in {'.local', 'node_modules', '.git'} for part in relative.parts):
            raise RuntimeError('La copia limpia no admite datos locales ni enlaces.')
        destination = copy / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    ports = set()
    while len(ports) < 3:
        ports.add(free_port())
    api, frontend, php = sorted(ports)
    environment = {**os.environ, 'API_PORT': str(api), 'FRONTEND_PORT': str(frontend), 'PHP_PORT': str(php),
                   'ENGINE_NETWORK': project + '_default'}
    engine = ['docker', 'compose', '--project-name', project, '-f', 'compose.yaml']
    portal = ['docker', 'compose', '--env-file', '.local/php-web.env', '--project-name', project + '-php',
              '-f', 'compose.php.yaml', '-f', 'compose.php.local.yaml']

    def run(command):
        subprocess.run(command, cwd=copy, env=environment, check=True)

    try:
        # No requiere Ollama instalado ni descarga modelos: el recorrido de IA
        # simulado se prueba separadamente con PostgreSQL y HTTP reales.
        run([sys.executable, 'scripts/quickstart.py', '--project', project, '--ollama', 'host',
             '--api-port', str(api), '--frontend-port', str(frontend), '--portal-port', str(php)])
        run([sys.executable, 'scripts/php_web_smoke.py', '--url', f'http://127.0.0.1:{php}/'])
        run([sys.executable, 'scripts/setup_env.py'])
        run([sys.executable, 'scripts/setup_php_web.py'])
        check = {'project': project, 'path': str(copy), 'status': 'passed', 'model_tested': False}
        (ROOT / '.local' / 'clean-install-result.json').write_text(json.dumps(check, indent=2), encoding='utf-8')
        print('Instalación limpia OK: secretos nuevos, migraciones, MySQL, PostgreSQL, portal y API por red privada.')
    finally:
        if (copy / '.local' / 'php-web.env').exists():
            subprocess.run(portal + ['stop'], cwd=copy, env=environment, check=False)
        if (copy / '.env').exists():
            subprocess.run(engine + ['stop'], cwd=copy, env=environment, check=False)
        print(f'Copia de prueba conservada en .local/{project}; no se borran volúmenes.')


if __name__ == '__main__':
    main()

"""Comprueba el contenido que Git publicaría, sin mostrar valores de secretos."""
import base64
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {'.env', 'local.php', 'php-admin.txt', 'php-web.env'}


def public_files(root: Path = ROOT) -> list[Path]:
    result = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=root,
                            capture_output=True, check=True)
    return sorted({root / name for name in result.stdout.decode('utf-8').split('\0') if name})


def private_values(root: Path) -> list[bytes]:
    values = []
    for source in [root / '.env', root / '.local' / 'php-web.env']:
        if not source.exists():
            continue
        for line in source.read_text(encoding='utf-8-sig').splitlines():
            name, separator, value = line.partition('=')
            if not separator or not re.search(r'PASSWORD|API_KEY|APP_SECRET|TOKEN', name):
                continue
            value = value.strip().strip('"\'')
            if len(value) >= 16 and not value.startswith('replace-with-'):
                raw = value.encode('utf-8')
                values += [raw, base64.b64encode(raw)]
    return values


def main():
    values = private_values(ROOT)
    files = public_files()
    failures = []
    for source in files:
        relative = source.relative_to(ROOT)
        if (source.name in FORBIDDEN or any(part in {'.local', 'storage', 'node_modules', '__pycache__'} for part in relative.parts)
                or (source.name.startswith('.env.') and source.name != '.env.example')):
            failures.append(str(relative) + ': archivo privado o generado')
            continue
        if source.is_symlink() or not source.resolve().is_relative_to(ROOT.resolve()):
            failures.append(str(relative) + ': enlace o ruta fuera del proyecto')
            continue
        data = source.read_bytes()
        if any(value in data for value in values):
            failures.append(str(relative) + ': contiene un secreto local')
        markers = [b'-----BEGIN ' + suffix for suffix in [b'PRIVATE KEY-----', b'OPENSSH PRIVATE KEY-----']]
        if any(marker in data for marker in markers):
            failures.append(str(relative) + ': contiene una clave privada')
    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        raise SystemExit('No publiques hasta corregir los archivos indicados. Los valores no se muestran.')
    print(f'Contenido público comprobado: {len(files)} archivos; configuración local y credenciales excluidas.')


if __name__ == '__main__':
    main()

"""Prepara secretos del portal PHP sin modificar el .env del motor."""
from pathlib import Path
import hashlib
import secrets

def read_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        name, separator, value = line.partition('=')
        if separator and not name.lstrip().startswith('#'):
            values[name.strip()] = value.strip().strip('"\'')
    return values


def prepare(root: Path, engine_url: str = 'http://host.docker.internal:8000') -> bool:
    directory = root / '.local'
    directory.mkdir(exist_ok=True)
    target = directory / 'php-web.env'
    credentials = directory / 'php-admin.txt'
    if target.exists():
        print('.local/php-web.env existente conservado.')
        return False
    if credentials.exists():
        raise SystemExit('Existen credenciales sin configuración. Revisa .local antes de continuar; no se sobrescriben.')
    api_key = read_env(root / '.env').get('API_KEY', '')
    if len(api_key) < 32:
        raise SystemExit('Prepara primero el .env de iaLogs con una API_KEY válida.')
    password = secrets.token_urlsafe(24)
    token = secrets.token_urlsafe(32)
    settings = {
        'MYSQL_PASSWORD': secrets.token_hex(32), 'MYSQL_ROOT_PASSWORD': secrets.token_hex(32),
        'APP_SECRET': secrets.token_hex(32), 'APP_ADMIN_EMAIL': 'admin@ialogs.local',
        'APP_ADMIN_PASSWORD': password, 'APP_INSTALL_TOKEN_HASH': hashlib.sha256(token.encode()).hexdigest(),
        'IALOGS_API_URL': engine_url, 'IALOGS_API_KEY': api_key,
    }
    with target.open('x', encoding='utf-8') as output:
        output.write('\n'.join(f'{name}={value}' for name, value in settings.items()) + '\n')
    target.chmod(0o600)
    with credentials.open('x', encoding='utf-8') as output:
        output.write(f'Email: {settings["APP_ADMIN_EMAIL"]}\nContraseña: {password}\n\nToken temporal para una instalación nueva: {token}\nHash del token: {settings["APP_INSTALL_TOKEN_HASH"]}\n')
    credentials.chmod(0o600)
    print('Configuración y credenciales propias creadas en .local/php-web.env y .local/php-admin.txt.')
    return True


if __name__ == '__main__':
    prepare(Path(__file__).resolve().parents[1])

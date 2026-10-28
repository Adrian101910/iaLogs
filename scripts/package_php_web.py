"""Genera un ZIP para hosting con una lista explícita de archivos, sin secretos."""
import hashlib
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
site = root / 'php-site'
dist = site / 'dist'
dist.mkdir(exist_ok=True)
archive = dist / 'ialogs-php-hosting.zip'
allowed = {}
for source in (site / 'public').rglob('*'):
    if source.is_file():
        allowed['public_html/' + source.relative_to(site / 'public').as_posix()] = source
private = site / 'ialogs-private'
for directory in ['app', 'database', 'bin']:
    for source in (private / directory).rglob('*'):
        if source.is_file() and '__pycache__' not in source.parts:
            allowed['ialogs-private/' + source.relative_to(private).as_posix()] = source
allowed['ialogs-private/config/example.php'] = private / 'config' / 'example.php'
allowed['ialogs-private/.htaccess'] = private / '.htaccess'
allowed['INSTALACION.md'] = site / 'README.md'
allowed['LICENSE'] = root / 'LICENSE'
hashes = []
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
    for name, source in sorted(allowed.items()):
        if source.is_symlink() or not (source.resolve().is_relative_to(site.resolve()) or source.resolve() == (root / 'LICENSE').resolve()):
            raise SystemExit('Se rechazó un archivo fuera del directorio del portal.')
        contents = source.read_bytes()
        output.writestr(name, contents)
        hashes.append(hashlib.sha256(contents).hexdigest() + '  ' + name)
    output.writestr('SHA256SUMS', '\n'.join(hashes) + '\n')
with zipfile.ZipFile(archive) as check:
    names = check.namelist()
    if check.testzip() is not None or any(name.endswith('/local.php') or '.env' in Path(name).name or '/storage/' in name for name in names):
        raise SystemExit('La verificación del ZIP no ha pasado.')
    # Comprueba las credenciales locales sin escribirlas en la salida.
    secrets_path = root / '.local' / 'php-web.env'
    if secrets_path.exists():
        secrets = [line.partition('=')[2].encode() for line in secrets_path.read_text().splitlines()
                   if line.partition('=')[0] in {'MYSQL_PASSWORD', 'MYSQL_ROOT_PASSWORD', 'APP_SECRET', 'APP_ADMIN_PASSWORD', 'IALOGS_API_KEY'}]
        for name in names:
            contents = check.read(name)
            if any(secret and secret in contents for secret in secrets):
                raise SystemExit('Se detectó un secreto local en el paquete; no lo distribuyas.')
print(f'Paquete verificado: {archive.relative_to(root)} ({len(names)} archivos, {archive.stat().st_size} bytes).')

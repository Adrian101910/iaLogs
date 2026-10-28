"""Genera configuración local sin sobrescribir secretos existentes."""
import argparse
from pathlib import Path
import secrets


def prepare(root: Path, model: str | None = None) -> bool:
    target = root / '.env'
    created = not target.exists()
    if created:
        content = (root / '.env.example').read_text(encoding='utf-8')
        content = content.replace('replace-with-a-random-key-of-at-least-32-characters', secrets.token_hex(32))
        content = content.replace('replace-with-a-random-hexadecimal-password', secrets.token_hex(32))
        if model:
            content = content.replace('OLLAMA_MODEL=qwen2.5-coder:14b', 'OLLAMA_MODEL=' + model)
        with target.open('x', encoding='utf-8') as output:
            output.write(content)
        target.chmod(0o600)
        print('.env creado con secretos propios de esta instalación.')
    else:
        print('.env existente conservado.')
    logs = root / '.local' / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    if not (logs / 'app.log').exists():
        (logs / 'app.log').write_bytes((root / 'collector' / 'sample.txt').read_bytes())
    return created


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model')
    args = parser.parse_args()
    if args.model and any(character.isspace() for character in args.model):
        parser.error('El nombre del modelo no admite espacios ni saltos de línea.')
    prepare(Path(__file__).resolve().parents[1], args.model)


if __name__ == '__main__':
    main()

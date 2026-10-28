"""Instalación inicial: secretos independientes e idempotencia."""
import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def scripts():
    directory = Path(__file__).resolve().parents[2] / 'scripts'
    if not directory.exists():
        directory = Path('/scripts')

    def load(name):
        spec = importlib.util.spec_from_file_location('test_' + name, directory / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return load('setup_env'), load('setup_php_web')


def empty_install(path):
    path.mkdir()
    (path / 'collector').mkdir()
    (path / 'collector' / 'sample.txt').write_text('sample\n')
    (path / '.env.example').write_text('API_KEY=replace-with-a-random-key-of-at-least-32-characters\n'
        'POSTGRES_PASSWORD=replace-with-a-random-hexadecimal-password\nOLLAMA_MODEL=qwen2.5-coder:14b\n')
    return path


def test_each_install_has_its_own_secrets(scripts, tmp_path):
    engine, portal = scripts
    one, two = [empty_install(tmp_path / name) for name in ['one', 'two']]
    for directory in [one, two]:
        assert engine.prepare(directory, 'qwen2.5-coder:1.5b')
        assert portal.prepare(directory, 'http://backend:8000')
    first, second = [portal.read_env(directory / '.env') for directory in [one, two]]
    assert first['API_KEY'] != second['API_KEY']
    assert first['POSTGRES_PASSWORD'] != second['POSTGRES_PASSWORD']
    assert first['OLLAMA_MODEL'] == 'qwen2.5-coder:1.5b'
    php_one, php_two = [portal.read_env(directory / '.local' / 'php-web.env') for directory in [one, two]]
    assert php_one['APP_ADMIN_PASSWORD'] != php_two['APP_ADMIN_PASSWORD']
    assert php_one['APP_SECRET'] != php_two['APP_SECRET']
    assert php_one['IALOGS_API_KEY'] == first['API_KEY']
    assert php_one['IALOGS_API_URL'] == 'http://backend:8000'


def test_repeated_setup_preserves_configuration_and_passwords(scripts, tmp_path):
    engine, portal = scripts
    directory = empty_install(tmp_path / 'project')
    engine.prepare(directory)
    portal.prepare(directory)
    paths = [directory / '.env', directory / '.local' / 'php-web.env', directory / '.local' / 'php-admin.txt']
    before = [path.read_bytes() for path in paths]
    assert not engine.prepare(directory, 'different-model')
    assert not portal.prepare(directory, 'http://different-engine')
    assert before == [path.read_bytes() for path in paths]


def test_existing_env_does_not_prevent_sample_preparation(scripts, tmp_path):
    engine, _ = scripts
    directory = empty_install(tmp_path / 'project')
    original = b'API_KEY=existing-private-key-that-must-be-preserved\n'
    (directory / '.env').write_bytes(original)
    engine.prepare(directory)
    assert (directory / '.local' / 'logs' / 'app.log').read_text() == 'sample\n'
    assert (directory / '.env').read_bytes() == original


def test_orphaned_credentials_are_never_overwritten(scripts, tmp_path):
    engine, portal = scripts
    directory = empty_install(tmp_path / 'project')
    engine.prepare(directory)
    credentials = directory / '.local' / 'php-admin.txt'
    credentials.write_text('existing credentials')
    with pytest.raises(SystemExit):
        portal.prepare(directory)
    assert credentials.read_text() == 'existing credentials'
    assert not (directory / '.local' / 'php-web.env').exists()

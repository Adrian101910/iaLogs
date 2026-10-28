"""Regresiones del adaptador Docker; la prueba real se ejecuta desde el host."""
import importlib.util
import io
import json
from pathlib import Path

import pytest


@pytest.fixture
def docker_collector():
    path = Path(__file__).resolve().parents[2] / 'scripts' / 'collect_docker.py'
    if not path.exists():
        path = Path('/scripts/collect_docker.py')
    spec = importlib.util.spec_from_file_location('docker_collector_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def container():
    return {'id': 'a' * 64, 'name': 'my-container', 'service': 'api', 'project': 'local'}


def record(module, container, message='INFO: started', stamp='2026-10-28T12:00:10.123456789Z'):
    return module.parse_line(f'{stamp} {message}\n'.encode(), container)


def test_nanoseconds_and_severity_are_preserved(docker_collector, container):
    item = record(docker_collector, container, '{"level":"warn","message":"<script>literal</script>"}')
    event = item['event']
    assert event['timestamp'] == event['attributes']['docker_timestamp'] == '2026-10-28T12:00:10.123456789Z'
    assert event['severity'] == 'WARNING'
    assert event['attributes']['severity_method'] == 'json_level'
    assert '<script>literal</script>' in event['message']
    assert event['attributes']['stream'] == 'stdout_stderr_combined'
    assert record(docker_collector, container, 'FATAL: stopped')['event']['severity'] == 'CRITICAL'
    assert record(docker_collector, container, 'not a severity')['event']['attributes']['severity_method'] == 'default'


@pytest.mark.parametrize('raw', [b'no timestamp\n', b'2026-99-99T12:00:00.000000000Z x\n',
                                 b'2026-10-28T12:00:00.000000000Z \xff\n',
                                 b'2026-10-28T12:00:00.000000000Z a\x00b\n',
                                 b'2026-10-28T12:00:00.000000000Z ' + b'x' * 16385 + b'\n'])
def test_invalid_lines_are_rejected(docker_collector, container, raw):
    with pytest.raises(docker_collector.CollectionError):
        docker_collector.parse_line(raw, container)


def test_checkpoint_skips_old_lines_and_counts_identical_timestamps(docker_collector, container, tmp_path, monkeypatch):
    module = docker_collector
    a, b = record(module, container, 'sensitive a'), record(module, container, 'sensitive b')
    snapshot = [a, a, b]
    sends, cursors = [], []

    def read(meta, since, max_lines):
        cursors.append(since)
        return snapshot.copy()

    monkeypatch.setattr(module, 'read_snapshot', read)
    monkeypatch.setattr(module, 'send_batch', lambda url, key, events: sends.extend(events))
    assert module.collect_once(container, 'secret-key', 'http://localhost:8000', tmp_path) == 3
    assert module.collect_once(container, 'secret-key', 'http://localhost:8000', tmp_path) == 0
    snapshot.append(a)
    assert module.collect_once(container, 'secret-key', 'http://localhost:8000', tmp_path) == 1
    assert len(sends) == 4
    assert cursors[1] == '2026-10-28T12:00:09Z'
    state = (tmp_path / (container['id'] + '.json')).read_text()
    assert 'sensitive' not in state and 'secret-key' not in state
    assert json.loads(state)['seen'][a['digest']]['count'] == 3


def test_partial_api_failure_keeps_only_confirmed_batches(docker_collector, container, tmp_path, monkeypatch):
    module = docker_collector
    snapshot = [record(module, container, f'line {i}') for i in range(4)]
    monkeypatch.setattr(module, 'read_snapshot', lambda *args: snapshot)
    sent = []

    def failing_send(url, key, events):
        if sent:
            raise module.CollectionError('API unavailable')
        sent.extend(events)

    monkeypatch.setattr(module, 'send_batch', failing_send)
    with pytest.raises(module.CollectionError):
        module.collect_once(container, 'key', 'http://localhost:8000', tmp_path, batch_size=2)
    assert len(sent) == 2
    monkeypatch.setattr(module, 'send_batch', lambda url, key, events: sent.extend(events))
    assert module.collect_once(container, 'key', 'http://localhost:8000', tmp_path, batch_size=2) == 2
    assert [item['message'] for item in sent] == [f'line {i}' for i in range(4)]


def test_checkpoint_cannot_be_reused_for_a_different_api(docker_collector, container, tmp_path, monkeypatch):
    module = docker_collector
    monkeypatch.setattr(module, 'read_snapshot', lambda *args: [record(module, container)])
    monkeypatch.setattr(module, 'send_batch', lambda *args: None)
    module.collect_once(container, 'key', 'http://localhost:8000', tmp_path)
    with pytest.raises(module.CollectionError, match='otra API'):
        module.collect_once(container, 'key', 'http://localhost:9000', tmp_path)


def test_snapshot_backlog_does_not_silently_drop_lines(docker_collector, container, monkeypatch):
    module = docker_collector

    class Process:
        def __init__(self):
            self.stdout = io.BytesIO(b'2026-10-28T12:00:10.123456789Z message\n' * 3)
            self.returncode = 0

        def poll(self):
            return 0

        def kill(self):
            pass

        def wait(self, **kwargs):
            return 0

    monkeypatch.setattr(module.subprocess, 'Popen', lambda *args, **kwargs: Process())
    with pytest.raises(module.CollectionError, match='max-lines'):
        module.read_snapshot(container, '15m', max_lines=2)


def test_metadata_query_never_reads_container_environment(docker_collector, container, monkeypatch):
    module = docker_collector
    calls = []

    def output(args):
        calls.append(args)
        if args[0] == 'compose':
            return container['id']
        return '\n'.join(json.dumps(item) for item in [container['id'], '/my-container',
                            {'com.docker.compose.service': 'api', 'unwanted': 'do-not-store'}])

    monkeypatch.setattr(module, 'docker_output', output)
    result = module.inspect_container(service='api')
    assert result['id'] == container['id']
    assert 'unwanted' not in result
    assert 'Config.Env' not in repr(calls)
    with pytest.raises(module.CollectionError):
        module.inspect_container(container='--dangerous-option')


def test_key_loader_and_child_environment(docker_collector, tmp_path, monkeypatch):
    module = docker_collector
    monkeypatch.delenv('API_KEY', raising=False)
    path = tmp_path / '.env'
    path.write_text('POSTGRES_PASSWORD=not-needed\nAPI_KEY="file-key"\n', encoding='utf-8')
    assert module.api_key(path) == 'file-key'
    monkeypatch.setenv('API_KEY', 'environment-key')
    assert module.api_key(path) == 'environment-key'
    assert 'API_KEY' not in module.docker_environment()

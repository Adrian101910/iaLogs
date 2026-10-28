"""Collector delivery/checkpoint regressions; real HTTP is tested by http_smoke.py."""

import importlib.util
import io
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tomllib
from urllib.error import HTTPError, URLError

import pytest


@pytest.fixture
def collector(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "collector" / "tail.py"
    if not path.exists():
        path = Path("/collector/tail.py")
    spec = importlib.util.spec_from_file_location("ialogs_test_collector", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.delenv("IALOGS_URL", raising=False)
    return module


@pytest.fixture
def configuration(collector, tmp_path):
    # Exercise the checked-in example config rather than a separate test-only shape.
    with (Path(collector.__file__).parent / "example.toml").open("rb") as source:
        config = tomllib.load(source)
    config.update(file=str(tmp_path / "sample.log"), checkpoint=str(tmp_path / "checkpoint.json"),
                  url="http://127.0.0.1:18000", batch_size=2)
    return config


class Response(io.BytesIO):
    status = 201

    def __init__(self, count):
        super().__init__(json.dumps({"items": [{"id": str(i)} for i in range(count)]}).encode())


def capture_requests(monkeypatch, collector):
    batches = []

    def send(request, timeout):
        assert request.full_url == "http://127.0.0.1:18000/v1/logs"
        assert request.get_header("X-api-key") == "test-key-kept-out-of-config"
        assert timeout == 30
        events = json.loads(request.data)["events"]
        batches.append(events)
        return Response(len(events))

    monkeypatch.setattr(collector, "open_request", send)
    return batches


def test_example_config_chunking_checkpoint_restart_and_append(collector, configuration, monkeypatch):
    source = Path(configuration["file"])
    source.write_bytes("uno\ndos\nacentuación\ncuatro\ncinco\n".encode())
    batches = capture_requests(monkeypatch, collector)
    collector.collect(configuration, "test-key-kept-out-of-config", once=True)
    assert [len(batch) for batch in batches] == [2, 2, 1]
    assert [event["message"] for batch in batches for event in batch] == ["uno", "dos", "acentuación", "cuatro", "cinco"]
    state = json.loads(Path(configuration["checkpoint"]).read_text())
    assert state["offset"] == source.stat().st_size
    assert batches[0][0]["attributes"]["byte_offset"] == 0
    assert batches[0][1]["attributes"]["byte_offset"] == len("uno\n".encode())
    assert batches[0][0]["attributes"]["timestamp_kind"] == "collection_time"
    collector.collect(configuration, "test-key-kept-out-of-config", once=True)
    assert len(batches) == 3
    with source.open("ab") as target:
        target.write(b"seis\n")
    collector.collect(configuration, "test-key-kept-out-of-config", once=True)
    assert batches[-1][0]["message"] == "seis"
    assert sum(map(len, batches)) == 6


def test_partial_line_waits_for_newline_and_preserves_offset(collector, configuration, monkeypatch):
    source = Path(configuration["file"])
    source.write_bytes(b"complete\npartial")
    batches = capture_requests(monkeypatch, collector)
    collector.collect(configuration, "test-key-kept-out-of-config", once=True)
    assert [row["message"] for batch in batches for row in batch] == ["complete"]
    assert json.loads(Path(configuration["checkpoint"]).read_text())["offset"] == len(b"complete\n")
    with source.open("ab") as target:
        target.write(b" completed\n")
    collector.collect(configuration, "test-key-kept-out-of-config", once=True)
    assert batches[-1][0]["message"] == "partial completed"


@pytest.mark.parametrize("raw", [b"too-long\n", b"too-long"])
def test_oversize_line_never_advances_checkpoint(collector, configuration, monkeypatch, raw):
    configuration["max_line_bytes"] = 5
    Path(configuration["file"]).write_bytes(raw)
    batches = capture_requests(monkeypatch, collector)
    with pytest.raises(ValueError, match="larga"):
        collector.collect(configuration, "test-key-kept-out-of-config", once=True)
    assert not batches
    assert not Path(configuration["checkpoint"]).exists()


def test_exact_byte_boundary_crlf_and_blank_lines(collector, configuration, monkeypatch):
    configuration["max_line_bytes"] = 5
    Path(configuration["file"]).write_bytes(b"12345\r\n\n")
    batches = capture_requests(monkeypatch, collector)
    collector.collect(configuration, "test-key-kept-out-of-config", once=True)
    assert batches[0][0]["message"] == "12345"
    assert batches[0][1]["message"]


@pytest.mark.parametrize("status", [400, 401, 404, 413, 422, 429])
def test_http_4xx_does_not_retry_or_advance_existing_checkpoint(collector, configuration, monkeypatch, status):
    source = Path(configuration["file"])
    checkpoint = Path(configuration["checkpoint"])
    source.write_bytes(b"confirmed\n")
    capture_requests(monkeypatch, collector)
    collector.collect(configuration, "test-key-kept-out-of-config", once=True)
    old_state = checkpoint.read_bytes()
    with source.open("ab") as target:
        target.write(b"not confirmed\n")
    calls = []

    def reject(request, timeout):
        calls.append(request)
        raise HTTPError(request.full_url, status, "rejected", None, io.BytesIO())

    monkeypatch.setattr(collector, "open_request", reject)
    with pytest.raises(ValueError, match=str(status)):
        collector.collect(configuration, "test-key-kept-out-of-config", once=False)
    assert len(calls) == 1
    assert checkpoint.read_bytes() == old_state


@pytest.mark.parametrize("failure", ["http_503", "offline", "timeout"])
def test_transient_failure_retries_without_losing_events(collector, configuration, monkeypatch, failure):
    Path(configuration["file"]).write_bytes(b"retry this line\n")
    checkpoint = Path(configuration["checkpoint"])
    calls, sleeps = [], []

    class EndPolling(Exception):
        pass

    def send(request, timeout):
        calls.append(json.loads(request.data)["events"])
        if len(calls) == 1:
            assert not checkpoint.exists()
            if failure == "http_503":
                raise HTTPError(request.full_url, 503, "unavailable", None, io.BytesIO())
            if failure == "offline":
                raise URLError("connection refused")
            raise TimeoutError("timeout")
        return Response(len(calls[-1]))

    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 1:
            assert not checkpoint.exists()
        else:
            raise EndPolling

    monkeypatch.setattr(collector, "open_request", send)
    monkeypatch.setattr(collector.time, "sleep", sleep)
    with pytest.raises(EndPolling):
        collector.collect(configuration, "unused", once=False)
    assert len(calls) == 2
    assert calls[0][0]["message"] == calls[1][0]["message"] == "retry this line"
    assert calls[0][0]["attributes"] == calls[1][0]["attributes"]
    assert json.loads(checkpoint.read_text())["offset"] == len(b"retry this line\n")
    assert sleeps[0] == 1


def test_incomplete_api_acknowledgement_does_not_create_checkpoint(collector, configuration, monkeypatch):
    Path(configuration["file"]).write_bytes(b"not confirmed\n")
    monkeypatch.setattr(collector, "open_request", lambda *args, **kwargs: Response(0))
    with pytest.raises(ValueError, match="incompleta"):
        collector.collect(configuration, "unused", once=True)
    assert not Path(configuration["checkpoint"]).exists()


def test_invalid_utf8_is_rejected_without_advancing(collector, configuration, monkeypatch):
    Path(configuration["file"]).write_bytes(b"\xff\n")
    batches = capture_requests(monkeypatch, collector)
    with pytest.raises(UnicodeDecodeError):
        collector.collect(configuration, "test-key-kept-out-of-config", once=True)
    assert not batches
    assert not Path(configuration["checkpoint"]).exists()


@contextmanager
def redirect_servers(status):
    """Real loopback origins prove urllib cannot forward the API key."""
    source_calls, destination_calls = [], []

    class Destination(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def record(self):
            destination_calls.append(dict(self.headers))
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            body = b'{"items": []}'
            self.send_response(201)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = record
        do_POST = record

    destination = ThreadingHTTPServer(("127.0.0.1", 0), Destination)

    class Redirect(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            source_calls.append(dict(self.headers))
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            self.send_response(status)
            self.send_header("Location", f"http://127.0.0.1:{destination.server_port}/stolen-key")
            self.send_header("Content-Length", "0")
            self.end_headers()

    source = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    servers = [destination, source]
    threads = [threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
               for server in servers]
    for thread in threads:
        thread.start()
    try:
        yield f"http://127.0.0.1:{source.server_port}", source_calls, destination_calls
    finally:
        for server in reversed(servers):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=5)


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("sender", ["collector", "demo"])
def test_redirects_never_forward_api_key_to_another_origin(collector, configuration, monkeypatch, status, sender):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    key = "redirect-regression-key-must-never-be-forwarded"
    with redirect_servers(status) as (url, source_calls, destination_calls):
        if sender == "collector":
            configuration["url"] = url
            Path(configuration["file"]).write_bytes(b"synthetic redirect test\n")
            with pytest.raises(ValueError, match=str(status)) as failure:
                collector.collect(configuration, key, once=True)
            assert not Path(configuration["checkpoint"]).exists()
        else:
            path = Path(__file__).resolve().parents[2] / "scripts" / "send_demo.py"
            if not path.exists():
                path = Path("/scripts/send_demo.py")
            spec = importlib.util.spec_from_file_location("ialogs_test_send_demo", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with pytest.raises(SystemExit, match=str(status)) as failure:
                module.send(url, key, "/v1/logs", {"events": []})
        assert len(source_calls) == 1
        assert source_calls[0].get("X-Api-Key") == key or source_calls[0].get("X-api-key") == key
        assert not destination_calls
        assert key not in str(failure.value)

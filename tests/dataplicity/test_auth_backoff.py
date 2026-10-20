from __future__ import print_function
from __future__ import unicode_literals

import json

from dataplicity.auth_backoff import (
    AuthBackoffGate,
    _monotonic,
    compute_auth_backoff_seconds,
    is_auth_failure_exception,
    is_auth_failure_message,
    is_auth_failure_status,
    parse_retry_after,
)
from dataplicity import client as mclient
from dataplicity import jsonrpc
from dataplicity.m2mmanager import M2MManager


def test_is_auth_failure_status():
    assert is_auth_failure_status(401)
    assert is_auth_failure_status(403)
    assert is_auth_failure_status(404)
    assert not is_auth_failure_status(429)
    assert not is_auth_failure_status(500)
    assert not is_auth_failure_status(None)


def test_is_auth_failure_message():
    assert is_auth_failure_message("authorization failed")
    assert is_auth_failure_message("invalid credentials")
    assert is_auth_failure_message("unknown device")
    assert is_auth_failure_message("Authorization Failed")
    assert not is_auth_failure_message("internal error")
    assert not is_auth_failure_message(None)


def test_is_auth_failure_exception_jsonrpc():
    exc = jsonrpc.RemoteMethodError(
        "device.check_auth", -32602, None, "authorization failed"
    )
    assert is_auth_failure_exception(exc)
    other = jsonrpc.RemoteMethodError(
        "device.set_disk_space", -32602, None, "tag_list must be an array"
    )
    assert not is_auth_failure_exception(other)


def test_auth_failure_starts_at_long_backoff():
    gate = AuthBackoffGate()
    now = 1000.0
    delay = gate.record_auth_failure(now=now, jitter=False)
    assert delay == 300.0
    assert not gate.ready(now=now + 60)
    assert gate.ready(now=now + 300)


def test_auth_failure_honours_larger_retry_after():
    gate = AuthBackoffGate()
    now = 1000.0
    delay = gate.record_auth_failure(
        retry_after_header="900", now=now, jitter=False
    )
    assert delay == 900.0


def test_auth_failure_grows_to_one_hour_cap():
    assert compute_auth_backoff_seconds(1, jitter=False) == 300.0
    assert compute_auth_backoff_seconds(2, jitter=False) == 600.0
    assert compute_auth_backoff_seconds(5, jitter=False) == 3600.0
    assert compute_auth_backoff_seconds(10, jitter=False) == 3600.0


def test_parse_retry_after_seconds():
    assert parse_retry_after("120") == 120.0
    assert parse_retry_after(None) is None
    assert parse_retry_after("") is None


def test_set_m2m_identity_long_backoff_on_auth_failure(
    serial_file, auth_file, httpserver
):
    """Auth failure must floor at ~5m and skip lomond poll retries."""
    error_body = json.dumps(
        [
            {
                "jsonrpc": "2.0",
                "id": "authenticate_result",
                "error": {
                    "code": -32602,
                    "message": "authorization failed",
                },
            },
            {
                "jsonrpc": "2.0",
                "id": "associate_result",
                "error": {
                    "code": -32602,
                    "message": "authorization failed",
                },
            },
        ]
    )
    httpserver.serve_content(
        error_body, code=200, headers={"Content-Type": "application/json"}
    )

    client = mclient.Client(rpc_url=httpserver.url)
    assert client.set_m2m_identity(b"id-1") is None
    assert len(httpserver.requests) == 1
    remaining = client.auth_gate.next_mono - _monotonic()
    assert remaining >= 250.0

    manager = M2MManager(client, "ws://example", remote_directory=None)
    for _ in range(20):
        manager.set_identity(b"id-1")
    # Poll ticks must not hit the API again while gated.
    assert len(httpserver.requests) == 1
    assert manager.notified_identity is None


def test_sync_skips_while_auth_gated(serial_file, auth_file, httpserver, caplog):
    error_body = json.dumps(
        [
            {
                "jsonrpc": "2.0",
                "id": "authenticate_result",
                "error": {
                    "code": -32602,
                    "message": "invalid credentials",
                },
            }
        ]
    )
    httpserver.serve_content(
        error_body, code=200, headers={"Content-Type": "application/json"}
    )

    client = mclient.Client(rpc_url=httpserver.url)
    client.sync()
    assert len(httpserver.requests) == 1
    assert "long backoff" in caplog.text
    client.sync()
    assert len(httpserver.requests) == 1

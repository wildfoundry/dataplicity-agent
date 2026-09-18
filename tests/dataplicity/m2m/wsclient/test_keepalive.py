"""Regression tests for the m2m websocket keepalive path.

Two faults used to leave the agent connected-but-silent until the router
kicked it as unresponsive: a half-open socket that lomond never dropped,
and a blocking identity sync running on the websocket read thread.
"""

import threading
import time

import pytest
from mock import Mock, call

from dataplicity import constants
from dataplicity.m2m.wsclient import WSClient


# The router treats a device as unresponsive after this long without a pong.
ROUTER_UNRESPONSIVE_SECONDS = 270


class FakeEvent(object):
    """Stands in for a lomond event."""

    def __init__(self, name):
        self.name = name


def wait_for(predicate, timeout=5.0):
    """Poll until predicate is true, returning whether it became true."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


@pytest.fixture
def client():
    return WSClient(Mock(), "ws://example.invalid/m2m/", Mock())


@pytest.fixture
def identity_worker(client):
    """Run the identity sync worker for the duration of a test."""
    worker = threading.Thread(target=client._sync_identity_loop)
    worker.daemon = True
    worker.start()
    yield worker
    client._stop_identity_sync()
    worker.join(5)
    assert not worker.is_alive()


def test_persist_uses_a_ping_timeout(client, mocker):
    """Without a ping timeout lomond sits on a half-open socket forever."""
    persist = mocker.patch("dataplicity.m2m.wsclient.persist", return_value=iter([]))

    client.run()

    kwargs = persist.call_args[1]
    assert kwargs["ping_rate"] == constants.M2M_PING_RATE
    assert kwargs["ping_timeout"] == constants.M2M_PING_TIMEOUT
    assert kwargs["ping_rate"] < kwargs["ping_timeout"]
    # We have to give up and reconnect before the router kicks us.
    assert 0 < kwargs["ping_timeout"] < ROUTER_UNRESPONSIVE_SECONDS
    # Local reconnect wait — does not depend on server Retry-After.
    assert kwargs["min_wait"] == constants.M2M_RECONNECT_MIN_WAIT
    assert kwargs["max_wait"] == constants.M2M_RECONNECT_MAX_WAIT
    assert kwargs["min_wait"] < kwargs["max_wait"]


def test_unresponsive_event_is_logged(client, mocker):
    """Makes the half-open case identifiable in device logs when it recurs."""
    warning = mocker.patch("dataplicity.m2m.wsclient.log.warning")

    client.on_event(FakeEvent("unresponsive"))

    assert warning.called


def test_sync_identity_only_signals(client):
    """The notify is blocking HTTP, so it must not run on the read thread."""
    client.identity = b"identity"

    client.sync_identity()

    assert client.manager.set_identity.call_count == 0
    assert client._identity_sync_pending.is_set()


def test_identity_worker_notifies_manager(client, identity_worker):
    client.identity = b"identity"

    client.sync_identity()

    assert wait_for(lambda: client.manager.set_identity.called)
    assert client.manager.set_identity.call_args == call(b"identity")


def test_read_loop_survives_a_stuck_identity_sync(client, identity_worker):
    """The original hang: m2m.associate blocked, so no pongs were sent."""
    release = threading.Event()
    client.manager.set_identity.side_effect = lambda identity: release.wait(30)

    client.sync_identity()
    assert wait_for(lambda: client.manager.set_identity.called)

    try:
        started = time.time()
        for _ in range(50):
            client.on_event(FakeEvent("poll"))
        assert time.time() - started < 1.0
    finally:
        release.set()


def test_close_stops_the_identity_worker(client):
    """Teardown must release the worker even if closing the socket fails."""
    worker = threading.Thread(target=client._sync_identity_loop)
    worker.daemon = True
    worker.start()

    try:
        client.close()
    except Exception:
        # lomond raises when closing a socket that never connected.
        pass

    worker.join(5)
    assert not worker.is_alive()
    assert client.is_closed

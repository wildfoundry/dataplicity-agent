"""Reconnect back-off for the classic m2m client.

These waits are local and unconditional. Auth failures are HTTP 200 JSON-RPC
errors on existing agents, so we cannot rely on server Retry-After to throttle
them. Retry-After only lengthens a wait when the server already sends it.
"""

from mock import Mock

from dataplicity import constants
from dataplicity.m2m import persist as persist_mod
from dataplicity.m2mmanager import M2MManager


class FakeEvent(object):
    def __init__(self, name, response=None, reason=""):
        self.name = name
        self.response = response
        self.reason = reason


def test_persist_always_waits_locally_after_a_failed_connect():
    """A rejected upgrade still backs off even with no Retry-After header."""
    waits = []

    class FakeExit(object):
        def wait(self, timeout):
            waits.append(timeout)
            return True  # stop after first back-off

    def fake_connect(**kwargs):
        yield FakeEvent(
            "rejected",
            response=Mock(status_code=503, get=Mock(return_value=None)),
        )
        yield FakeEvent("disconnected")

    websocket = Mock()
    websocket.connect.side_effect = lambda **kwargs: fake_connect()

    list(
        persist_mod.persist(
            websocket,
            min_wait=5,
            max_wait=30,
            ping_rate=30,
            ping_timeout=120,
            exit_event=FakeExit(),
        )
    )

    assert len(waits) == 1
    assert waits[0] >= 1.0
    assert waits[0] <= 30


def test_persist_retry_after_only_raises_the_floor():
    """When Retry-After is already present, wait at least that long (capped)."""
    waits = []

    class FakeExit(object):
        def wait(self, timeout):
            waits.append(timeout)
            return True

    response = Mock(status_code=429)
    response.get.return_value = "45"

    def fake_connect(**kwargs):
        yield FakeEvent("rejected", response=response, reason="temporary backoff")
        yield FakeEvent("disconnected")

    websocket = Mock()
    websocket.connect.side_effect = lambda **kwargs: fake_connect()

    list(
        persist_mod.persist(
            websocket,
            min_wait=5,
            max_wait=120,
            ping_rate=30,
            ping_timeout=120,
            exit_event=FakeExit(),
        )
    )

    assert len(waits) == 1
    assert waits[0] >= 45
    assert waits[0] <= 120


def test_auth_failure_backs_off_before_retrying_associate():
    """check_auth failures are HTTP 200 RPC errors — wait locally, not on 429."""
    client = Mock()
    client.set_m2m_identity.return_value = None
    manager = M2MManager(client, "ws://example.invalid/m2m/", Mock())

    manager.set_identity(b"identity-1")
    assert client.set_m2m_identity.call_count == 1
    assert manager.notified_identity is None
    assert manager._identity_retry_after > 0

    manager.set_identity(b"identity-1")
    assert client.set_m2m_identity.call_count == 1  # still in back-off

    manager._identity_retry_after = 0.0
    client.set_m2m_identity.return_value = b"identity-1"
    manager.set_identity(b"identity-1")
    assert client.set_m2m_identity.call_count == 2
    assert manager.notified_identity == b"identity-1"


def test_persist_never_reconnects_immediately():
    """Even min_wait=0 must wait at least 1s — no busy-loop reconnects."""
    waits = []

    class FakeExit(object):
        def wait(self, timeout):
            waits.append(timeout)
            return True

    def fake_connect(**kwargs):
        yield FakeEvent("disconnected")

    websocket = Mock()
    websocket.connect.side_effect = lambda **kwargs: fake_connect()

    list(
        persist_mod.persist(
            websocket,
            min_wait=0,
            max_wait=0,
            ping_rate=30,
            ping_timeout=120,
            exit_event=FakeExit(),
        )
    )

    assert len(waits) == 1
    assert waits[0] >= 1.0


def test_auth_fail_backoff_constant_is_positive():
    assert constants.M2M_AUTH_FAIL_BACKOFF >= 5
    assert constants.M2M_RECONNECT_MAX_WAIT >= 1
    assert constants.M2M_RECONNECT_MIN_WAIT >= 1

"""API-side back-off after auth / associate failures.

Auth failures are HTTP 200 JSON-RPC errors on existing agents, so we throttle
retries locally on the API path rather than changing m2m websocket behaviour.
"""

from mock import Mock

from dataplicity import constants
from dataplicity.m2mmanager import M2MManager


def test_auth_failure_backs_off_before_retrying_associate():
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


def test_api_auth_fail_backoff_constant_is_positive():
    assert constants.API_AUTH_FAIL_BACKOFF >= 5
    assert constants.JSONRPC_RETRY_MIN_WAIT >= 1

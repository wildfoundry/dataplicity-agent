from json import dumps

import pytest
from dataplicity.jsonrpc import (JSONRPC, ErrorCode, InvalidResponseError,
                                 ProtocolError, RemoteError, RemoteMethodError,
                                 Batch)
import six


@pytest.fixture
def response():
    return {
        "jsonrpc": '2.0',
        "id": 2
    }


def test_call_id_increments(httpserver, response):
    """ test code for incrementation of message id
    """
    httpserver.serve_content(dumps(response))
    client = JSONRPC(httpserver.url)

    client.call('foo', bar='baz')
    assert client.call_id == 2


def test_jsonrpc_client_errors(httpserver, response):
    """ unit test for JSONRPC client code.
        uses pytest-localserver plugin
    """
    client = JSONRPC(httpserver.url)
    httpserver.serve_content("invalid-json")
    with pytest.raises(InvalidResponseError) as exc:
        client.call('foo')

    assert str(exc.value) == 'unable to decode response as JSON'

    response['jsonrpc'] = '1'
    httpserver.serve_content(dumps(response))

    with pytest.raises(ProtocolError) as exc:
        client.call('foo')

    assert str(exc.value) == 'Client only understands JSONRPC v2.0'

    del response['jsonrpc']
    httpserver.serve_content(dumps(response))

    with pytest.raises(ProtocolError) as exc:
        client.call('foo')

    assert str(exc.value) == 'Invalid response from server'


def test_that_id_in_response_must_match(httpserver, response):
    """ test code for matching id
    """
    response["id"] = 20

    httpserver.serve_content(dumps(response))
    client = JSONRPC(httpserver.url)

    with pytest.raises(ProtocolError) as exc:
        client.call("foo")

    assert str(exc.value) == "Invalid response from the server, 'id' field does not match"  # noqa


def test_remote_error(httpserver, response):
    """ test code for handling RemoteError / RemoteMethodError
    """
    response['error'] = {
        'code': ErrorCode.parse_error,
        'message': 'test-message'
    }

    httpserver.serve_content(dumps(response))
    client = JSONRPC(httpserver.url)

    with pytest.raises(RemoteError) as exc:
        client.call("foo")

    assert str(exc.value) == 'test-message'

    # imitate an error which is not a known RemoteError
    response['error']['code'] = 0
    httpserver.serve_content(dumps(response))
    client = JSONRPC(httpserver.url)

    with pytest.raises(RemoteMethodError) as exc:
        client.call("foo")

    assert str(exc.value) == 'test-message'


def test_notify(httpserver, response):
    """ call_id in the notify method should stay the same
    """
    httpserver.serve_content(dumps(response))
    client = JSONRPC(httpserver.url)

    client.notify("foo")
    assert client.call_id == 1


def test_batch_factory():
    client = JSONRPC(None)
    batch = client.batch()
    assert isinstance(batch, Batch)

    batch.call("foo")
    batch.call("bar")

    assert len(batch.calls) == 2


def test_abandon_call():
    client = JSONRPC(None)

    with Batch(client) as b:
        b.call("foo")
        b.abandon()


def test_send_batch_calls(httpserver, response):
    httpserver.serve_content(dumps(response))
    client = JSONRPC(httpserver.url)

    with pytest.raises(ProtocolError) as exc:
        with client.batch() as batch:
            batch = Batch(client)
            batch.call("foo")

    assert str(exc.value) == 'Expected a list of response from the server'

    response = [
        response,
        {'jsonrpc': '2.0', 'result': 'test-result', 'id': 3}
    ]
    httpserver.serve_content(dumps(response))
    client.call_id = 1

    with client.batch() as foo:
        foo.call("Foo")
        foo.call("FFF")

    assert foo.get_result(2) is None
    assert foo.get_result(3) == 'test-result'

    with pytest.raises(KeyError) as exc:
        foo.get_result(1111)

    expected_message = 'No such call_id in response'
    if six.PY2:
        assert str(exc.value.message) == expected_message
    elif six.PY3:
        assert exc.value.args[0] == expected_message

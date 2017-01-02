from json import dumps

import pytest
from dataplicity.jsonrpc import (JSONRPC, ErrorCode, InvalidResponseError,
                                 ProtocolError, RemoteError, RemoteMethodError)


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

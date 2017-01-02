from dataplicity.jsonrpc import JSONRPC


def test_jsonrpc(httpserver):
    """ unit test for JSONRPC client code.
        uses pytest-localserver plugin
    """
    httpserver.serve_content("""{"jsonrpc": "2.0", "id": 2}""")
    client = JSONRPC(httpserver.url)

    client.call('foo', bar='baz')

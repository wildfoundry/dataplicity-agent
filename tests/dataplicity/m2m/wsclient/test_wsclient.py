import threading
import time

from dataplicity.m2m.wsclient import WSClient
from websocket_server import wsserver_factory
from ws4py.websocket import EchoWebSocket

# this factory yields a fixture which we can use inside of testing functions.
# it runs a websocket server on a separate thread, and will shutdown once the
# test function returns.
wsserver = wsserver_factory(EchoWebSocket)


class WSClientThread(threading.Thread):
    """since the WSClient enters a forloop, there has to be a way to control
       its demise. A simple way of achieving it would be to use thread.
       we can send the commands (using client._server) and when we no longer
       need the client (i.e. at the end of the test method) we can do
       client.close()
    """
    def __init__(self, uri, *args, **kwargs):
        self._server = WSClient(uri, *args, **kwargs)
        super(WSClientThread, self).__init__(
            name=self.__class__,
            target=self._server.start
        )

    def close(self):
        self._server.close()


def test_wsclient(wsserver):
    """ this is a very basic proof that we can start and stop the builtin
        WSClient *and* wsserver
    """
    with WSClient(wsserver.uri, uuid='ident') as client:
        assert client.identity == 'ident'

    assert client.identity is None

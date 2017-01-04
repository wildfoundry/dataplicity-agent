import pytest
import threading
from SimpleWebsocketServer import SimpleWebSocketServer, WebSocket  # noqa


class WebsocketServer(threading.Thread):
    def __init__(self, handler_class, host='127.0.0.1', port=0, **kwargs):
        self._server = SimpleWebSocketServer(host, port, handler_class)
        super(WebsocketServer, self).__init__()

    @property
    def uri(self):
        return 'ws://{}'.format(self._server.serversocket.getsockname())

    def stop(self):
        self._server.finish = True

    def run(self):
        self._server.serveforever()


def wsserver_factory(server_handler_class):
    """ websocket server factory. Creates a pytest factory which can be
        later used in the tests.

        Usage:
        from websocket_server import wsserver_factory, WebSocket

        # echo server implementation.
        class MyServerHandler(WebSocket):
            def handleMessage(self):
                self.sendMessage(self.data)

        wsserver = wsserver_factory(MyServerHandler)

        def test_some_functionality(wsserver):
            # you can now access the wsserver uri, like so:
            print(wsserver.uri) # ws://localhost:some-port
    """
    @pytest.fixture
    def wsserver():
        server = WebsocketServer(server_handler_class, 'localhost', 0)
        server.start()
        yield server
        server.stop()

    return wsserver

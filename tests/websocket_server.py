import threading

import pytest
from ws4py.server.wsgirefserver import WebSocketWSGIRequestHandler, WSGIServer
from ws4py.server.wsgiutils import WebSocketWSGIApplication
from wsgiref.simple_server import make_server


class WebsocketServer(threading.Thread):
    """ Local websocket thread.
        This class will allow us to test websocket requests locally, without
        the need to mock any socket operations. It is a threading class, so
        that we would be able to start and stop the server.
    """
    def __init__(self, handler_class, host='127.0.0.1', port=0, **kwargs):
        self._server = make_server(
            host, port, server_class=WSGIServer,
            handler_class=WebSocketWSGIRequestHandler,
            app=WebSocketWSGIApplication(handler_cls=handler_class)
        )
        self._server.initialize_websockets_manager()
        super(WebsocketServer, self).__init__(
            name=self.__class__,
            target=self._server.serve_forever
        )

    @property
    def uri(self):
        return 'ws://{}:{}'.format(*self._server.server_address)

    def stop(self):
        self._server.shutdown()


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

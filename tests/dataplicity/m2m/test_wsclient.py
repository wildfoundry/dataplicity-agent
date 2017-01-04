from dataplicity.m2m.wsclient import WSClient
from websocket_server import wsserver_factory, WebSocket


class SimpleEcho(WebSocket):
    def handleMessage(self):
        # echo message back to client
        self.sendMessage(self.data)

    def handleConnected(self):
        print(self.address, 'connected')

    def handleClose(self):
        print(self.address, 'closed')


wsserver = wsserver_factory(SimpleEcho)


def test_wsclient(wsserver):
    print('===', wsserver.uri)

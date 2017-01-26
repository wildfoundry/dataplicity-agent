import pytest
from dataplicity.m2m.echoservice import EchoService
from dataplicity.m2m.wsclient import Channel


class TestClient(object):
    """ class used to simulate a real wsclient.
    """
    def channel_write(self, number, data):
        """ we need this function to inspect, whether the EchoService has
            passed the values back to the client
        """
        self.number = number
        self.data = data


def test_echoservice_client():
    """ unit test for EchoService class
    """
    # prepare a test channel.
    client = TestClient()
    channel = Channel(client, 123)

    service = EchoService(channel)

    data = b'\x01\x02'
    # try a succesful write:
    channel.on_data(data)
    # please note that because EchoService registers a callback in the
    # constructor, this means that a succesful call to channel.on_data will
    # in turn, call the code from the echoservice, which, in turn calls the
    # code from the same channel. Thanks to the fact that we have substituted
    # the client by our handy class (see above), and implemented a very simple
    # channel_write function, we can check, whether the values made it into
    # the client.
    assert channel.client.number == channel.number
    assert channel.client.data == data

    # however, when we delete the channel instance ...
    del channel
    # then on_data call within the echoservice should fail
    with pytest.raises(AttributeError):
        service.on_data(data)

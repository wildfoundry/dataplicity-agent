from dataplicity.m2m.wsclient import ChannelFile


class FakeClient(object):
    """ The ChannelFile class calls
        `self.client.channel_write` inside, therefore this simple class can
        act as a client representative.
    """
    def __init__(self):
        self.buffer = b''

    def channel_write(self, channel_no, data):
        self.buffer += data


def test_channelfile(capfd):
    """ test for ChannelFile class

        `capfd` is a fixture from pytest which replaces sys.stdout / stderr as
        a in-memory buffer, so that we would be able to read output from it.
    """
    channel_no = -100
    client = FakeClient()
    channel = ChannelFile(client, channel_no)

    assert channel.fileno() is None

    data = b"test-string 123"
    channel.write(data)

    assert client.buffer == data

    # channelfile outputs to sys.stdout, so let's check for that.
    out, err = capfd.readouterr()
    # of course, the readout from stdout will be a string, not bytes
    assert out == data.decode()
    # and there should be no errors.
    assert err == ''

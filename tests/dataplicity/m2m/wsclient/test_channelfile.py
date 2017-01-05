from dataplicity.m2m.wsclient import ChannelFile


class FakeClient(object):
    """ The ChannelFile class calls
        `self.client.channel_write` inside, therefore this simple class can
        act as a client representative.
    """
    def __init__(self):
        self.buffer = ''

    def channel_write(self, channel_no, data):
        self.buffer += data


def test_channelfile(capsys):
    """ test for ChannelFile class
    """
    channel_no = -100
    client = FakeClient()
    channel = ChannelFile(client, channel_no)

    assert channel.fileno() is None

    data = "test-string 123"
    channel.write(data)

    assert client.buffer == data

    # channelfile outputs to sys.stderr, so let's check for that.
    out, err = capsys.readouterr()
    assert out == data
    assert err == ''

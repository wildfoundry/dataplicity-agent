from dataplicity.m2m.wsclient import Channel
from mock import Mock
import logging


def test_channel_repr():
    """ unit test for Channel class
    """
    c = Channel(None, 123)
    assert repr(c) == '<channel 123>'


def test_channel_close(caplog, mocker):
    """ unit tests for closing functionality
    """
    class TestClient(object):
        """ the actual channel talks to the client. However, since we're tsting
            just the channel functionality here, we want to make sure only that
            certain functions get called. Therefore this fake Client class will
            do
        """
        def close_channel(self, number):
            pass

    def close_callback_which_raises_error():
        raise ValueError('Intentional')

    mock_close_callback = Mock()
    client = TestClient()
    chan = Channel(client, 123)

    assert chan.is_closed is False
    mocker.spy(client, 'close_channel')
    chan.close()
    # make sure that the client function was called
    assert client.close_channel.call_count == 1

    # we set the _closed attribute to True, and now the function shouldn't be
    # called...
    chan._closed = True
    chan.close()
    # ... leaving the call_count at 1
    assert client.close_channel.call_count == 1
    chan._closed = False

    chan.set_callbacks(on_close=mock_close_callback)
    chan.on_close()
    # ok, here's what should have happened.
    # 1. chan._closed should be set to True
    assert chan._closed is True
    # 2. close callback should have ben called
    assert mock_close_callback.call_count == 1
    # now, when we try to call close() for the second time, it should quickly
    # return, without hitting the callback
    chan.on_close()
    assert mock_close_callback.call_count == 1

    # ok, now for something completely different.
    chan.set_callbacks(on_close=close_callback_which_raises_error)
    chan._closed = False
    num_log_entries = len(caplog.records)
    chan.on_close()
    # make sure that log.exception was called
    assert len(caplog.records) == num_log_entries + 1
    assert caplog.records[-1].msg == 'error in close callback'
    assert caplog.records[-1].levelno == logging.ERROR

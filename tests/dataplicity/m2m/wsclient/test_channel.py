from dataplicity.m2m.wsclient import Channel
from mock import Mock, call
import logging
import pytest


class TestClient(object):
    """ the actual channel talks to the client. However, since we're testing
        just the channel functionality here, we want to make sure only that
        certain functions get called. Therefore this fake Client class will
        do
    """
    def close_channel(self, number):
        pass


@pytest.fixture
def channel():
    client = TestClient()
    return Channel(client, 123)


def test_channel_repr():
    """ unit test for Channel class
    """
    c = Channel(None, 123)
    assert repr(c) == '<channel 123>'


def test_channel_close(caplog, mocker, channel):
    """ unit tests for closing functionality
    """

    def close_callback_which_raises_error():
        raise ValueError('Intentional')

    mock_close_callback = Mock()
    chan = channel
    client = chan.client

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


def test_channel_on_data(caplog, channel):
    """ unit test for Channel::on_data
    """
    chan = channel
    chan._closed = True
    num_log_entries = len(caplog.records)
    # the function should break early
    data = b'\x01\x02\x03'
    chan.on_data(data)
    assert len(caplog.records) == num_log_entries + 1
    chan._closed = False

    data = b'\x01\x02\x03'
    mock_data_callback = Mock()
    chan.set_callbacks(on_data=mock_data_callback)
    chan.on_data(data)
    assert mock_data_callback.called

    chan.set_callbacks(on_data=None)
    # this returns true only when data_event is set.
    assert bool(chan) is False
    assert chan.deque.count(data) == 0
    chan.on_data(data)
    # data_even should be set, because there was no callback registered to
    # handle on_data event
    assert bool(chan) is True
    assert chan.deque.count(data) == 1
    assert chan.size == 3


def test_channel_on_control_with_closed_channel(caplog, channel):
    chan = channel
    chan.on_close()
    num_log_entries = len(caplog.records)
    chan.on_control(b'\x01\x02\x03')
    assert len(caplog.records) == num_log_entries + 1
    assert caplog.records[-1].message == '3 bytes from closed <channel 123> ignored'  # noqa
    assert caplog.records[-1].levelno == logging.DEBUG


def test_channel_on_control_with_callback(channel, mocker):
    def control_callback(data):
        pass

    channel.set_callbacks(on_control=control_callback)
    mocker.spy(channel, '_control_callback')

    data = b'\x01\x02\x03'
    channel.on_control(data)

    assert channel._control_callback.call_count == 1
    print(type(channel._control_callback.call_args))
    assert channel._control_callback.call_args == call(data)

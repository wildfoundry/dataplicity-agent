import logging

import pytest
import six
from dataplicity.m2m.wsclient import Channel, ChannelFile
from mock import Mock, call


class TestClient(object):
    """ the actual channel talks to the client. However, since we're testing
        just the channel functionality here, we want to make sure only that
        certain functions get called. Therefore this fake Client class will
        do
    """
    def close_channel(self, number):
        """ empty implementation of close_channel function. We only care about
            call args, but the function has to exist, in order for us to
            get this property
        """
        pass

    def channel_write(self, number, data):
        """ please refer to docstring of close_channel
        """
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


def test_channel_close(channel, mocker):
    """ unit tests for closing functionality
    """
    assert channel.is_closed is False
    mocker.spy(channel.client, 'close_channel')
    channel.close()
    # make sure that the client function was called
    assert channel.client.close_channel.call_count == 1


def test_client_close_isnt_called_when_channel_is_closed(mocker, channel):
    assert channel.is_closed is False
    channel.on_close()
    assert channel.is_closed is True
    mocker.spy(channel.client, 'close_channel')
    channel.close()
    # make sure that the client function was not called
    assert channel.client.close_channel.call_count == 0


def test_channel_calls_callback_on_close(mocker, channel):
    mock_close_callback = Mock()
    channel.set_callbacks(on_close=mock_close_callback)
    channel.on_close()
    # ok, here's what should have happened.
    # 1. chan._closed should be set to True
    assert channel.is_closed is True
    # 2. close callback should have ben called
    assert mock_close_callback.call_count == 1
    # now, when we try to call close() for the second time, it should quickly
    # return, without hitting the callback
    channel.on_close()
    assert mock_close_callback.call_count == 1

def test_channel_logs_exception_on_close(caplog, mocker, channel):
    capture_log = caplog

    def close_callback_which_raises_error():
        raise ValueError('Intentional')

    channel.set_callbacks(on_close=close_callback_which_raises_error)

    num_log_entries = len(capture_log.records)
    channel.on_close()
    # make sure that log.exception was called
    assert len(capture_log.records) == num_log_entries + 1
    assert capture_log.records[-1].msg == 'error in close callback'
    assert capture_log.records[-1].levelno == logging.ERROR


def test_channel_on_data(caplog, channel):
    """ unit test for Channel::on_data
    """
    # Set the logger level to capture debug messages
    caplog.set_level(logging.DEBUG)

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
    """ this unit test covers the code which is launched when there is an
        attempt to use the on_control function, but the channel has been closed
    """
    # Set the logger level to capture debug messages
    caplog.set_level(logging.DEBUG)

    chan = channel
    chan.on_close()
    num_log_entries = len(caplog.records)
    chan.on_control(b'\x01\x02\x03')
    assert len(caplog.records) == num_log_entries + 1
    assert caplog.records[-1].message == '3 bytes from closed <channel 123> ignored'  # noqa
    assert caplog.records[-1].levelno == logging.DEBUG


def test_channel_on_control_with_callback(channel, mocker):
    """ unit test for 'on_control'
    """
    def control_callback(data):
        """ method which imitates a control callback
        """
        pass

    channel.set_callbacks(on_control=control_callback)
    mocker.spy(channel, '_control_callback')

    data = b'\x01\x02\x03'
    channel.on_control(data)

    assert channel._control_callback.call_count == 1
    assert channel._control_callback.call_args == call(data)


def test_channel_get_file(channel):
    """ unit test for channel::get_file
    """
    assert isinstance(channel.get_file(), ChannelFile)


def test_channel_read_returns_empty_data_if_block_timeouts(channel):
    """ let's try to test if we tell to read 2 bytes, but don't actually send
        anything, the function returns empty data.
    """
    assert channel.read(count=1, timeout=1, block=True) == six.b('')


def test_channel_read(channel):
    """ unit test for reading from channel
    """

    # data to be sent to channel.
    data = b'\x01\x02\x03\x04\x05\x06\x07'
    # write the data
    channel.on_data(data)

    # let's read only 6 bytes from the channel.
    assert channel.read(count=6) == data[:-1]
    # now we should be able to read 1 remaining byte
    # note: -1: is by all means not accidental. It is true, that there will be
    # no other byte available apart from the last one (-1), however we want to
    # interpret the output as a binary string, and omitting the colon (and thus
    # leaving just data[-1]) would yield 7 (as a number, not binary string)
    assert channel.read(count=1) == data[-1:]
    # the subsequential reads should yield empty data:
    assert channel.read(1) == b''


def test_channel_write(channel, mocker):
    """ test code for channel::write
    """
    with pytest.raises(Exception) as e:
        channel.write(six.u("abcde"))

    assert str(e.value) == "data must be bytes"

    # check that client was called in order to write the data.
    mocker.spy(channel.client, 'channel_write')
    data = b'\x01\x02'
    channel.write(data)
    assert channel.client.channel_write.call_args == call(
        channel.number, data)

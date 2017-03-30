from __future__ import print_function
from __future__ import unicode_literals

import logging
import socket
import ssl
import sys
import threading
import time
from collections import defaultdict, deque

from ws4py.client.threadedclient import WebSocketClient

from . import bencode
from . import packets
from ..compat import text_type
from .dispatcher import Dispatcher, expose
from .packets import M2MPacket as Packet
from .packets import PacketType
from .. import constants


log = logging.getLogger('m2m')


class ClientError(Exception):
    pass


class ChannelFile(object):
    """Mimicks a writable file."""

    def __init__(self, client, channel_no):
        self.client = client
        self.channel_no = channel_no

    def write(self, data):
        # http://stackoverflow.com/questions/23932332/writing-bytes-to-standard-output-in-a-way-compatible-with-both-python2-and-pyth
        # retrieve stdout as a binary file object
        output = getattr(sys.stdout, 'buffer', sys.stdout)
        output.write(data)
        self.client.channel_write(self.channel_no, data)

    def fileno(self):
        return None


class Channel(object):
    """An interface to a channel."""

    def __init__(self, client, number):
        self.client = client
        self.number = number
        self._closed = False

        self._data_callback = None
        self._close_callback = None
        self._control_callback = None
        self._lock = threading.RLock()
        self.deque = deque()
        self._data_event = threading.Event()

    def __repr__(self):
        """Show the channel number."""
        return "<channel {}>".format(self.number)

    def close(self):
        """Call to *request* a close."""
        if not self._closed:
            self.client.close_channel(self.number)

    def on_close(self):
        """Called when the notify_close packet is received."""
        if self._closed:
            return
        self._closed = True
        try:
            if self._close_callback is not None:
                self._close_callback()
        except:
            log.exception('error in close callback')

    @property
    def is_closed(self):
        return self._closed

    def on_data(self, data):
        """On incoming data."""
        if self._closed:
            log.debug('%s bytes from closed %r ignored', len(data), self)
            return
        if self._data_callback is not None:
            self._data_callback(data)
        else:
            with self._lock:
                self.deque.append(data)
                self._data_event.set()

    def on_control(self, data):
        """On control data."""
        if self._closed:
            log.debug('%s bytes from closed %r ignored', len(data), self)
            return
        if self._control_callback is not None:
            self._control_callback(data)

    def set_callbacks(self, on_data=None, on_close=None, on_control=None):
        self._data_callback = on_data
        self._close_callback = on_close
        self._control_callback = on_control

    @property
    def size(self):
        with self._lock:
            return sum(len(b) for b in self.deque)

    def __nonzero__(self):
        return self._data_event.is_set()

    def __bool__(self):
        return self.__nonzero__()

    def read(self, count, timeout=None, block=False):
        """Read up to `count` bytes."""
        incoming_bytes = []
        bytes_remaining = count

        # Block until data
        if block:
            if not self._data_event.wait(timeout):
                return b''

        with self._lock:
            # Data may be spread across multiple / partial messages
            while self.deque and bytes_remaining:
                head = self.deque[0]
                read_bytes = min(bytes_remaining, len(head))
                incoming_bytes.append(head[:read_bytes])
                bytes_left = head[read_bytes:]
                bytes_remaining -= read_bytes
                if not bytes_left:
                    self.deque.popleft()
                else:
                    self.deque[0] = bytes_left
            if not self.deque:
                self._data_event.clear()

        return b''.join(incoming_bytes)

    def write(self, data):
        assert isinstance(data, bytes), "data must be bytes"
        with self._lock:
            self.client.channel_write(self.number, data)

    def get_file(self):
        return ChannelFile(self.client, self.number)


class WSApp(WebSocketClient):
    """Wrapper around ws4py interface for WSClient."""

    def __init__(self, url, on_open, on_message, on_error, on_close):
        self.on_open = on_open
        self.on_message = on_message
        self.on_error = on_error
        self.on_close = on_close
        super(WSApp, self).__init__(url)
        self.sock.settimeout(10.0)

    def connect(self):
        """Connect the WS, call on_error callback."""
        try:
            super(WSApp, self).connect()
        except Exception as error:
            self.on_error(self, error)

    def close(self, code=1000, reason=''):
        """Close the WS, log errors."""
        try:
            super(WSApp, self).close(code=code, reason=reason)
        except Exception as error:
            log.debug('WSApp.close %s', error)

    def opened(self):
        """Call on_open callback, log errors."""
        try:
            self.on_open(self)
        except Exception as error:
            log.error('WSApp.on_open: %s', error)

    def received_message(self, message):
        """Call on_message with binary packets."""
        try:
            self.on_message(self, message)
        except Exception as error:
            log.error('WSApp.received_message: %s', error)

    def closed(self, code, reason=None):
        """Call on_close method, log errors."""
        try:
            self.on_close(self)
        except Exception as error:
            log.error('WSApp.closed: %s', error)

    def unhandled_error(self, error):
        """Called by ws4py when there is an error in run_forever."""
        # ws4py calls this with any socket errors
        # Doesn't matter what the socket error is; connection is fubar.
        log.error('error in WSApp: %s', error)
        # Can't terminate here
        # Trick the server in to exiting
        self.server_terminated = True

        try:
            self.on_close(self)
        except Exception as close_error:
            log.error('WSApp.unhandler_error on_close: %s', close_error)

    def close_connection(self):
        """Close WS connection."""
        # Implement close_connection in order to invoke on_close
        # when the heartbeat thread fails.
        log.debug('close_connection called')
        try:
            super(WSApp, self).close_connection()
        finally:
            try:
                self.on_close(self)
            except Exception as error:
                log.error('WSApp.close_connection on_close: %s', error)


class WSClient(Dispatcher):
    """Interface to the M2M server."""

    def __init__(self, url, uuid=None,
                 channel_callback=None, control_callback=None, **kwargs):
        self.url = url
        self.channel_callback = channel_callback
        self.control_callback = control_callback
        self.app = WSApp(
            url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

        self._closed = False
        self.identity = uuid
        self.channels = {}
        self.last_packet_time = time.time()

        self.callback_lock = threading.RLock()
        self.write_lock = threading.Lock()
        self.ready_event = threading.Event()
        self.close_event = threading.Event()
        self.callbacks = defaultdict(list)
        self.hooks = defaultdict(list)
        self._abandoned = False

        self.name = "m2m"  # Thread name
        self.daemon = True

        super(WSClient, self).__init__(Packet, log=log)


    def __repr__(self):
        """Return the URL."""
        return 'WSClient({!r})'.format(self.url)

    def __enter__(self):
        """Wait until the client is connected and ready."""
        self.wait_ready()
        return self

    def __exit__(self, *args, **kwargs):
        """Auto close the client."""
        if not self.close_event.is_set():
            self.close()

    @property
    def is_closed(self):
        return self._closed

    @property
    def is_ready(self):
        return self.ready_event.is_set()

    @property
    def open_channels(self):
        """List of open channels."""
        return self.channels.keys()

    @property
    def time_since_last_packet(self):
        """Time, in seconds, since the last packet."""
        return time.time() - self.last_packet_time

    @property
    def is_responding(self):
        """Check the server is still responding."""
        if self.is_closed:
            return False
        if constants.MAX_TIME_SINCE_LAST_PACKET is None:
            return True
        return self.time_since_last_packet < constants.MAX_TIME_SINCE_LAST_PACKET

    def connect(self, wait=True, timeout=None):
        """Connect and optionally wait until we are ready to communicate with the server."""
        self.app.connect()
        if wait:
            return self.wait_ready(timeout=timeout)
        return None

    def abandon(self):
        """Stop all processing due to connection drop."""
        log.debug('WSClient.abandon')
        self._abandoned = True
        self._closed = True
        self.identity = None
        self.close_event.set()
        self.ready_event.set()
        self.clear_callbacks()

    def add_callback(self, command_id, callback):
        self.callbacks[command_id].append(callback)

    def callback(self, command_id, result):
        with self.callback_lock:
            if command_id in self.callbacks:
                for callback in self.callbacks[command_id]:
                    try:
                        callback(result)
                    except:
                        log.exception('error in command callback')
                del self.callbacks[command_id]

    def clear_callbacks(self):
        """Clear all callbacks, because they may be blocking."""
        with self.callback_lock:
            for command_id, callbacks in self.callbacks.items():
                for callback in callbacks:
                    try:
                        callback(None)
                    except:
                        log.exception('error clearing callback')

    def get_channel(self, channel_no):
        # TODO: Create channels in response to packets
        if channel_no not in self.channels:
            self.channels[channel_no] = Channel(self, channel_no)
        return self.channels[channel_no]

    def has_channel(self, channel_no):
        return channel_no in self.channels

    def close_channel(self, channel_no):
        log.debug("request close")
        self.send('request_close', port=channel_no)

    def hard_close_channels(self):
        """Called when all the channels have been abruptly closed."""
        for channel in self.channels.values():
            channel.on_close()

    def run(self):
        sockopt = [(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)]
        try:
            self.app.run_forever(
                ssl_options={"cert_reqs": ssl.CERT_NONE}
            )
        except (SystemExit, KeyboardInterrupt):
            log.info('wsclient exit requested')
        except:
            log.exception('unable to initialise websocket')

        self.identity = None
        self.ready_event.set()
        try:
            self.app.close()
        except:
            log.exception('error closing app')

    def close(self, timeout=5):
        if not self._closed and self.ready_event.is_set():
            self.send(PacketType.request_leave)
            if timeout:
                self.close_event.wait(timeout)
            self.clear_callbacks()
        self._closed = True
        self.identity = None
        self.ready_event.set()
        self.app.close()

    def wait_ready(self, timeout=10):
        """Wait until the server is ready, and return identity."""
        # Q. What are we waiting for?
        # A. Establishing a m2m connection, and for the server to send us an identity.
        self.ready_event.wait(timeout)
        return self.identity

    def terminate(self):
        """Terminate the websocket."""
        try:
            # Trick ws4py in to exiting its loop
            self.app.server_terminated = True
        except:
            log.exception('error in terminate %s')

    def send(self, packet, *args, **kwargs):
        """Send a packet. Will encode if necessary."""
        if isinstance(packet, (bytes, text_type)):
            packet = PacketType[packet].value
        if isinstance(packet, (PacketType, int)):
            packet = Packet.create(packet, *args, **kwargs)
        if not getattr(packet, 'no_log', False):
            log.debug("sending %r", packet)

        packet_bytes = packet.encode_binary()
        self.send_bytes(packet_bytes)

    def send_bytes(self, packet_bytes):
        """Send bytes over the websocket."""
        with self.write_lock:
            if self.app.client_terminated:
                log.debug('send_bytes ignored')
                return False
            else:
                try:
                    self.app.send(packet_bytes, binary=True)
                except:
                    log.exception('error in send_bytes')
                    self.terminate()
                return True

    def on_open(self, app):
        """Called when WS is opened."""
        log.debug("websocket opened")
        if not self.is_closed:
            if self.identity is None:
                self.send(PacketType.request_join)
            else:
                self.send(PacketType.request_identify, uuid=self.identity)

    def on_message(self, app, message):
        """On a WS message."""
        log.debug('received ws message %r', message)
        self.last_packet_time = time.time()
        if message.is_binary:
            data = message.data
            try:
                packet = bencode.decode(data)
            except:
                log.exception('packet could not be decoded')
            else:
                self.on_packet(packet)

    def on_error(self, app, error):
        """Called on WS error."""
        if error:
            log.error("websocket error %r", error)
        self._closed = True
        self.identity = None
        self.close_event.set()
        self.ready_event.set()
        self.hard_close_channels()
        self.clear_callbacks()
        try:
            # Not entirely sure if this is necessary
            self.app.close()
        except:
            log.exception('error closing ws app in on_error')

    def on_close(self, app):
        """Called by WS app when socket closes."""
        log.debug('on_close... connection closed by peer')
        self._closed = True
        self.identity = None
        self.close_event.set()
        self.ready_event.set()
        self.clear_callbacks()

    def on_packet(self, packet):
        """Called with a binary packet."""
        try:
            packet_type = packets.PacketType(packet[0])
            packet_body = packet[1:]
        except:
            log.exception('packet is badly formatted')
        else:
            self.dispatch(packet_type, packet_body)

    def channel_write(self, channel, data):
        """Write data to a virtual channel."""
        self.send(PacketType.request_send, channel=channel, data=data)

    def on_instruction(self, sender, data):
        """Called with an instruction."""
        log.debug('instruction from {%s} %r', sender, data)

    # --------------------------------------------------------
    # Packet handlers
    # -------------------------------------------------------

    @expose(PacketType.null)
    def handle_null(self, packet_type):
        """Ignore null packet."""
        # Null packets may be sent just to check the connection

    @expose(PacketType.set_identity)
    def handle_set_identity(self, packet_type, identity):
        """Server is telling us about our identity."""
        if not self.is_closed:
            self.identity = identity
            log.debug('setting identity to %s', self.identity)

    @expose(PacketType.ping)
    def handle_ping(self, packet_type, data):
        """Ping send from the server, send back a pong with the same data."""
        self.send('pong', data=data[:1024])

    @expose(PacketType.welcome)
    def handle_welcome(self, packet_type):
        """Welcome packet means we can start talking to the m2m server."""
        self.ready_event.set()

    @expose(PacketType.log)
    def handle_log(self, packet_type, msg):
        """The server has sent a message for us to write to the logs."""
        log.debug(msg)

    @expose(PacketType.route)
    def handle_route(self, packet_type, channel, data):
        """Route packet containing data to write to a 'channel'."""
        channel = self.get_channel(channel)
        if self.channel_callback is not None:
            try:
                self.channel_callback(channel, data)
            except:
                log.exception('error in channel callback')
        channel.on_data(data)

    @expose(PacketType.route_control)
    def handle_route_control(self, packet_type, channel, data):
        """A control packet is out of band data associated with an existing channel."""
        channel = self.get_channel(channel)
        if self.control_callback is not None:
            try:
                self.control_callback(channel, data)
            except:
                log.exception('error in channel callback')
        channel.on_control(data)

    @expose(PacketType.notify_open)
    def on_notify_open(self, packet_type, channel_no):
        """The server has told us of a new channel."""
        channel = self.get_channel(channel_no)
        log.debug('%s opened', channel)

    @expose(PacketType.notify_close)
    def on_notify_close(self, packet_type, channel_no):
        """The server has told us of a channel being closed."""
        log.debug('%s closed', channel_no)
        if self.has_channel(channel_no):
            channel = self.get_channel(channel_no)
            channel.on_close()
            del self.channels[channel_no]

    @expose(PacketType.notify_login_success)
    def on_login_success(self, packet_type, user):
        """Logged in users have special privileges (typically not needed by dpcore clients)."""
        self.user = user
        log.debug('logged in as %s', user)

    @expose(PacketType.response)
    def on_response(self, packet_type, command_id, result):
        """We have received a response to a command."""
        self.callback(command_id, result)

    @expose(PacketType.instruction)
    def on_instruction_packet(self, packet_type, sender, data):
        """An instruction packet contains application specific data."""
        try:
            self.on_instruction(sender, data)
        except:
            log.exception('error handling instruction')

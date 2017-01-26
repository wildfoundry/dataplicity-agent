from __future__ import print_function
from __future__ import unicode_literals

import logging
import socket
import ssl
import sys
import threading
from collections import defaultdict, deque

import websocket

from . import bencode
from . import packets
from ..compat import text_type
from .dispatcher import Dispatcher, expose
from .packets import M2MPacket as Packet
from .packets import PacketType

log = logging.getLogger('m2m')
server_log = logging.getLogger('m2m.server')


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


class ThreadedDispatcher(threading.Thread, Dispatcher):
    """Dispatches packets from a thread."""

    def __init__(self, **kwargs):
        # Why didn't super work here?
        # Because threading.Thread doesn't call super
        threading.Thread.__init__(self)
        Dispatcher.__init__(self, Packet, log=kwargs.get('log'))


class WSClient(ThreadedDispatcher):
    """Interface to the M2M server."""

    def __init__(self, url, uuid=None, log=None,
                 channel_callback=None, control_callback=None, **kwargs):
        self.url = url
        self.channel_callback = channel_callback
        self.control_callback = control_callback
        kwargs['on_open'] = self.on_open
        kwargs['on_message'] = self.on_message
        kwargs['on_error'] = self.on_error
        kwargs['on_close'] = self.on_close
        self.kwargs = kwargs

        self._closed = False
        self.identity = uuid
        self.channels = {}

        self.callback_lock = threading.RLock()
        self.write_lock = threading.Lock()
        self.ready_event = threading.Event()
        self.close_event = threading.Event()
        self.callbacks = defaultdict(list)
        self.hooks = defaultdict(list)

        super(WSClient, self).__init__(log=log)
        self.name = "m2m"  # Thread name
        self.daemon = True

        self.app = websocket.WebSocketApp(self.url,
                                          **self.kwargs)

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

    def connect(self, wait=True, timeout=None):
        """Connect and optionally wait until we are ready to communicate with the server."""
        self.start()
        if wait:
            return self.wait_ready(timeout=timeout)
        return None

    def add_callback(self, command_id, callback):
        self.callbacks[command_id].append(callback)

    def callback(self, command_id, result):
        with self.callback_lock:
            if command_id in self.callbacks:
                for callback in self.callbacks[command_id]:
                    try:
                        callback(result)
                    except:
                        self.exception('error in command callback')
                del self.callbacks[command_id]

    def clear_callbacks(self):
        """Clear all callbacks, because they may be blocking."""
        with self.callback_lock:
            for command_id, callbacks in self.callbacks.items():
                for callback in callbacks:
                    try:
                        callback(None)
                    except:
                        self.exception('error clearing callback')

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
            self.app.run_forever(sockopt=sockopt,
                                 ping_interval=30,
                                 ping_timeout=10,
                                 sslopt={"cert_reqs": ssl.CERT_NONE})
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
            self.app.sock.send_binary(packet_bytes)

    def on_open(self, app):
        """Called when WS is opened."""
        log.debug("websocket opened")
        if not self.is_closed:
            if self.identity is None:
                self.send(PacketType.request_join)
            else:
                self.send(PacketType.request_identify, uuid=self.identity)

    def on_message(self, app, data):
        """On a WS message."""
        try:
            packet = bencode.decode(data)
        except:
            log.exception('packet could not be decoded')
        else:
            self.on_packet(packet)

    def on_error(self, app, error):
        """Called on WS error."""
        if error:
            self.log.error("websocket error %r", error)
        self._closed = True
        self.identity = None
        self.close_event.set()
        self.ready_event.set()
        self.hard_close_channels()
        self.clear_callbacks()
        try:
            # Not entirely sure if this is neccesary
            self.app.close()
        except:
            log.exception('error closing ws app in on_error')

    def on_close(self, app):
        """Called by WS app when socket closes."""
        self.log.debug('connection closed by peer')
        self._closed = True
        self.identity = None
        self.close_event.set()
        self.ready_event.set()
        self.clear_callbacks()

    def on_packet(self, packet):
        try:
            packet_type = packets.PacketType(packet[0])
            packet_body = packet[1:]
        except:
            log.exception('packet is badly formatted')
        else:
            self.dispatch(packet_type, packet_body)

    def channel_write(self, channel, data):
        self.send(PacketType.request_send, channel=channel, data=data)

    def on_instruction(self, sender, data):
        self.log.debug('instruction from {%s} %r', sender, data)

    # --------------------------------------------------------
    # Packet handlers
    # -------------------------------------------------------

    @expose(PacketType.set_identity)
    def handle_set_identity(self, packet_type, identity):
        """Server is telling us about our identity."""
        if not self.is_closed:
            self.identity = identity
            self.log.debug('setting identity to %s', self.identity)

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
        server_log.info(msg)

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

from __future__ import print_function
from __future__ import unicode_literals

import json
import logging
import sys
import threading
import time
from collections import defaultdict, deque

from lomond import WebSocket
from lomond.constants import USER_AGENT as LOMOND_USER_AGENT
from lomond.persist import persist
from lomond.errors import WebSocketError

from . import bencode
from . import packets
from ..compat import text_type
from .dispatcher import Dispatcher, expose
from .packets import M2MPacket as Packet
from .packets import PacketType
from .._version import __version__


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
        if not self.is_closed:
            with self._lock:
                self.client.channel_write(self.number, data)

    def send_control(self, control):
        """Write a control packet."""
        if not self.is_closed:
            with self._lock:
                self.client.channel_control_write(self.number, control)

    def get_file(self):
        return ChannelFile(self.client, self.number)


class WSClient(threading.Thread):
    """Interface to the M2M server."""

    def __init__(self, manager, url, uuid=None,
                 channel_callback=None, control_callback=None,
                 **kwargs):
        super(WSClient, self).__init__()
        self.manager = manager
        self.url = url
        _user_agent = "Agent/{} {}".format(
            __version__,
            LOMOND_USER_AGENT
        )
        self.websocket = WebSocket(url, agent=_user_agent)
        self.channel_callback = channel_callback
        self.control_callback = control_callback

        self._closed = False
        self.identity = uuid
        self.channels = {}
        self.last_packet_time = time.time()

        self.callback_lock = threading.RLock()
        self.write_lock = threading.Lock()
        self.callbacks = defaultdict(list)
        self.hooks = defaultdict(list)

        self.dispatcher = Dispatcher(
            packet_cls=Packet,
            handler_instance=self,
            log=log
        )

        self.name = "m2m"  # Thread name
        self.daemon = True

    def __repr__(self):
        """Return the URL."""
        return 'WSClient({!r})'.format(self.url)

    @property
    def is_closed(self):
        return self._closed

    @property
    def open_channels(self):
        """List of open channels."""
        return self.channels.keys()

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
        """Main websocket handling loop."""
        try:
            with self.websocket:
                for event in persist(self.websocket):
                    log.debug('WS %r', event)
                    try:
                        self.on_event(event)
                    except Exception as error:
                        log.exception('error handling websocket event')
        except (SystemExit, KeyboardInterrupt):
            log.info('exit requested')
        except Exception:
            log.exception('unhandled error from websocket')
        self.on_close()

    def on_event(self, event):
        """Called when new websocket events arrive."""
        if event.name == 'ready':
            self.on_ready()
        elif event.name == 'disconnected':
            self.on_disconnected()
        elif event.name == 'binary':
            self.on_binary(event.data)
        elif event.name == 'poll':
            self.sync_identity()

    def close(self, timeout=5):
        self.websocket.close()
        self._closed = True
        self.identity = None

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
        try:
            self.websocket.send_binary(packet_bytes)
        except WebSocketError:
            return False
        else:
            return True

    def on_ready(self):
        """Called when WS is opened."""
        log.debug("websocket opened")
        if self.identity is None:
            self.send(PacketType.request_join)
        else:
            self.send(PacketType.request_identify, uuid=self.identity)

    def on_binary(self, data):
        """On a WS message."""
        self.last_packet_time = time.time()
        try:
            packet = bencode.decode(data)
        except:
            log.exception('packet could not be decoded')
        else:
            self.on_packet(packet)

    def sync_identity(self):
        """Ask manager to set the m2m identity."""
        self.manager.set_identity(self.identity)

    def on_disconnected(self):
        """Called when ws socket closes."""
        self.identity = None
        self.clear_callbacks()
        self.hard_close_channels()

    def on_packet(self, packet):
        """Called with a binary packet."""
        try:
            packet_type = packets.PacketType(packet[0])
            packet_body = packet[1:]
        except:
            log.exception('packet is badly formatted')
        else:
            self.dispatcher.dispatch(packet_type, packet_body)

    def channel_write(self, channel, data):
        """Write data to a virtual channel."""
        self.send(PacketType.request_send, channel=channel, data=data)

    def on_instruction(self, sender, data):
        """Called with an instruction."""
        log.debug('instruction from {%s} %r', sender, data)
        self.manager.on_instruction(sender, data)

    def channel_control_write(self, channel, control_dict):
        """Send a channel control packet."""
        control_json = json.dumps(control_dict)
        self.send(
            PacketType.request_send_control,
            channel=channel,
            data=control_json
        )

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
            log.debug('setting identity to %s', identity)
            self.identity = identity
            self.sync_identity()

    @expose(PacketType.ping)
    def handle_ping(self, packet_type, data):
        """Ping send from the server, send back a pong with the same data."""
        self.send('pong', data=data[:1024])

    @expose(PacketType.welcome)
    def handle_welcome(self, packet_type):
        """Welcome packet means we can start talking to the m2m server."""
        pass

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

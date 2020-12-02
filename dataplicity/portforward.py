"""
Port forwarding client.

Reads and writes to a socket, proxied over m2m.

"""

from __future__ import print_function
from __future__ import unicode_literals

from time import time
import logging
import select
import socket
import threading
import weakref

from .constants import CHUNK_SIZE, SERVER_BUSY


log = logging.getLogger("pf")


class Connection(threading.Thread):
    """Handles a single remote controlled TCP/IP connection."""

    def __init__(self, limiter, close_event, channel, host_port):
        """Initialize the connection, set up callbacks."""
        super(Connection, self).__init__()
        self.limiter = limiter
        self._close_event = close_event
        self.channel = channel
        self.host_port = host_port

        self._lock = threading.RLock()
        self._start_time = time()
        self.socket = None
        self.read_buffer = []  # For data received before we connected

        self.channel.set_callbacks(
            self.on_channel_data, self.on_channel_close, self.on_channel_control
        )

    @property
    def close_event(self):
        """Get a threading.Event object."""
        return self._close_event

    def run(self):
        """Run the main loop, and decrement limiter."""
        try:
            self._run()
        finally:
            # Ensure decrement is called if _run throws an exception
            self.limiter.decrement()

    def _run(self):
        """
        Main loop, connects to local server, reads data, and writes it to an
        m2m channel.
        """
        bytes_written = 0
        readable_events = select.POLLIN | select.POLLPRI  # Data in , priority data in
        error_events = select.POLLERR | select.POLLHUP  #  Error or hang up
        events = readable_events | error_events
        poll = select.poll()
        try:
            # Connect to remote host
            if not self._connect():
                return

            poll.register(self.socket.fileno(), events)

            log.debug("entered recv loop")
            # Read all the data we can and write it to the channel
            while not self.close_event.is_set():
                # Block for a period of time until the socket becomes readable,
                # or there is an error
                try:
                    poll_result = poll.poll(5 * 1000)
                except Exception as error:
                    # For paranoia only.
                    log.warning("error in portforward.py poll.poll; %s", error)
                    break
                if self.channel.is_closed:
                    break
                for _file_descriptor, event_mask in poll_result:
                    if event_mask & readable_events:
                        try:
                            # Reads *up to* BUFFER_SIZE bytes
                            data = self.socket.recv(CHUNK_SIZE)
                        except Exception:
                            log.exception("error in recv")
                            break
                        else:
                            if data:
                                self.channel.write(data)
                                bytes_written += len(data)
                            else:
                                # No data means the socket has been closed
                                break
                    if event_mask & error_events:
                        # Socket has been closed in another thread, possibly due to
                        # m2m channel closing
                        self.close_event.set()
        finally:

            speed = bytes_written / 1024.0 / (time() - self._start_time)
            log.debug("left recv loop (read %s bytes) %0.1fKB/s ", bytes_written, speed)
            # These close methods are a null operation if the objects are
            # already closed
            self.channel.close()
            self._shutdown_read()

    def _shutdown_read(self):
        """Shutdown reading."""
        with self._lock:
            if self.socket:
                try:
                    self.socket.shutdown(socket.SHUT_RD)
                except Exception:
                    pass

    def _shutdown_write(self):
        """Shutdown writing."""
        with self._lock:
            if self.socket:
                try:
                    self.socket.shutdown(socket.SHUT_WR)
                except Exception:
                    pass

    def _close_socket(self):
        """Shutdown the socket."""
        with self._lock:
            if self.socket is not None:
                try:
                    self.socket.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    self.socket.close()
                except Exception:
                    log.exception("error closing socket")

    def connect(self):
        """Start thread, and connect to local server."""
        # Connect may block, so do it in a thread

        try:
            with self.limiter():
                self.start()
        except Exception as error:
            log.warning("unable to start portforard thread; %r", error)
            self.channel.write(SERVER_BUSY)
            self.channel.close()

    def _connect(self):
        """Connect to a local server, return True on success."""
        _socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # No Nagle since we are going for as close to realtime as possible
        _socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # Set the timeout for initial connect, as default is too high
        _socket.settimeout(5.0)

        log.debug("connecting to %s:%d", *self.host_port)
        try:
            _socket.connect(self.host_port)
        except socket.timeout:
            log.error("timed out connecting to server")
            return False
        except IOError as e:
            log.error("IO Error when connecting, %s", e)
            return False
        except Exception:
            log.exception("error connecting")
            return False
        else:
            log.debug("connected to %s:%d", *self.host_port)
            self.socket = _socket
            self._flush_buffer()
            return True

    def on_channel_data(self, data):
        """Called by m2m channel."""
        with self._lock:
            self.read_buffer.append(data)
            self._flush_buffer()

    def _flush_buffer(self):
        with self._lock:
            if self.socket is not None:
                try:
                    for chunk in self.read_buffer:
                        self.socket.sendall(chunk)
                finally:
                    del self.read_buffer[:]

    def on_channel_close(self):
        """Called when the channel has been closed."""
        log.debug("channel close")
        with self._lock:
            # Shut down the socket
            # This will cause an exceptional condition in the select loop,
            # which will subsequently exit cleanly
            self._flush_buffer()
            self._shutdown_write()

    def on_channel_control(self, data):
        """Called when the remote end sends a control packet (currently not used)."""
        log.debug("channel control %r", data)


class Service(object):
    """A service defines a host and port to forward."""

    def __init__(self, manager, name, port, host="127.0.0.1"):
        self._manager = weakref.ref(manager)
        self.name = name
        self.port = port
        self.host = host
        self.m2m_port = None
        self._connect_index = 0
        self._lock = threading.RLock()

    def __repr__(self):
        """Some useful info re the service."""
        return "<service {}:{} '{}'>".format(self.host, self.port, self.name)

    @property
    def manager(self):
        """Get the manager from weakref."""
        return self._manager()

    @property
    def m2m(self):
        """Get the M2M interface."""
        return self.manager.m2m

    @property
    def close_event(self):
        """The one close event to rule them all."""
        return self.manager.close_event

    @property
    def host_port(self):
        """A tuple of (host, port) as a convenience for socket.connect."""
        return (self.host, self.port)

    def connect(self, limiter, port_no):
        """Add a new connection."""
        self.m2m_port = port_no
        channel = self.m2m.m2m_client.get_channel(port_no)
        log.debug("new %r connection on port %s", self, port_no)
        try:
            with limiter():
                with self._lock:
                    connection = Connection(
                        limiter, self.close_event, channel, self.host_port
                    )
                connection.start()
        except Exception as error:
            channel.write(SERVER_BUSY)
            channel.close()
            log.warning("failed to connect %r; %s", self, error)


class PortForwardManager(object):
    """Managed port forwarded services."""

    def __init__(self, client):
        self._client = weakref.ref(client)
        self._services = {}
        self._ports = {}
        self._close_event = threading.Event()

    @property
    def client(self):
        return self._client()

    @property
    def m2m(self):
        return self.client.m2m if self.client else None

    @classmethod
    def init(cls, client):
        manager = cls(client)
        manager.add_service("web", 80)
        manager.add_service("ext", 81)
        manager.add_service("extalt", 8000)
        manager.add_service("alt", 8080)
        return manager

    @property
    def close_event(self):
        return self._close_event

    def on_client_close(self):
        """M2M client closed."""
        log.debug("m2m exited")

    def get_service_on_port(self, port):
        """Get the service on a numbered port."""
        service_name = self._ports.get(port)
        if service_name is None:
            return None
        return self._services[service_name]

    def get_service(self, service, default=None):
        """Get a named service."""
        return self._services.get(service, default)

    def add_service(self, name, port, host="127.0.0.1"):
        """Add a service to be exposed."""
        service = Service(self, name, port, host=host)
        self._services[name] = service
        self._ports[port] = name
        log.debug("added port forward service '%s' on port %s", name, port)

    def open_service(self, limiter, service, route):
        log.debug("opening service %s on %r", service, route)
        node1, port1, node2, port2 = route
        self.open(limiter, port2, service)

    def open(self, limiter, m2m_port, service=None, port=None):
        """Open a port forward service."""
        if service is None and port is None:
            raise ValueError("one of service or port is required")
        if port is not None:
            service = self.get_service_on_port(port or 80)
        elif service is not None:
            service = self.get_service(service)
        if service is None:
            return
        service.connect(limiter, m2m_port)

    def redirect_port(self, limiter, m2m_port, device_port):
        # we need to store the reference to the Service somewhere so that
        # when the Connection starts in thread it wouldn't loose the value
        # of service variable. However, we have to remember that there may
        # be numerous connections to the same local port.
        # for instance, one could be ssh'ed into a machine twice, so we
        # shan't confuse these two connections.
        # therefore, an easy way is to store these in a dict, so that the
        # lookup would be quick
        #
        channel = self.m2m.m2m_client.get_channel(m2m_port)
        try:
            with limiter():
                Connection(
                    limiter,
                    close_event=self.close_event,
                    channel=channel,
                    host_port=("127.0.0.1", device_port),
                ).start()
        except Exception as error:
            log.warning("unable to start portforard thread; %r", error)
            channel.write(SERVER_BUSY)
            channel.close()

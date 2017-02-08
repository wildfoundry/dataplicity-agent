from __future__ import unicode_literals
from __future__ import print_function

"""
Dispatches incoming packets

"""


from ..compat import text_type

import logging
import inspect


class PacketFormatError(Exception):
    pass


class UnknownMethodError(Exception):
    """Unknown packet type"""


def expose(packet_type):
    def deco(f):
        f._dispatcher_exposed = True
        f._dispatcher_packet_type = packet_type
        return f
    return deco


class Dispatcher(object):
    """
    Base class to dispatch to handlers for a packet.

    May also be used to dispatch to methods of another object, rather than a base class.

    """

    def __init__(self, packet_cls=None, handler_instance=None, log=None):
        super(Dispatcher, self).__init__()
        self._handler_instance = handler_instance or self

        if log is None:
            self.log = logging.getLogger('dispatcher')
        else:
            self.log = log

        self._packet_cls = packet_cls
        self._packet_handlers = {}
        self._init_dispatcher()
        self._dispatch_enabled = True

    def set_packet_class(self, packet_cls):
        self._packet_cls = packet_cls

    def disable(self):
        """Prevent all further packet dispatch."""
        self._dispatch_enabled = False
        self._packet_handlers.clear()

    def _init_dispatcher(self):
        for method_name in dir(self._handler_instance):
            if method_name.startswith('_'):
                continue
            method = getattr(self._handler_instance, method_name)
            if getattr(method, '_dispatcher_exposed', False):
                packet_type = method._dispatcher_packet_type
                self._packet_handlers[packet_type] = method

    def dispatch(self, packet_type, packet_body):
        """Dispatch a packet to appropriate handler"""
        if not self._dispatch_enabled:
            return
        if not isinstance(packet_type, int):
            raise PacketFormatError('packet type should be an int')
        assert self._packet_cls is not None, "packet class must be set with set_packet_class"

        packet = self._packet_cls.create(packet_type, *packet_body)
        return self.dispatch_packet(packet)

    def dispatch_packet(self, packet):
        if not getattr(packet, 'no_log', False):
            self.log.debug('received %r', packet)
        packet_type = packet.type
        method = self._packet_handlers.get(packet_type, None)

        if method is None:
            self.on_missing_handler(packet)
            return None

        arg_spec = inspect.getargspec(method)
        args, kwargs = packet.get_method_args(len(arg_spec[0]))

        try:
            inspect.getcallargs(method, packet_type, *args, **kwargs)
        except TypeError as e:
            raise PacketFormatError(text_type(e))

        try:
            ret = method(packet_type, *args, **kwargs)
        except Exception:
            raise
        else:
            return ret

    def on_missing_handler(self, packet):
        """Called when no handler is available to handle `packet`"""
        self.log.debug('missing handler for %r', packet)

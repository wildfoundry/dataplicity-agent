"""A M2M service that returns data sent to it. May be used as a heart-beat."""

from __future__ import print_function
from __future__ import unicode_literals

import logging
import weakref

log = logging.getLogger('m2m')


class EchoService(object):
    """
    M2M echo service.

    Data will be sent back on the same channel.

    """

    def __init__(self, channel):
        # When the channel is closed, this object should go out of scope
        self.channel = weakref.ref(channel)
        channel.set_callbacks(on_data=self.on_data)

    def on_data(self, data):
        # Send data back
        self.channel().write(data)

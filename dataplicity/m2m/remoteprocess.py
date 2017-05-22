"""Manage a subprocess that streams to a remote side"""

from __future__ import unicode_literals
from __future__ import print_function

import json
import logging
import os
import signal
import shlex

from . import proxy

log = logging.getLogger('m2m')


class RemoteProcess(proxy.Interceptor):
    """Process managed remotely over m2m."""

    def __init__(self, command, channel, user=None, group=None, size=None):
        self.command = command
        self.channel = channel
        self.size = size

        self._closed = False

        self.channel.set_callbacks(on_data=self.on_data,
                                   on_close=self.on_close,
                                   on_control=self.on_control)

        super(RemoteProcess, self).__init__(user=user, group=group, size=size)

    @property
    def is_closed(self):
        return self._closed

    def __repr__(self):
        return "RemoteProcess({!r}, {!r})".format(self.command, self.channel)

    def run(self):
        self.spawn(shlex.split(self.command))

    def on_data(self, data):
        try:
            self.stdin_read(data)
        except:
            self.channel.close()

    def on_control(self, data):
        try:
            control = json.loads(data)
        except:
            log.exception("error decoding control")
            return
        control_type = control.get('type', None)
        if control_type == "window_resize":
            size = control['size']
            log.debug('resize terminal to {} X {}'.format(*size))
            self.resize_terminal(size)
        else:
            log.warning('unknown control packet {}'.format(control_type))

    def on_close(self):
        self.close()

    def master_read(self, data):
        self.channel.write(data)
        super(RemoteProcess, self).master_read(data)

    def write_master(self, data):
        super(RemoteProcess, self).write_master(data)

    def close(self):
        if not self._closed and self.pid is not None:
            log.debug('sending kill signal to %r', self)
            # TODO: Implement a non-blocking kill
            os.kill(self.pid, signal.SIGKILL)
            log.debug('waiting for %r', self)
            os.waitpid(self.pid, 0)
            log.debug('killed %r', self)
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

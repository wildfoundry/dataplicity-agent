"""Manage a subprocess that streams to a remote side"""

from __future__ import unicode_literals
from __future__ import print_function

import json
import logging
import os
import signal
import shlex
import time
from threading import Thread

from . import proxy

log = logging.getLogger("m2m")


class PidWaitThread(Thread):
    """A thread to wait for a process to exit, and display warnings."""

    def __init__(self, command, pid):
        self.command = command
        self.pid = pid
        super(PidWaitThread, self).__init__()
        self.daemon = True

    def __str__(self):
        return '"%s" (pid=%i)' % (self.command, self.pid)

    def run(self):
        """Poll PID for exit status, displaying warnings at given intervals if it is taking too long."""
        log.debug("Waiting for %s to close", self)
        start_time = time.time()
        warnings = [
            5,
            10,
            30,
            60,
            60 * 10,  # ten minutes
            60 * 60,  # An hour
            60 * 60 * 24,  # A day
        ]  # Seconds between warnings
        sent_kill = False
        kill_time = 15  # Send a sigkill if process doesn't shut down (in seconds)
        while warnings:
            time.sleep(2)
            # os.WNOHANG flags makes waitpid return immediately if the process is running
            pid, exit_code = os.waitpid(self.pid, os.WNOHANG)
            if pid:
                # The process has returned an exit code
                log.debug("process %s exited with code=%i", self, exit_code)
                break
            else:
                # Process is still running
                time_passed = time.time() - start_time
                if time_passed >= warnings[0]:
                    warnings.pop(0)
                    log.warning(
                        "process %s failed to exit after %.1f seconds",
                        self,
                        time_passed,
                    )
                if not sent_kill and time_passed >= kill_time:
                    sent_kill = True
                    log.debug("sending SIGKILL to process %s", self)
                    os.kill(self.pid, signal.SIGKILL)
        else:
            log.error("process %s will not die!", self)


class RemoteProcess(proxy.Interceptor):
    """Process managed remotely over m2m."""

    def __init__(self, limiter, command, channel, user=None, group=None, size=None):
        self.limiter = limiter
        self.command = command
        self.channel = channel
        self.size = size
        self._closed = False
        self.channel.set_callbacks(
            on_data=self.on_data, on_close=self.on_close, on_control=self.on_control
        )

        super(RemoteProcess, self).__init__(user=user, group=group, size=size)

    @property
    def is_closed(self):
        return self._closed

    def __repr__(self):
        return "RemoteProcess({!r}, {!r}, pid={})".format(
            self.command, self.channel, self.pid
        )

    def run(self):
        try:
            self.spawn(shlex.split(self.command))
        finally:
            self.limiter.decrement()

    def on_data(self, data):
        try:
            self.stdin_read(data)
        except Exception:
            self.channel.close()

    def on_control(self, data):
        try:
            control = json.loads(data)
        except Exception:
            log.exception("error decoding control")
            return
        control_type = control.get("type", None)
        if control_type == "window_resize":
            size = control["size"]
            log.debug("resize terminal to {} X {}".format(*size))
            self.resize_terminal(size)
        else:
            log.warning("unknown control packet {}".format(control_type))

    def on_close(self):
        self.close()

    def master_read(self, data):
        self.channel.write(data)
        super(RemoteProcess, self).master_read(data)

    def write_master(self, data):
        super(RemoteProcess, self).write_master(data)

    def close(self):
        if not self._closed and self.pid is not None:
            log.debug("sending SIGHUP to %r", self)
            os.kill(self.pid, signal.SIGHUP)
            try:
                wait_thread = PidWaitThread(self.command, self.pid)
                wait_thread.start()
            except Exception as error:
                log.warning("pid wait thread failed to launch; %s", error)
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

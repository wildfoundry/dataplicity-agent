"""

An M2M Service to run commands.

The stdout is sent a line at a time, until the command is finished,
and the channel is closed.

"""

from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import select
import subprocess
import threading

from lomond.errors import WebSocketError

from ..limiter import LimitReached
from ..constants import CHUNK_SIZE


log = logging.getLogger("m2m")


class CommandService(threading.Thread):
    """Runs a command and sends the stdout over m2m."""

    def __init__(self, limiter, channel, command):
        self.limiter = limiter
        self._repr = "CommandService({!r}, {!r})".format(channel, command)
        try:
            with limiter():
                super(CommandService, self).__init__(
                    args=(channel, command), target=self.run_service
                )
                self.start()
        except Exception as error:
            log.warning("unable to launch %r; %s", self, error)
            self.send_error(channel, "error", str(error))
            channel.close()

    def __repr__(self):
        return self._repr

    @classmethod
    def send_error(cls, channel, status, msg, **extra):
        """Send a control packet with an error"""
        error = {"service": "command", "type": "error", "status": status, "msg": msg}
        error.update(extra)
        channel.send_control(error)

    def run_service(self, channel, command):
        """Run the thread and log exceptions."""
        try:
            try:
                self._run_service(channel, command)
            except Exception:
                log.exception("error running %r", self)
                self.send_error(channel, "error", "error running command")
        finally:
            self.limiter.decrement()

    def _run_service(self, channel, command):
        """Run command and send stdout over m2m."""
        log.debug("%r started", self)
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )
        bytes_sent = 0
        stdout_fh = process.stdout.fileno()
        stderr_fh = process.stderr.fileno()

        readable_events = select.POLLIN | select.POLLPRI  # Data in , priority data in
        error_events = select.POLLERR | select.POLLHUP  #  Error or hang up
        events = readable_events | error_events
        poll = select.poll()
        poll.register(stdout_fh, events)
        poll.register(stderr_fh, events)
        try:
            more_data = True
            while more_data:
                try:
                    poll_result = poll.poll(0.5 * 1000)
                except Exception as error:
                    log.warning("error in commandservice.py poll.poll; %s", error)
                    break

                for _file_descriptor, event_mask in poll_result:
                    if event_mask & readable_events:
                        if _file_descriptor == stdout_fh:
                            chunk = os.read(stdout_fh, CHUNK_SIZE)
                            if not chunk:
                                more_data = False
                                log.debug("%r EOF", self)
                                break
                            channel.write(chunk)
                            bytes_sent += len(chunk)
                        else:
                            chunk = os.read(stderr_fh, CHUNK_SIZE)
                            log.debug("%r [stderr] %r", self, chunk)
                    if event_mask & error_events:
                        break
                if channel.is_closed:
                    log.debug("%r channel closed", self)
                    break

        except WebSocketError as websocket_error:
            log.warning("%r websocket error (%s)", self, websocket_error)
            # Can't send error message if websocket is fubar
        except Exception as error:
            log.exception("%r error", self)
            self.send_error(channel, "error", "error running command")
        else:
            log.info('read %s byte(s) from command "%s"', bytes_sent, command)
        finally:
            channel.send_control(
                {"service": "command", "type": "complete", "returncode": process.poll()}
            )
            channel.close()
            try:
                if process.poll() is None:
                    process.kill()
            except OSError:
                log.exception("%r failed to kill", self)

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


log = logging.getLogger('m2m')


class CommandService(threading.Thread):
    """Runs a command and sends the stdout over m2m."""

    CHUNK_SIZE = 4096

    def __init__(self, channel, command):
        self._repr = "CommandService({!r}, {!r})".format(channel, command)
        super(CommandService, self).__init__(
            args=(channel, command),
            target=self.run_service
        )
        self.start()

    def __repr__(self):
        return self._repr

    @classmethod
    def send_error(cls, channel, status, msg, **extra):
        """Send a control packet with an error"""
        error = {
            "service":"run-command",
            "type": "error",
            "status": status,
            "msg": msg
        }
        error.update(extra)
        channel.send_control(error)

    def run_service(self, channel, command):
        """Run the thread and log exceptions."""
        try:
            self._run_service(channel, command)
        except Exception:
            log.exception("error running %r", self)
            self.send_error(channel, "error", "error running command")

    def _run_service(self, channel, command):
        """Run command and send stdout over m2m."""
        log.debug("%r started", self)
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True
            )
        except OSError as error:
            log.warning('%r command failed; %s', self, error)
            self.send_error(channel, "fail", "failed to run command")
            return

        bytes_sent = 0
        stdout_fh = process.stdout.fileno()
        stderr_fh = process.stderr.fileno()
        try:
            while True:
                if channel.is_closed:
                    log.debug("%r channel closed", self)
                    break
                readable, _, _ = select.select(
                    [stdout_fh, stderr_fh], [], [], 0.5
                )
                for fh in readable:
                    if fh == stdout_fh:
                        # Send stdout over m2m
                        chunk = os.read(fh, self.CHUNK_SIZE)
                        if not chunk:
                            log.debug('%r EOF', self)
                            break
                        channel.write(chunk)
                        bytes_sent += len(chunk)
                    elif fh == stderr_fh:
                        # Log stderr
                        chunk = os.read(fh, self.CHUNK_SIZE)
                        log.debug("%r [stderr] %r", self, chunk)
            else:
                log.debug('%r complete', self)

        except WebSocketError as websocket_error:
            log.warning('%r websocket error (%s)', self, websocket_error)
            # Can't send error message if websocket is fubar
        except Exception as error:
            log.exception('%r error', self)
            self.send_error(channel, "error", "error running command")
        else:
            log.info(
                'read %s byte(s) from command "%s"',
                bytes_sent,
                command
            )
        finally:
            channel.close()
            process.terminate()

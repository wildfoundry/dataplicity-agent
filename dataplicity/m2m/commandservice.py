"""

An M2M Service to run commands.

The stdout it sent a line at a time, until the command is finished,
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

    CHUNK_SIZE = 1024

    def __init__(self, channel, command):
        self._repr = "CommandService({!r}, {!r})".format(channel, command)
        super(CommandService, self).__init__(
            args=(channel, command),
            target=self.run_service
        )
        self.start()

    def __repr__(self):
        return self._repr

    def run_service(self, channel, command):
        """Run the thread and log exceptions."""
        try:
            self._run_service(channel, command)
        except Exception:
            log.exception("error running %r", self)

    def _run_service(self, channel, command):
        """Run command and send stdout over m2m."""
        log.debug("%r started", self)
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                shell=True
            )
        except OSError as error:
            log.warning('%r command failed; %s', self, error)
            return

        bytes_sent = 0
        fh = process.stdout.fileno()
        try:
            while True:
                if channel.is_closed:
                    log.debug("%r channel closed", self)
                    break
                readable, _, _ = select.select([fh], [], [], 0.5)
                if readable:
                    chunk = os.read(fh, self.CHUNK_SIZE)
                    if not chunk:
                        log.debug('%r EOF', self)
                        break
                    channel.write(chunk)
                    bytes_sent += len(chunk)
            else:
                log.debug('%r complete', self)

        except WebSocketError as websocket_error:
            log.warning('%r websocket error (%s)', self, websocket_error)
        except Exception as error:
            log.exception('%r error', self)
        else:
            log.info(
                'read %s byte(s) from command "%s"',
                bytes_sent,
                command
            )
        finally:
            process.terminate()
            channel.close()

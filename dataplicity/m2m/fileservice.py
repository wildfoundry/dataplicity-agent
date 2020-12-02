"""

An M2M Service to retrieve files.

File data is sent in chunks.

"""

from __future__ import print_function
from __future__ import unicode_literals

from functools import partial
import logging
import os.path
import threading

from lomond.errors import WebSocketError

from ..limiter import LimitReached
from ..constants import CHUNK_SIZE, SERVER_BUSY


log = logging.getLogger("m2m")


class FileService(threading.Thread):
    """A thread the sends data from a file over m2m."""

    # A word on lifetime management of this and similar objects...
    # There does not need to be any other references to these objects;
    # the thread maintains a reference to a m2m channel in the run
    # function, so the entire object will be garbage collected when
    # the thread exits.

    def __init__(self, limiter, channel, path):
        self.limiter = limiter
        self._repr = "FileService({!r}, {!r})".format(channel, path)
        try:
            with limiter():
                super(FileService, self).__init__(
                    args=(channel, path), target=self.run_service
                )
                self.start()
        except Exception as error:
            # Could be limit reached, or out of threads
            log.warning("failed to create file service; %s", error)
            channel.write(SERVER_BUSY)
            channel.close()

    def __repr__(self):
        return self._repr

    @classmethod
    def send_error(cls, channel, status, msg, **extra):
        """Send a control packet with an error"""
        error = {
            "service": "remote-file",
            "type": "error",
            "status": status,
            "msg": msg,
        }
        error.update(extra)
        channel.send_control(error)

    def run_service(self, channel, path):
        """Run the thread and log exceptions."""
        try:
            try:
                self._run_service(channel, path)
            except Exception:
                log.exception("error running %r", self)
                self.send_error(channel, "error", "internal error, see agent logs")
        finally:
            self.limiter.decrement()

    def _run_service(self, channel, path):
        """Send a file over a port."""
        log.debug("%r started", self)
        bytes_sent = 0
        if not path.startswith("/"):
            path = "/" + path
        try:
            with open(path, "rb") as read_file:
                read = partial(read_file.read, CHUNK_SIZE)
                for chunk in iter(read, b""):
                    if channel.is_closed:
                        log.warning("%r m2m closed prematurely", self)
                        break
                    channel.write(chunk)
                    bytes_sent += len(chunk)
        except IOError as error:
            self.send_error(channel, "ioerror", msg="unable to open file")
            log.debug('unable to read file "%s"; %r', path, error)
        except WebSocketError as websocket_error:
            log.warning("websocket error (%s)", websocket_error)
        except Exception:
            self.send_error(channel, "error", "internal error, see agent logs")
            log.exception("error in file service")
        else:
            log.info('read %s byte(s) from "%s"', bytes_sent, path)
        finally:
            channel.close()

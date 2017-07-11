"""

An M2M Service to retrieve files.

File data is sent in chunks.

"""

from __future__ import print_function
from __future__ import unicode_literals

from functools import partial
import logging
import threading

from lomond.errors import WebSocketError


log = logging.getLogger('m2m')


class FileService(threading.Thread):
    """A thread the sends data from a file over m2m."""

    # A word on lifetime management of this and similar objects...
    # There does not need to be any other references to these objects;
    # the thread maintains a reference to a m2m channel in the run
    # function, so the entire object will be garbage collected when
    # the thread exits.

    CHUNK_SIZE = 4096

    def __init__(self, channel, path):
        self._repr = "FileService({!r}, {!r})".format(channel, path)
        super(FileService, self).__init__(
            args=(channel, path),
            target=self.run_service
        )
        self.start()

    def __repr__(self):
        return self._repr

    def run_service(self, channel, path):
        """Run the thread and log exceptions."""
        try:
            self._run_service(channel, path)
        except Exception:
            log.exception("error running %r", self)

    def _run_service(self, channel, path):
        """Send a file over a port."""
        log.debug("%r started", self)
        bytes_sent = 0
        try:
            with open(path, 'rb') as read_file:
                read = partial(read_file.read, self.CHUNK_SIZE)
                for chunk in iter(read, b''):
                    if channel.is_closed:
                        log.warning('%r m2m closed prematurely', self)
                        break
                    channel.write(chunk)
                    bytes_sent += len(chunk)
        except IOError:
            log.debug('unable to read file "%s"', path)
        except WebSocketError as websocket_error:
            log.warning('websocket error (%s)', websocket_error)
        except Exception as error:
            log.exception('error in file service')
        else:
            log.info(
                'read %s byte(s) from "%s"',
                bytes_sent,
                path
            )
        finally:
            channel.close()

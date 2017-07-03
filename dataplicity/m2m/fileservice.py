"""

An M2M Service to retrieve files.

"""

from __future__ import print_function
from __future__ import unicode_literals

import logging
import weakref

log = logging.getLogger('m2m')


class FileService(object):

    def __init__(self, channel, path):
        self.channel = weakref.ref(channel)
        self.path = path
        self._send_file()

    def _send_file(self):
        """Send a file over a port."""
        # Fairly naive implementation
        try:
            with open(self.path, 'rb') as read_file:
                file_data = read_file.read()
        except IOError:
            log.debug('unable to open file "%s"', self.path)
        except Exception as error:
            log.exception('error in file service')
        else:
            log.debug(
                'read %s byte(s) from ""',
                len(file_data),
                self.path
            )
            self.channel.write(file_data)
        finally:
            self.channel.close()

"""

An M2M Service to run commands.

"""

from __future__ import print_function
from __future__ import unicode_literals

import logging
import subprocess
import weakref

log = logging.getLogger('m2m')


class CommandService(object):

    def __init__(self, channel, command):
        self.channel = weakref.ref(channel)
        self.command = command
        self._run_command()

    def _run_command(self):
        try:
            output = subprocess.check_output(self.command, shell=True)
        except subprocess.CalledProcessError as process_error:
            log.debug(
                'command error with code=%s',
                process_error.returncode
            )
        except Exception as error:
            log.debug('error running "%s" (%s)', self.command, error)
        else:
            self.channel.write(output)
        finally:
            self.channel.close()
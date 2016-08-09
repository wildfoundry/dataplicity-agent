from __future__ import unicode_literals
from __future__ import print_function

import logging

from .. import constants
from ..subcommand import SubCommand


log = logging.getLogger('install')


class Install(SubCommand):
    """Run the dataplicity service in the foreground"""
    help = """Install firmware"""

    def add_arguments(self, parser):
        parser.add_argument(dest="path", metavar="PATH",
                            help="Firmware to install")
        parser.add_argument('-i', dest="install_path", metavar="INSTALL PATH", default=None,
                            help="Directory where the firmware should be installed")
        parser.add_argument('-a', '--active', dest="make_active", action="store_true",
                            help="make this the active firmware")
        parser.add_argument('-q', '--quiet', dest="quiet", action="store_true",
                            help="silence output")

    def run(self):
        log.warning('install is deprecated')

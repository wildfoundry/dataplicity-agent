from __future__ import unicode_literals
from __future__ import print_function

import logging

from ..subcommand import SubCommand


log = logging.getLogger('registersamplers')


class Registersamplers(SubCommand):
    """Run the dataplicity service in the foreground"""
    help = """Register samplers"""

    def add_arguments(self, parser):
        parser.add_argument('--auth', dest="auth", metavar="AUTH TOKEN", default=None, required=False,
                            help="Authorization token (the default use the auth token in datpalicity.conf)")

    def run(self):
        log.warning('registersamplers is deprecated')

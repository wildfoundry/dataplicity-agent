from __future__ import unicode_literals
from __future__ import print_function

import logging

from ..subcommand import SubCommand


log = logging.getLogger('registersamplers')


class Report(SubCommand):
    """Run the dataplicity service in the foreground"""
    help = """Send a diagnostic report to Dataplicity support"""

    def add_arguments(self, parser):
        return parser

    def run(self):
        log.warning('not implemented')

from __future__ import unicode_literals
from __future__ import print_function

import logging

from ..subcommand import SubCommand


log = logging.getLogger('dpagent')


class Run(SubCommand):
    """Run the dataplicity service in the foreground"""
    help = """Run dataplicity agent"""

    def add_arguments(self, parser):
        return parser

    def run(self):
        client = self.app.make_client()
        client.run_forever()

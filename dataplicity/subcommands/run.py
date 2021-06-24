from __future__ import unicode_literals
from __future__ import print_function

from ..subcommand import SubCommand


class Run(SubCommand):
    """Run the dataplicity service in the foreground"""

    help = """Run dataplicity agent"""

    def run(self):
        client = self.app.make_client()
        client.run_forever()

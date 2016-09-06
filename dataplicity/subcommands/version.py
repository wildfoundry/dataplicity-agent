from __future__ import unicode_literals
from __future__ import print_function

from ..subcommand import SubCommand
from .. import __version__

import sys


class Version(SubCommand):
    """Run the dataplicity service in the foreground"""
    help = """Write version to stdout."""

    def run(self):
        sys.stdout.write(__version__)

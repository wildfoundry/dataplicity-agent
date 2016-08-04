
from ..subcommand import SubCommand


class Report(SubCommand):
    """Run the dataplicity service in the foreground"""
    help = """Send a diagnostic report to Dataplicity support"""

    def add_arguments(self, parser):
        return parser

    def run(self):
        pass

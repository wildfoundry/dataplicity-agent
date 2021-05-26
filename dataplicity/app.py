from __future__ import unicode_literals
from __future__ import print_function

import argparse
import logging
import logging.config
import sys

from . import __version__
from . import subcommand
from .client import Client
from .subcommands import run, version

log = logging.getLogger("app")

# Map log levels on to integer values
_logging_level_names = {
    "NOTSET": 0,
    "DEBUG": 10,
    "INFO": 20,
    "WARN": 30,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


class App(object):
    """Dataplicity Agent command line interface."""

    def __init__(self):
        self.subcommands = {
            name: cls(self) for name, cls in subcommand.registry.items()
        }

    def _make_arg_parser(self):
        """Make an argument parse object."""
        parser = argparse.ArgumentParser("dataplicity", description=self.__doc__)

        _version = "dataplicity agent v{}".format(__version__)
        parser.add_argument(
            "-v",
            "--version",
            action="version",
            version=_version,
            help="Display version and exit",
        )
        parser.add_argument(
            "--log-level",
            metavar="LEVEL",
            default="INFO",
            help="Set log level (INFO or WARNING or ERROR or DEBUG)",
        )
        parser.add_argument(
            "--log-file", metavar="PATH", default=None, help="Set log file"
        )
        parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            dest="debug",
            default=False,
            help="Enables debug output",
        )
        parser.add_argument(
            "-s",
            "--server-url",
            metavar="URL",
            dest="server_url",
            default=None,
            help="URL of dataplicity.com api",
        )
        parser.add_argument(
            "-m",
            "--m2m-url",
            metavar="WS URL",
            dest="m2m_url",
            default=None,
            help="URL of m2m server (should start with ws:// or wss://",
        )
        parser.add_argument(
            "-q", "--quiet", action="store_true", default=False, help="Hide output"
        )
        parser.add_argument(
            "--serial",
            dest="serial",
            metavar="SERIAL",
            default=None,
            help="Set Dataplicity serial",
        )
        parser.add_argument(
            "--auth",
            dest="auth_token",
            metavar="KEY",
            default=None,
            help="Set Dataplicity auth token",
        )

        parser.add_argument(
            "--remote-dir",
            dest="remote_directory",
            metavar="PATH",
            default=None,
            help="Set remote directory location",
        )

        subparsers = parser.add_subparsers(
            title="available sub-commands", dest="subcommand", help="sub-command help"
        )

        for name, _subcommand in self.subcommands.items():
            subparser = subparsers.add_parser(
                name,
                help=_subcommand.help,
                description=getattr(_subcommand, "__doc__", None),
            )
            _subcommand.add_arguments(subparser)
        return parser

    def _init_logging(self):
        """Initialise logging."""
        log_format = "%(asctime)s %(name)s\t: %(message)s"
        log_level = "CRITICAL" if self.args.quiet else self.args.log_level.upper()
        try:
            log_level_no = _logging_level_names[log_level]
        except IndexError:
            self.error("invalid log level")

        if self.args.log_file:
            log_config = {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "simple": {
                        "class": "logging.Formatter",
                        "format": log_format,
                        "datefmt": "[%d/%b/%Y %H:%M:%S]",
                    }
                },
                "handlers": {
                    "file": {
                        "level": log_level,
                        "class": "logging.handlers.RotatingFileHandler",
                        "maxBytes": 5 * 1024 * 1024,
                        "backupCount": 5,
                        "filename": self.args.log_file,
                        "formatter": "simple",
                    }
                },
                "loggers": {"": {"level": log_level, "handlers": ["file"]}},
            }
            logging.config.dictConfig(log_config)
        else:
            logging.basicConfig(
                format=log_format, datefmt="[%d/%b/%Y %H:%M:%S]", level=log_level_no
            )

    def make_client(self):
        """Make the client object."""
        client = Client(
            rpc_url=self.args.server_url,
            m2m_url=self.args.m2m_url,
            serial=self.args.serial,
            auth_token=self.args.auth_token,
            remote_directory_path=self.args.remote_directory,
        )
        return client

    def error(self, msg, code=-1):
        """Display error and exit app."""
        log.critical("app exit ({%s}) code={%s}", msg, code)
        sys.stderr.write(msg + "\n")
        sys.exit(code)

    def run(self):
        parser = self._make_arg_parser()
        args = self.args = parser.parse_args(sys.argv[1:])

        self._init_logging()
        log.debug("ready")

        if args.subcommand is None:
            parser.print_help()
            return 1

        subcommand = self.subcommands[args.subcommand]
        subcommand.args = args

        try:
            return subcommand.run() or 0
        except Exception as e:
            if self.args.debug:
                raise
            sys.stderr.write("(dataplicity {}) {}\n".format(__version__, e))
            cmd = sys.argv[0].rsplit("/", 1)[-1]
            debug_cmd = " ".join([cmd, "--debug"] + sys.argv[1:])
            sys.stderr.write("(run '{}' for a full traceback)\n".format(debug_cmd))
            return -1


def main():
    """Dataplicity Agent entry point."""
    return_code = App().run() or 0
    log.debug("exit with code %s", return_code)
    sys.exit(return_code)

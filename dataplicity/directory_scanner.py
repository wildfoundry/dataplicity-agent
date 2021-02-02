from __future__ import print_function
from __future__ import unicode_literals

import logging
import random
from time import sleep, time
from threading import Event, Thread
from typing import Optional

from .scan_directory import scan_directory, ScanResult, ScanDirectoryError
from . import jsonrpc

log = logging.getLogger("agent")


class DirectoryScanner(Thread):
    """Periodically scans and uploads directory information."""

    def __init__(
        self, exit_event, root_path, rpc, serial, auth_token, period=60 * 60 * 24
    ):
        # type: (Event, str, jsonrpc.JSONRPC, str, str, float) -> None
        self.exit_event = exit_event
        self.root_path = root_path
        self.rpc = rpc
        self.serial = serial
        self.auth_token = auth_token
        self.period = period
        self.previous_scan = None  # type: Optional[ScanResult]
        self.scan_event = Event()
        super(DirectoryScanner, self).__init__(daemon=True)

    def run(self):
        # type: () -> None
        """Use the exit event to sleep until its time for a scan"""
        # Perform a single scan on startup
        log.info("Starting directory scan for %s", self.root_path)
        sleep(random.randint(10, 60))  # Small sleep to let everything settle
        self.perform_scan()

        # Perform scans at regular intervals
        scan_time = time() + self.period

        while not self.exit_event.is_set():
            if self.scan_event.wait(5):
                if self.exit_event.is_set():
                    break
                # schedule_scan has been called in other thread
                self.scan_event.clear()
                log.debug("Performing on-demand scan")
                self.perform_scan()
            elif time() >= scan_time:
                # Regularly scheduled scan
                scan_time += self.period
                log.debug("Performing regular scan")
                self.perform_scan()

    def schedule_scan(self):
        # type: () -> None
        """Immediately perform scan in thread."""
        self.scan_event.set()

    def perform_scan(self):
        # type: () -> None
        """Scan and upload directory structure."""
        try:
            directory = scan_directory(self.root_path)
        except ScanDirectoryError as error:
            log.warning(str(error))
        except Exception:
            log.exception("failed to scan directory; %s", self.root_path)
        else:
            try:
                self.upload_directory(directory)
            except Exception:
                log.exception("failed to upload directory")

    def upload_directory(self, directory):
        # type: (ScanResult) -> None
        """Upload directory structure (if it has changed)"""

        if self.previous_scan == directory:
            log.debug("No changes to directory scan")
            return

        try:
            with self.rpc.batch() as batch:
                batch.call_with_id(
                    "authenticate_result",
                    "device.check_auth",
                    device_class="tuxtunnel",
                    serial=self.serial,
                    auth_token=self.auth_token,
                )
                batch.call_with_id(
                    "upload_result",
                    "device.upload_directory_scan",
                    directory=directory,
                )
        except jsonrpc.JSONRPCError as error:
            log.error(
                'unable to upload directory ("%s"=%s, "%s")',
                error.method,
                error.code,
                error.message,
            )
        except Exception as error:
            log.error("upload directory failed; %s", error)
            return None
        else:
            log.debug("Uploaded directory scan successfully")
            self.previous_scan = directory

from __future__ import print_function
from __future__ import unicode_literals

import logging
import random
from time import time
from threading import Event, Thread
from typing import Optional

from .scan_directory import scan_directory, ScanResult, ScanDirectoryError
from . import jsonrpc

log = logging.getLogger("agent")


class DirectoryScanner(Thread):
    """Periodically scans and uploads directory information."""

    def __init__(self, exit_event, root_path, rpc, serial, auth_token, period=60 * 60):
        # type: (Event, str, jsonrpc.JSONRPC, str, str, float) -> None
        """Create directory Scanner.

        Args:
            exit_event (Event): Event set when client is exiting.
            root_path (str): Root of scan.
            rpc (JSONRPC instance): RPC object.
            serial (str): Device serial.
            auth_token (str): Device auth token.
            period (int, optional): Delay between regular scans (in seconds). Defaults to 60*60 (hour).
        """
        self.exit_event = exit_event
        self.root_path = root_path
        self.rpc = rpc
        self.serial = serial
        self.auth_token = auth_token
        self.period = period
        self.previous_scan = None  # type: Optional[ScanResult]
        self.scan_event = Event()
        super(DirectoryScanner, self).__init__()
        self.daemon = True

    def run(self):
        # type: () -> None
        """Use the exit event to sleep until its time for a scan"""
        log.info("Starting directory scanner for %s", self.root_path)
        # Small random delay on startup to avoid devices synchronizing
        if self.exit_event.wait(random.randint(5, 15)):
            # Client must have exited while we were waiting
            return
        # Run first scan on startup
        self.perform_scan()
        # Perform scans at regular intervals
        scan_time = time() + self.period

        while not self.exit_event.is_set():
            if self.scan_event.wait(5):
                if self.exit_event.is_set():
                    # Client has exited while waiting for scan event
                    break
                # schedule_scan has been called in other thread
                self.scan_event.clear()
                log.debug("Performing on-demand scan")
                # On demand scans include file sizes
                self.perform_scan(file_sizes=True)
            elif time() >= scan_time:
                # Regularly scheduled scan
                scan_time += self.period
                log.debug("Performing regular scan")
                # Regular scans don't include file sizes as it would likely increase data usage
                # due to files changing sizes from scan to scan
                self.perform_scan()

    def schedule_scan(self):
        # type: (bool) -> None
        """Immediately perform scan in thread."""
        self.scan_event.set()

    def perform_scan(self, file_sizes=False):
        # type: (bool) -> None
        """Scan and upload directory structure."""
        try:
            directory = scan_directory(self.root_path, file_sizes=file_sizes)
        except ScanDirectoryError as error:
            log.warning(str(error))
        except Exception:
            log.exception("failed to scan directory %s", self.root_path)
        else:
            try:
                self.upload_directory(directory, file_sizes=file_sizes)
            except Exception:
                log.exception("failed to upload directory")

    def upload_directory(self, directory, file_sizes=False):
        # type: (ScanResult, bool) -> None
        """Upload directory structure (if it has changed)"""

        if not file_sizes and self.previous_scan == directory:
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
                    "device.set_remote_directory",
                    file_sizes=file_sizes,
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
            if not file_sizes:
                self.previous_scan = directory

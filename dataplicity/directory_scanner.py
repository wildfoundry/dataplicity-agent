from __future__ import print_function
from __future__ import unicode_literals

import logging
import random
from time import time
from threading import Event, RLock, Thread
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
        self._lock = RLock()
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
                try:
                    self._perform_scan()
                except Exception:
                    # errors have been logged
                    pass
            elif time() >= scan_time:
                # Regularly scheduled scan
                scan_time += self.period
                log.debug("Performing regular scan")
                # Regular scans don't include file sizes as it would likely increase data usage
                # due to files changing sizes from scan to scan
                try:
                    self._perform_scan()
                except Exception:
                    # errors have been logged
                    pass

    def schedule_scan(self):
        # type: () -> None
        """Immediately perform scan in thread."""
        self.scan_event.set()

    def perform_scan(self, file_sizes=True):
        # type: (bool) -> None
        """Perform a scan in the background."""
        thread = Thread(target=self._perform_scan, kwargs={"file_sizes": file_sizes})
        thread.start()

    def _perform_scan(self, file_sizes=True):
        # type: (bool) -> None
        """Scan and upload directory structure."""
        with self._lock:
            try:
                start_time = time()
                directory = scan_directory(self.root_path, file_sizes=file_sizes)
                elapsed = time() - start_time
                log.debug("scan directory elapsed %.1f", elapsed * 1000)
            except ScanDirectoryError as error:
                log.warning(str(error))
                raise
            except Exception:
                log.exception("failed to scan directory %s", self.root_path)
                raise
            else:
                try:
                    self.upload_directory(directory, file_sizes=file_sizes)
                except Exception:
                    log.exception("failed to upload directory")
                    raise

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

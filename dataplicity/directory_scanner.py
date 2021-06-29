from __future__ import print_function, unicode_literals

import json
import logging
import os.path
import tempfile
from threading import Lock, Thread
from time import time
from typing import Callable, Optional

from .compat import text_type
from .scan_directory import ScanDirectoryError, ScanResult, scan_directory

log = logging.getLogger("agent")


class DirectoryScanner(object):
    """Scans and serializes directory information."""

    def __init__(self, root_path):
        # type: (str) -> None
        """Create directory Scanner.

        Args:            
            root_path (str): Root of scan.            
        """
        self.root_path = root_path

        self._lock = Lock()

    def perform_scan(self, file_sizes=True, on_success=None):
        # type: (bool, Callable[[], None]) -> None
        """Perform a scan in the background."""
        if self._lock.locked():
            # Scan is in progress, no point in doing another
            return
        thread = Thread(
            target=self._perform_scan,
            kwargs={"file_sizes": file_sizes, "on_success": on_success},
        )
        thread.start()

    def _perform_scan(self, file_sizes=True, on_success=None):
        # type: (bool, Optional[Callable]) -> None
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
                    self.write_scan(directory)
                except Exception:
                    log.exception("failed to write_scan")
                    raise
                else:
                    if on_success is not None:
                        try:
                            on_success()
                        except Exception:
                            log.exception("error in on_success")

    def write_scan(self, directory):
        # type: (ScanResult) -> None
        """Save the scan to tmp."""

        scan_json = json.dumps(directory)
        if isinstance(scan_json, text_type):
            scan_json = scan_json.encode("utf-8")

        file_path = os.path.join(
            tempfile.gettempdir(), "__dataplicity_remote_directory_scan___.json"
        )
        with open(file_path, "wb") as scan_file:
            scan_file.write(scan_json)

import logging
import shutil
import os
import os.path
import tempfile
import typing

if typing.TYPE_CHECKING:
    from typing import Text

from . import disk_tools

# Amount of free space (bytes) to leave on disk
FREE_SPACE_MARGIN = 20 * 1000 * 1000


log = logging.getLogger("agent")


class RemoteDirectoryError(Exception):
    """Base exception for remote directory errors."""


class AddFail(RemoteDirectoryError):
    """Unable to add new upload."""


class ReadFail(RemoteDirectoryError):
    """Read operation failed (unlikely be recoverable)"""


class LowDiskSpace(RemoteDirectoryError):
    """There is not enough disk space to create a snapshot."""


class IllegalPath(RemoteDirectoryError):
    """The upload path is invalid."""


def validate_path(path):
    # type: (Text) -> bool
    """Check a path has no backrefs that may end up serving outside the remote directory root.

    Args:
        path (Text): A path.

    Returns:
        bool: True if the path is valid, otherwise False
    """
    for component in path.split(os.sep):
        if component == "..":
            return False
    return True


class RemoteDirectory(object):
    """Manages remote directory."""

    def __init__(self, path):
        # type: (Text) -> None
        self.path = path
        self.temp_path = tempfile.gettempdir()

    def __repr__(self):
        # type: () -> Text
        return "RemoteDirectory(%r)" % self.path

    def get_snapshot_path(self, upload_id):
        # type: (Text) -> Text
        """Get the path to a snapshot.

        Args:
            upload_id (str): Upload ID.

        Returns:
            str: A path to the snapshot file.
        """
        try:
            temp_path = tempfile.gettempdir()
            dir_path = os.path.join(temp_path, "dataplicity_remote")
            if not os.path.isdir(dir_path):
                os.mkdir(dir_path)
                log.debug("%r created %s", self, dir_path)
            snapshot_path = os.path.join(dir_path, upload_id)
            return snapshot_path
        except Exception as error:
            log.warning("unable to get snapshot path; %r", error)
            raise RemoteDirectoryError("Failed to get snapshot path")

    def add_upload(self, path, upload_id):
        # type: (Text, Text) -> int
        """Add a new upload.

        Args:
            path (str): Path to the file to upload relative to self.path
            upload_id (str): Upload ID.

        Raises:
            LowDiskSpace: If there is not enough disk space to create a snapshot (including margin)
            AddFail: If the upload could not be added for any reason.

        Returns:
            int: The size of the snapshot file (in bytes)
        """
        file_path = os.path.join(self.path, path)

        if not validate_path(file_path):
            raise IllegalPath("Path %s is illegal" % file_path)

        try:
            disk_usage = disk_tools.disk_usage(self.temp_path)
            file_size = snapshot_size = os.path.getsize(file_path)
            if disk_usage.used + file_size > disk_usage.total - FREE_SPACE_MARGIN:
                raise LowDiskSpace(
                    "not enough space on %s to create snapshot" % self.temp_path
                )
        except Exception as error:
            # Don't want to fail here, probably worth honoring the request
            log.warning("failed to get disk usage information; %s", error)

        snapshot_path = self.get_snapshot_path(upload_id)
        # Sanity check for path
        if not snapshot_path.startswith(self.temp_path):
            raise IllegalPath("Path %s is illegal" % path)

        try:

            # Copy file to temporary location, creating a "snapshot"
            shutil.copyfile(file_path, snapshot_path)
            snapshot_size = os.path.getsize(snapshot_path)
            return snapshot_size
        except Exception as error:
            log.error("failed to add_upload; %r", error)
            raise AddFail("Unable to add upload %r %r", file_path, upload_id)

    def read_upload(self, upload_id, offset, size):
        # type: (Text, int, int) -> bytes
        """Read data from the snapshot.

        Args:
            upload_id (str): Upload ID.
            offset (int): Offset in the file.
            size (int): Number of bytes to read.

        Raises:
            ReadFail: If the file could not be read from.

        Returns:
            bytes: Raw data from the file.
        """
        snapshot_path = self.get_snapshot_path(upload_id)
        try:
            with open(snapshot_path, "rb") as snapshot_file:
                snapshot_file.seek(offset)
                data = snapshot_file.read(size)
        except Exception as error:
            # Most likely, the snapshot file has been removed
            log.error("failed to read_upload; %r", error)
            raise ReadFail("unable to read %r" % upload_id)
        return data

    def close_upload(self, upload_id):
        # type: (Text) -> None
        """Close the upload and remove the snapshot file.

        Args:
            upload_id (str): Upload ID.
        """
        snapshot_path = self.get_snapshot_path(upload_id)
        if not os.path.exists(snapshot_path):
            # If its already been removed, this is a no-opp
            return
        try:
            os.remove(snapshot_path)
        except Exception as error:
            log.warning("failed to remove %r; %r", snapshot_path, error)

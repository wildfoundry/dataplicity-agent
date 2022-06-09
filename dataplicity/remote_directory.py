import logging
import shutil
import os
import os.path
import shutil
import tempfile
import typing

if typing.TYPE_CHECKING:
    from typing import Callable, Text

from . import disk_tools
from .directory_scanner import DirectoryScanner
from .m2m.packets import PacketType
from .m2m.wsclient import WSClient

# Amount of free space (bytes) to leave on disk
FREE_SPACE_MARGIN = 50 * 1000 * 1000


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


class TooManyCopies(RemoteDirectoryError):
    """Too many duplicate path"""


def validate_path(path):
    # type: (Text) -> bool
    """Check a path has no backrefs that may end up serving outside the remote directory root.

    Args:
        path (Text): A path.

    Returns:
        bool: True if the path is valid, otherwise False
    """
    return ".." not in path.split(os.sep)


class RemoteDirectory(object):
    """Manages remote directory."""

    def __init__(self, path, directory_scanner):
        # type: (Text, DirectoryScanner) -> None
        path = os.path.expanduser(path)
        self.path = os.path.abspath(path)
        self.directory_scanner = directory_scanner
        # Use /var/tmp if it exists as it is persistent
        self.temp_path = (
            "/var/tmp" if os.path.exists("/var/tmp") else tempfile.gettempdir()
        )

    def __repr__(self):
        # type: () -> Text
        return "RemoteDirectory(%r)" % self.path

    def scan(self, on_success=None):
        # type: (Callable[[], None]) -> None
        """Scan remote directory."""
        self.directory_scanner.perform_scan(on_success=on_success)

    def get_snapshot_path(self, upload_id):
        # type: (Text) -> Text
        """Get the path to a snapshot.

        Args:
            upload_id (str): Upload ID.

        Returns:
            str: A path to the snapshot file.
        """
        try:
            temp_path = self.temp_path
            dir_path = os.path.join(temp_path, "dataplicity_remote")
            if not os.path.isdir(dir_path):
                os.mkdir(dir_path)
                log.debug("%r created %s", self, dir_path)
            snapshot_path = os.path.join(dir_path, upload_id)
            return snapshot_path
        except Exception as error:
            log.warning("unable to get snapshot path; %r", error)
            raise RemoteDirectoryError("Failed to get snapshot path")

    def add_download(self, id):
        # type: (Text) -> Text
        """Add an upload.

        Args:
            id (str): The download ID

        Returns:
            [type]: [description]
        """

        temp_path = self.temp_path
        dir_path = os.path.join(temp_path, "dataplicity_remote_downloads")
        if not os.path.isdir(dir_path):
            os.mkdir(dir_path)
            log.debug("%r created %s", self, dir_path)

        device_path = os.path.join(dir_path, id)

        # Create the file
        # This could fail for a variety of reasons
        # Exceptions must be caught by the caller
        with open(device_path, "wb"):
            pass

        return device_path

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

        if path.startswith("\0"):
            if path == "\0scan.json":
                # Special file served from temp
                file_path = os.path.join(
                    tempfile.gettempdir(), "__dataplicity_remote_directory_scan___.json"
                )
            else:
                raise IllegalPath("Unknown special path; %r" % path)
        else:
            # Regular file in remote directory
            file_path = os.path.join(self.path, path.lstrip("/"))

            if not validate_path(file_path) or not file_path.startswith(self.path):
                raise IllegalPath("Path %s is illegal" % file_path)

        try:
            disk_usage = disk_tools.disk_usage(self.temp_path)
            file_size = os.path.getsize(file_path)
        except Exception as error:
            # Don't want to fail here, probably worth honoring the request
            log.warning("failed to get disk usage information; %s", error)
        else:
            if disk_usage.used + file_size > disk_usage.total - FREE_SPACE_MARGIN:
                raise LowDiskSpace(
                    "not enough space on %s to create snapshot" % self.temp_path
                )

        snapshot_path = self.get_snapshot_path(upload_id)
        # Sanity check for path
        if not snapshot_path.startswith(self.temp_path):
            raise IllegalPath("Path %s is illegal" % path)

        try:
            # Copy file to temporary location, creating a "snapshot"
            shutil.copyfile(file_path, snapshot_path)
            snapshot_size = os.path.getsize(snapshot_path)
            log.debug("created snapshot for %s; %s", file_path, snapshot_path)
            return snapshot_size
        except (IOError, OSError) as error:
            raise AddFail("Unable to open (%s)" % error.strerror)
        except Exception as error:
            log.error("failed to add_upload; %r", error)
            raise AddFail("Unable to open; %s" % error)

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
                log.debug("read %i bytes from %s", len(data), snapshot_path)
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
        # If its already been removed, this is a no-opp
        if os.path.exists(snapshot_path):
            try:
                os.remove(snapshot_path)
            except Exception as error:
                log.warning("failed to remove %r; %r", snapshot_path, error)

    def on_open_remote_file(self, client, upload_id, path):
        # type: (WSClient, bytes, bytes) -> None
        """Open remote file packet."""
        try:
            size = self.add_upload(path.decode("utf-8"), upload_id.decode("utf-8"))
        except RemoteDirectoryError as error:
            # Known fail that we can report to the user
            client.send(
                PacketType.open_remote_file_result,
                upload_id=upload_id,
                size=-1,
                fail=1,
                fail_reason=str(error),
            )
        except Exception as error:
            client.send(
                PacketType.open_remote_file_result,
                upload_id=upload_id,
                size=-1,
                fail=1,
                fail_reason="open failed, see dataplicity.log",
            )
            log.exception("failed to add upload")
        else:
            client.send(PacketType.open_remote_file_result, upload_id, size, 0, "")

    def on_close_remote_file(self, client, upload_id):
        # type: (WSClient, bytes) -> None
        """On close remote file packet."""
        try:
            self.close_upload(upload_id.decode("utf-8"))
        except Exception:
            log.exception("failed to close upload")

    def on_read_remote_file(self, client, upload_id, offset, size):
        # type: (WSClient, bytes, int, int) -> None
        try:
            data = self.read_upload(upload_id.decode("utf-8"), offset, size)
        except RemoteDirectoryError as error:
            client.send(
                PacketType.read_remote_file_result,
                upload_id=upload_id,
                offset=offset,
                size=size,
                data="",
                fail=1,
                fail_reason=str(error),
            )
        except Exception:
            log.exception("failed to read upload")
            client.send(
                PacketType.read_remote_file_result,
                upload_id=upload_id,
                offset=offset,
                size=size,
                data="",
                fail=1,
                fail_reason="read failed, see dataplicity.log",
            )
        else:
            client.send(
                PacketType.read_remote_file_result,
                upload_id=upload_id,
                offset=offset,
                size=size,
                data=data,
                fail=0,
                fail_reason="",
            )

    def on_write_remote_file(self, client, id, path, device_path, offset, data, final):
        # type: (WSClient, bytes, bytes, bytes, int, bytes, int) -> None
        """Write data from server to temporary file."""
        write_device_path = device_path.decode("utf-8")
        try:
            # If we haven't set a device_path allocate a temp location
            if not write_device_path:
                write_device_path = self.add_download(id.decode("utf-8"))
        except Exception as error:
            log.exception("error adding download")
            # Couldn't create temporary location, tell server
            client.send(
                PacketType.write_remote_file_result,
                id,
                device_path,
                1,
                str(error).encode("utf-8", "replace"),
            )
            return

        device_path = write_device_path.encode("utf-8")

        if data:
            try:
                # Write the data at the given offset
                log.debug("writing %i bytes to %s offset=%i", len(data), write_device_path, offset)
                with open(write_device_path, "r+b") as download_file:
                    download_file.seek(offset)
                    download_file.write(data)
            except Exception as error:
                # Error writing chunk, tell server
                log.exception("error writing download")
                client.send(
                    PacketType.write_remote_file_result,
                    id,
                    offset,
                    device_path,
                    2,
                    str(error).encode("utf-8", "replace"),
                )
                try:
                    log.debug("removing %s", write_device_path)
                    os.remove(write_device_path)
                except:
                    log.exception("failed to remove %r", write_device_path)
                return

        if final:
            try:
                client.remote_directory.copy_download(write_device_path, path)
            except Exception as error:
                log.exception("failed to copy download %s %s", write_device_path, path)
                client.send(
                    PacketType.write_remote_file_result,
                    id,
                    offset,
                    device_path,
                    3,
                    str(error).encode("utf-8", "replace"),
                )
                return

        # Return a success response
        client.send(
            PacketType.write_remote_file_result,
            id,
            offset + len(data),
            device_path,
            0,
            b"",
        )

    def copy_download(self, device_path, path):
        # type (Text, Text) -> None
        """Copy a download in to the remote directory"""

        destination_path = os.path.join(self.path, path.lstrip("/"))
        dirname, filename = os.path.split(destination_path)
        if not os.path.isdir(dirname):
            dirname = self.path

        basename, ext = os.path.splitext(filename)

        # If the foo.bar exists, try foo.copyN.bar, where N is an integer
        # N starts at 1 and will increase until it finds a free filename

        tries = 0
        while os.path.exists(destination_path):
            tries += 1
            if tries > 100:
                raise TooManyCopies(
                    "Can't find unique filename for %s" % destination_path
                )
            destination_path = "%s/%s(%s)%s" % (dirname, basename, tries, ext)

        log.debug("copying %s to %s", device_path, destination_path)
        try:
            os.rename(device_path, destination_path)
        except Exception:
            # Atomic rename didn't work, we will need to copy the data
            try:
                shutil.move(device_path, destination_path)
            except Exception:
                log.exception("unable to store download")
                raise

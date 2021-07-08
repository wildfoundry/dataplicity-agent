from __future__ import print_function


import logging
import os
import os.path
import time

from typing import Dict, Iterable, Iterator, List, Optional, Set, Tuple, TypedDict


try:
    # Scandir from stdlib in Python3
    from os import DirEntry, scandir
except ImportError:
    # Can't import scandir, so we will implement as much as we need
    # This will be less efficient, but will work

    from os.path import join
    from stat import S_ISDIR

    class DirEntry(object):  # type: ignore
        def __init__(self, path):
            # type(str) -> None
            self.path = path
            self.name = os.path.basename(self.path)
            self._stat = None

        def stat(self):
            # type() -> os.stat_result
            if self._stat is None:
                self._stat = os.stat(self.path)
            return self._stat

        def is_dir(self):
            # type: () -> bool
            return S_ISDIR(self.stat().st_mode)

        def is_file(self):
            # type: () -> bool
            return not S_ISDIR(self.stat().st_mode)

        def inode(self):
            # type: () -> int
            return self.stat().st_ino

    def scandir(dir_path):  # type: ignore
        # type(str) > Iterator[DirEntry]
        return iter(DirEntry(join(dir_path, path)) for path in os.listdir(dir_path))


FileInfo = Tuple[str, int]
DirectoryDict = TypedDict(
    "DirectoryDict", {"files": List[FileInfo], "dirs": List[str]}, total=False
)
ScanResult = TypedDict(
    "ScanResult",
    {"root": str, "time": float, "directories": Dict[str, DirectoryDict]},
)
_ScanStackEntry = Tuple[str, Iterable[DirEntry]]

log = logging.getLogger("agent")


class ScanDirectoryError(Exception):
    """Unable to scan the directory."""


def scan_directory(root_path, file_sizes=False, max_depth=10):
    # type: (str, bool, Optional[int]) -> ScanResult
    """Scan and serialize directory structure.

    Uses scandir to do this quite efficiently (without code recursion). Recursive links
    are detected and omitted.

    Returns a dict in the following format.

    {
        "root": <str: ABSOLUTE PATH>,
        "time": <float: EPOCH TIME>,
        "directories": {
            <str: RELATIVE PATH>: {
                "dirs" (optional): [<str: NAME>, ...],
                "files" (optional): [
                    (<str: NAME>, <int: FILESIZE>),
                    ...
                ]
            },
            ...
        }
    }

    Args:
        root_path (str): Root path
        file_sizes (boolean, optional): Add file sizes, defaults to False. If this is false, file sizes
            will be reported as -1
        max_depth (int, optional): Maximum number of depth of directory, defaults to 10

    Returns:
        dict: Serialized directory structure
    """
    root_path = os.path.abspath(os.path.expanduser(root_path))
    if not os.path.isdir(root_path):
        raise ScanDirectoryError("Can't scan %s; not a directory" % root_path)
    stack = []  # type: List[_ScanStackEntry]
    push = stack.append
    pop = stack.pop
    directories = {}  # type: Dict[str, DirectoryDict]
    visited_directories = set()  # type: Set[int]

    def push_directory(path):
        # type: (str) -> None
        """Push a new directory on to the stack."""
        scan_path = os.path.join(root_path, path)
        try:
            stack_entry = path, scandir(scan_path)
            push(stack_entry)
        except Exception as error:
            # Doesn't matter what the error is, log it and continue
            log.warning("error in scandir(%r); %s", scan_path, error)
        else:
            # This dict may contain "files" and "dirs", but are
            # omitted by default for brevity.
            directories[path] = {}

    scan_time = time.time()
    push_directory("")
    join = os.path.join
    while stack:
        path, scan = stack[-1]
        try:
            dir_entry = next(scan)
        except StopIteration:
            # End of directory scan, we can discard top of stack
            pop()
            continue
        if dir_entry.name.startswith("."):
            # Exclude hidden files and directories
            continue
        try:
            is_dir = dir_entry.is_dir()
        except Exception:
            is_dir = False

        try:
            is_file = dir_entry.is_file()
        except Exception:
            is_file = False

        if is_dir:
            if max_depth is not None and len(stack) >= max_depth:
                # Max depth reached, so skip this dir
                continue
            try:
                inode = dir_entry.inode()
            except Exception as error:
                log.warning("error in inode; %r", error)
            else:
                if inode in visited_directories:
                    # We have visited this directory before, we must have a recursive link
                    continue
                directories[path].setdefault("dirs", []).append(dir_entry.name)
                visited_directories.add(inode)
            push_directory(join(path, dir_entry.name))
        elif is_file:
            try:
                size = dir_entry.stat().st_size
            except Exception:
                size = -1
            file_info = (dir_entry.name, size) if file_sizes else (dir_entry.name, -1)
            directories[path].setdefault("files", []).append(file_info)

    scan_result = {
        "root": root_path,
        "time": scan_time,
        "directories": directories,
    }  # type: ScanResult
    return scan_result

from __future__ import print_function


import logging
import os
import os.path
import time

try:
    # Scandir from stdlib in Python3
    from os import DirEntry, scandir
except ImportError:
    # scandir from pypy on Python 2.7
    from scandir import DirEntry, scandir

from typing import Dict, Iterable, List, Optional, Set, Tuple, Union, TypedDict

FileInfo = Tuple[str, int]
DirectoryDict = TypedDict(
    "DirectoryDict", {"files": List[FileInfo], "dirs": List[str]}, total=False
)
ScanResult = TypedDict(
    "ScanResult", {"root": str, "time": float, "directories": Dict[str, DirectoryDict]},
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
        if dir_entry.is_dir():
            if max_depth is not None and len(stack) >= max_depth:
                # Max depth reached, so skip this dir
                continue
            inode = dir_entry.inode()
            if inode in visited_directories:
                # We have visited this directory before, we must have a recursive link
                continue
            directories[path].setdefault("dirs", []).append(dir_entry.name)
            visited_directories.add(inode)
            push_directory(join(path, dir_entry.name))
        elif dir_entry.is_file():
            file_info = (
                (dir_entry.name, dir_entry.stat().st_size)
                if file_sizes
                else (dir_entry.name, -1)
            )
            directories[path].setdefault("files", []).append(file_info)

    scan_result = {
        "root": root_path,
        "time": scan_time,
        "directories": directories,
    }  # type: ScanResult
    return scan_result

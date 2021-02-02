from __future__ import print_function


import logging
import os
import os.path
import time

try:
    from scandir import DirEntry, scandir
except ImportError:
    from os import DirEntry, scandir

from typing import Dict, List, Optional, Set, Tuple, TypedDict

FileInfo = Tuple[str, int]
DirectoryDict = TypedDict("DirectoryDict", {"files": List[FileInfo], "dirs": List[str]})
ScanResult = TypedDict(
    "ScanResult", {"root": str, "time": float, "directories": Dict[str, DirectoryDict]},
)
ScanStackEntry = Tuple[str, DirEntry]

log = logging.getLogger("agent")


class ScanDirectoryError(Exception):
    """Unable to scan the directory."""


def scan_directory(root_path, max_depth=10):
    # type: (str, Optional[int]) -> ScanResult
    """Scan and serialize directory structure.

    Uses scandir to do this quite efficiently (without code recursion). Recursive links 
    are detected and omitted.

    Returns a dict in the following format.

    {
        "root": <str: ABSOLUTE PATH>,
        "time": <float: EPOCH TIME>,
        "directories": {
            <str: RELATIVE PATH>: {
                "dirs": [<str: NAME>, ...],
                "files: [
                    (<str: NAME>, <int: FILESIZE>),
                    ...                    
                ]
            },
            ...
        }
    }

    Args:
        root_path (str): Root path

    Returns:
        dict: Serialized directory structure
    """
    if not os.path.isdir(root_path):
        raise ScanDirectoryError("Can't scan %s; not a directory", root_path)
    root_path = os.path.abspath(root_path)
    stack = []  # type: List[ScanStackEntry]
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
        except Exception:
            log.exception("error in os.scan(%s)", scan_path)
        else:
            directories[path] = {"files": [], "dirs": []}

    scan_time = time.time()
    push_directory("")
    join = os.path.join
    while stack:
        path, scan = stack[-1]
        try:
            dir_entry = next(scan)
        except StopIteration:
            pop()
        else:
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
                directories[path]["dirs"].append(dir_entry.name)
                visited_directories.add(inode)
                push_directory(join(path, dir_entry.name))
            elif dir_entry.is_file():
                file_info = (dir_entry.name, dir_entry.stat().st_size)
                directories[path]["files"].append(file_info)
    scan_result = {
        "root": root_path,
        "time": scan_time,
        "directories": directories,
    }  # type: ScanResult
    return scan_result


if __name__ == "__main__":
    import sys

    try:
        from rich import print
    except ImportError:
        pass

    start = time.time()
    scan = scan_directory(sys.argv[1])
    end_time = time.time()
    print(scan)
    print(len(scan["directories"]), "directories scanned")
    print("{:.1f}ms".format((end_time - start) * 1000))


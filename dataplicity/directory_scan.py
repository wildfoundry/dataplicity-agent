import logging
import os
import os.path
import time

import typing


if typing.TYPE_CHECKING:
    from typing import Dict, List, Optional, Set, Tuple, TypedDict, Iterable

    FileDict = TypedDict("FileDict", {"name": str, "size": int})
    DirectoryDict = TypedDict(
        "DirectoryDict", {"files": List[FileDict], "dirs": List[str]}
    )
    ScanResult = TypedDict(
        "ScanResult",
        {"root": str, "time": float, "directories": Dict[str, DirectoryDict]},
    )

log = logging.getLogger("agent")


def directory_scan(root_path, max_depth=10):
    # type: (str, Optional[int]) -> ScanResult
    """Scan and serialize directory structure.

    Uses scandir to do this quite efficiently (without code recursion). Recursive links 
    are detected and omitted.

    Returns a dict in the following format.

    {
        "root": <PATH>,
        "time": <EPOCH TIME>,
        "directories" [
            {
                "dirs": [<NAMES>, ...],
                "files: [
                    {
                        "name": <NAME>,
                        "size": <FILESIZE>
                    },
                    ...
                ]
            },
            ...
        ]
    }

    Args:
        root_path (str): Root path

    Returns:
        dict: Serialized directory structure
    """
    root_path = os.path.abspath(root_path)
    stack = []  # type: List[Tuple[str, Iterable[os.DirEntry]]]
    directories = {}  # type: Dict[str, DirectoryDict]
    visited_directories = set()  # type: Set[int]

    def push_directory(path):
        # type: (str) -> None
        """Push a new directory on to the stack."""
        scan_path = os.path.join(root_path, path)
        try:
            stack.append((path, iter(os.scandir(scan_path))))
        except Exception:
            log.exception("error in os.scan(%s)", scan_path)
        else:
            directories[path] = {"files": [], "dirs": []}

    scan_time = time.time()
    push_directory(".")

    while stack:
        path, iter_scan = stack[-1]
        try:
            dir_entry = next(iter_scan)
        except StopIteration:
            stack.pop()
        else:
            if dir_entry.name.startswith("."):
                # Exclude hidden files and directories
                continue
            if dir_entry.is_dir():
                if max_depth is not None and len(stack) >= max_depth:
                    # Max depth reach, so skip this dir
                    continue
                inode = dir_entry.inode()
                if inode in visited_directories:
                    # We have visited this directory before, we must have a recursive link
                    continue
                directories[path]["dirs"].append(dir_entry.name)
                visited_directories.add(inode)
                push_directory(path + "/" + dir_entry.name)
            elif dir_entry.is_file():
                file_dict = {
                    "name": dir_entry.name,
                    "size": dir_entry.stat().st_size,
                }  # type: FileDict
                directories[path]["files"].append(file_dict)
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
    scan = directory_scan(sys.argv[1])
    end_time = time.time()
    print(scan)
    print(len(scan["directories"]), "directories scanned")
    print("{:.1f}ms".format((end_time - start) * 1000))


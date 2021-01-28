import logging
import os
import os.path
import time

import typing

if typing.TYPE_CHECKING:
    from typing import Dict, List, Set, Tuple, Iterable
log = logging.getLogger("agent")


def directory_scan(root_path):
    # type: (str) -> dict
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

    directories = {}  # type: Dict[str, Dict]
    visited_directories = set()  # type: Set[int]

    def push_directory(path,):
        # type: (str) -> None
        """Push a new directory on to the stack."""
        scan_path = os.path.join(root_path, path)
        try:
            stack.append((path, iter(os.scandir(scan_path))))
        except Exception:
            log.exception("error in os.scan(%s)", scan_path)
        else:
            directories[path] = {"files": [], "dirs": []}

    push_directory(".")

    start_time = time.time()
    while stack:
        path, iter_scan = stack[-1]
        try:
            dir_entry = next(iter_scan)
        except StopIteration:
            stack.pop()
        else:
            if dir_entry.name.startswith("."):
                continue
            if dir_entry.is_dir():
                inode = dir_entry.inode()
                if inode not in visited_directories:
                    directories[path]["dirs"].append(dir_entry.name)
                    visited_directories.add(inode)
                    push_directory(path + "/" + dir_entry.name)
            elif dir_entry.is_file():
                directories[path]["files"].append(
                    {"name": dir_entry.name, "size": dir_entry.stat().st_size}
                )
    scan_result = {"root": root_path, "time": start_time, "directories": directories}
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


"""
Raspberry Pi specific tools.

"""

from __future__ import unicode_literals


def get_machine_revision():
    """
    Get the machine revision.

    A return value of None indicates an error (possibly because its
    not running on an RPI).
    Otherwise the return value is the revision code.

    """
    revision_code = None
    try:
        with open("/proc/cpuinfo", "rb") as fp:
            for line in fp:
                if b":" not in line:
                    continue
                key, _, value = line.partition(b":")
                key = key.strip().lower()
                value = value.strip().lower()
                if key == b"revision":
                    revision_code = value
                    break
    except IOError:
        return None
    else:
        if isinstance(revision_code, bytes):
            return revision_code.decode("utf-8")
        return revision_code

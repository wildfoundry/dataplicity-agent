from __future__ import unicode_literals

import platform

from . import rpi
from ._version import __version__


# Cache the meta dict because it never changes
_META_CACHE = None


def get_meta():
    """Get a dict containing device meta information."""
    global _META_CACHE
    if _META_CACHE is not None:
        return _META_CACHE.copy()
    meta = {}
    meta['agent_version'] = __version__
    meta['machine_type'] = rpi.get_machine_type()
    meta['os_version'] = get_os_version()
    meta['uname'] = get_uname()
    _META_CACHE = meta
    return meta


def get_uname():
    """Get uname."""
    # Preferable to running a system command
    uname = ' '.join(platform.uname())
    return uname


def get_os_version():
    """Get the OS version."""
    # Linux is a fair assumption for now
    distro = " ".join(platform.linux_distribution()).strip()
    return distro

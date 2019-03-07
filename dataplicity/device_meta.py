from __future__ import unicode_literals

import logging
import platform
import subprocess
import re

from .iptool import get_all_interfaces
from . import rpi
from ._version import __version__


log = logging.getLogger("agent")


# Cache the meta dict because it never changes
_META_CACHE = None

TAG_SCRIPT = "/opt/dataplicity/tuxtunnel/taglist.sh"


def get_meta():
    """Get a dict containing device meta information."""
    global _META_CACHE
    if _META_CACHE is not None:
        return _META_CACHE.copy()
    meta = {}
    meta["agent_version"] = __version__
    meta["machine_revision"] = rpi.get_machine_revision()
    meta["os_version"] = get_os_version()
    meta["uname"] = get_uname()
    meta["ip_list"] = get_ip_address_list()
    meta["tag_list"] = get_tag_list()
    _META_CACHE = meta
    return meta


def get_uname():
    """Get uname."""
    # Preferable to running a system command
    uname = " ".join(platform.uname())
    return uname


def get_os_version():
    """Get the OS version."""
    # Linux is a fair assumption for now
    distro = " ".join(platform.linux_distribution()).strip()
    return distro


def get_ip_address_list():
    # Get the ip addresses from all the interfaces
    try:
        interfaces = get_all_interfaces()
    except Exception:
        log.exception("unable to retrieve interface information")
        # Sorry for the pokemon exception, but I don't know how
        # reliable the call is, and if it fails what it will fail with.
        # It needs some exception handling or the whole get_meta call
        # will fail
        return []
    return [i[1] for i in interfaces]


def get_tag_list():
    """Run the taglist.sh script, get output as a list of tags"""
    try:
        output = subprocess.check_output(TAG_SCRIPT)
    except (OSError, subprocess.CalledProcessError) as error:
        log.error(error)
        return []

    # regex split on comma, spaces, newline and tabs
    tag_list = re.split(r"[,\s\n\t]", output)
    return [tag for tag in tag_list if tag != ""]

from __future__ import division
from collections import namedtuple

import os
import sys


sdiskusage = namedtuple("sdiskusage", ["total", "used", "free", "percent"])


def usage_percent(used, total, _round=None):
    """Calculate percentage usage of 'used' against 'total'."""
    try:
        ret = (used / total) * 100
    except ZeroDivisionError:
        ret = 0.0 if isinstance(used, float) or isinstance(total, float) else 0
    if _round is not None:
        return round(ret, _round)
    else:
        return ret


def disk_usage(path):
    """Return disk usage associated with path.
    Note: UNIX usually reserves 5% disk space which is not accessible
    by user. In this function "total" and "used" values reflect the
    total and used disk space whereas "free" and "percent" represent
    the "free" and "used percent" user disk space.
    Code from https://github.com/giampaolo/psutil/blob/master/psutil/_psposix.py
    """
    try:
        st = os.statvfs(path)
    except UnicodeEncodeError:
        if isinstance(path, unicode):
            # this is a bug with os.statvfs() and unicode on
            # Python 2, see:
            # - https://github.com/giampaolo/psutil/issues/416
            # - http://bugs.python.org/issue18695
            try:
                path = path.encode(sys.getfilesystemencoding())
            except UnicodeEncodeError:
                pass
            st = os.statvfs(path)
        else:
            raise

    # Total space which is only available to root (unless changed
    # at system level).
    total = st.f_blocks * st.f_frsize
    # Remaining free space usable by root.
    avail_to_root = st.f_bfree * st.f_frsize
    # Remaining free space usable by user.
    avail_to_user = st.f_bavail * st.f_frsize
    # Total space being used in general.
    used = total - avail_to_root
    # Total space which is available to user (same as 'total' but
    # for the user).
    total_user = used + avail_to_user
    # User usage percent compared to the total amount of space
    # the user can use. This number would be higher if compared
    # to root's because the user has less space (usually -5%).
    usage_percent_user = usage_percent(used, total_user, _round=1)

    # NB: the percentage is -5% than what shown by df due to
    # reserved blocks that we are currently not considering:
    # https://github.com/giampaolo/psutil/issues/829#issuecomment-223750462
    return sdiskusage(
        total=total, used=used, free=avail_to_user, percent=usage_percent_user
    )

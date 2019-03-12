from __future__ import unicode_literals

import subprocess
import re
import logging

log = logging.getLogger("agent")


TAG_SCRIPT = "/home/dataplicity/dataplicity_tags"


class TagException(Exception):
    """Custom exception raised when get_tag_list has an exception"""

    pass


def get_tag_list():
    """Run the dataplicity.tags script, get output as a list of tags"""
    try:
        output = subprocess.check_output(TAG_SCRIPT)
    except OSError:
        return []
    except Exception as error:
        log.error(error)
        raise TagException

    # regex split on comma, spaces, newline and tabs
    tag_list = re.split(r"[,\s\n\t]", output)
    return [
        tag.strip().decode("utf8", errors="ignore")[:25]
        for tag in tag_list
        if tag != ""
    ]

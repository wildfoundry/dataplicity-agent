from __future__ import unicode_literals

import os
import subprocess
import re
import logging

log = logging.getLogger("agent")


class TagError(Exception):
    """Custom exception raised when get_tag_list has an exception"""


def get_tag_list():
    """Run the dataplicity.tags script, get output as a list of tags"""

    home_dir = os.environ.get("HOME", "/home/dataplicity/")
    tag_executable = os.path.join(home_dir, "dataplicity_tags")

    # Early out if the script isn't there.
    if not os.path.exists(tag_executable):
        log.debug("tag executable %s does not exist", tag_executable)
        return []

    log.debug("reading tags from %s", tag_executable)
    try:
        output = subprocess.check_output(tag_executable)
    except OSError as error:
        log.debug("failed to run %s; %s", tag_executable, error)
        return []
    except Exception as error:
        log.error("error running %s; %s", tag_executable, error)
        raise TagError("error running %s" % tag_executable)

    str_output = output.decode("utf-8", errors="ignore")

    # regex split on comma, spaces, newline and tabs
    tag_list = re.split(r"[,\s\n\t]", str_output)
    tags = [tag.strip()[:25] for tag in tag_list if tag]
    return tags

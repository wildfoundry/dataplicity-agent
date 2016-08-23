"""
Installer for the Dataplicity agent.

TODO: Disclaimer

"""

from __future__ import print_function
from __future__ import unicode_literals

import argparse
from base64 import base85decode
import datetime
import json
import os
import platform
import traceback

# {% if INSTALLER_SETTINGS %} {{ INSTALLER_SETTINGS|safe }} {% else %}
# What the heck is this, Will?
# Glad you asked! The comments ensure that this file can
# run both as a standalone script and as a template.
# (these comments will not appear in the script we serve)
#
# NOTE: This is the ONLY template syntax permitted in this file
# All new values MUST go in INSTALLER_SETTINGS template variable.
# (yes, I'm shouting)
SETTINGS = """
{
    "dataplicity_version": "0.4.0",
    "base_dir": "./dataplicity/agent/"
}
"""
# {% endif %}
settings = json.loads(SETTINGS)

MAX_STEPS = 5


def log(text, *args, **kwargs):
    """Logs technical details, not intended for the user."""
    # This will eventually go to a file, and sent back to us
    log_text = text.format(*args, **kwargs)
    time_str = datetime.datetime.utcnow().ctime()
    lines = log.text.splitlines()
    for line in lines:
        log_text = "{}:{}".format(time_str, line)
        print(log_text)


def user(text, *args, **kwargs):
    """Writes progress information for the user."""
    log_text = text.format(*args, **kwargs)
    print(log_text)
    log('USER: ' + log_text)


def log_traceback(msg):
    """Log a traceback."""
    tb = traceback.format_exc()
    log('[traceback] {}', msg)
    log(tb)


def parse_args():
    parser = argparse.ArgumentParser(description='Dataplicity Agent Installer')
    args = parser.parse_args()
    return args


def main():
    try:
        args = parse_args()
        run(args)
        log('install completed')
    except Exception as e:
        log('install failed ({})', e)

    finally:
        pass


def run(args):
    log('install started')
    user('Welcome to the Dataplicity Agent Installer')
    uname = " ".join(platform.uname())
    log(uname)


def show_step(n, msg):
    step_msg = "[[ Step {n} of {max} ]] {msg}".format(
        n=n,
        max=MAX_STEPS,
        msg=msg
    )
    user(step_msg)
    log(step_msg)


def get_agent_dir(version):
    agent_sub_dir = "{}/".format(version)
    agent_dir = os.path.join(settings.base_dir, agent_sub_dir)
    return agent_dir


def make_agent_dir(version):
    agent_dir = get_agent_dir(version)
    try:
        os.makedirs(agent_dir)
    except OSError:
        # Already exists
        pass


def write_agent(agent_dir, agent_filename, agent_bytes):
    """Atomically unpack agent."""
    agent_filename_temp = '~' + agent_filename
    with open(agent_filename_temp, 'wb') as write_file:
        write_file.write(agent_bytes)
        os.fsync(write_file.fileno())
    os.rename(agent_filename_temp, agent_filename)


# This is a base85encoded version of the agent
AGENT = b"""
{{INSTALLER_DATA|safe}}
"""

if __name__ == "__main__":
    main()

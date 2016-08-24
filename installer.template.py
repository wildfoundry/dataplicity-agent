"""
Installer for the Dataplicity agent.

TODO: Disclaimer

"""

from __future__ import print_function
from __future__ import unicode_literals

import argparse
import base64
import datetime
import json
import os
import platform
import subprocess
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
    "agent_version": "0.4.0",
    "base_dir": "./__agent__/"
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
    lines = (log_text + '\n').splitlines()
    for line in lines:
        log_text = "[{}] {}".format(time_str, line)
        print(log_text)


def user(text, *args, **kwargs):
    """Writes progress information for the user."""
    log_text = text.format(*args, **kwargs)
    print(log_text)
    log('USER: ' + log_text)


def log_traceback(msg, *args, **kwargs):
    """Log a traceback."""
    tb = traceback.format_exc()
    log('[traceback]' + msg, *args, **kwargs)
    log(tb)


def make_dir(path):
    """Make a directory if it does not exist."""
    try:
        os.makedirs(path)
    except OSError:
        log('[make_dir] {} (exists)', path)
    else:
        log('[make_dir] {} (created)', path)


def parse_args():
    parser = argparse.ArgumentParser(description='Dataplicity Agent Installer')
    args = parser.parse_args()
    log("args={!r}", args)
    return args


def main():
    try:
        args = parse_args()
        run(args)
        log('install completed')
    except Exception as e:
        log_traceback('install failed ({})', e)
    finally:
        pass


def run(args):
    log('-' * 70)
    log('install started')
    log('')
    user('Welcome to the Dataplicity Agent Installer')

    distro = " ".join(platform.linux_distribution())
    log('[LINUX]')
    log('distro={}', distro)
    log('')

    system, node, release, version, machine, processor = platform.uname()

    log('[UNAME]')
    log('system={!r}', system)
    log('node={!r}', node)
    log('release={!r}', release)
    log('version={!r}', version)
    log('machine={!r}', machine)
    log('processor={!r}', processor)
    log('')

    log('[SETTINGS]')
    for k, v in settings.items():
        log('{}={!r}', k, v)
    log('')

    show_step(1, 'extracting agent')

    agent_dir = get_agent_dir()
    agent_path = write_agent(agent_dir, 'dataplicity')
    executable_path = get_executable_path()

    make_dir(agent_dir)
    link(agent_path, executable_path)
    make_executable(agent_path)


def show_step(n, msg):
    """Show current step information."""
    step_msg = "[[ Step {n} of {max} ]] {msg}".format(
        n=n,
        max=MAX_STEPS,
        msg=msg
    )
    user(step_msg)


def get_agent_dir():
    """Get the absolute directory where the agent will be stored."""
    agent_dir = os.path.abspath(
        os.path.join(
            settings['base_dir'],
            settings['agent_version']
        )
    )
    return agent_dir


def get_executable_path():
    """Get the absolute path of the dataplicity executable."""
    executable_path = os.path.abspath(
        os.path.join(
            settings['base_dir'],
            'dataplicity'
        )
    )
    return executable_path


def write_agent(agent_dir, agent_filename):
    """Atomically unpack agent, return agent path."""
    agent_bytes = base64.b64decode(AGENT)
    log('decoded agent {} bytes', len(agent_bytes))

    agent_filename_temp = '~' + agent_filename
    path = os.path.join(agent_dir, agent_filename)
    path_temp = os.path.join(agent_dir, agent_filename_temp)
    log('writing {}', path_temp)

    with open(path_temp, 'wb') as write_file:
        write_file.write(agent_bytes)
        os.fsync(write_file.fileno())

    log('renamed {}', path)
    os.rename(path_temp, path)

    return path


def link(agent_path, executable_path):
    """Link current version of agent."""
    executable_path_temp = executable_path + '~'
    os.symlink(agent_path, executable_path_temp)
    os.rename(executable_path_temp, executable_path)
    log("[link] {}", executable_path)


def make_executable(path):
    """Make a path executable."""
    os.chmod(path, 0o777)
    log('[make_executable] {}', path)


def apt_get(package):
    log('[apt_get] {}', package)
    retcode = subprocess.call(['apt-get', package])


# This is a b64encoded version of the agent
# {% if INSTALLER_DATA %}{% INSTALLER_DATA %}{% else %}
with open('bin/dataplicity', 'rb') as f:
    AGENT = base64.b64encode(f.read())
# {% endif %}

if __name__ == "__main__":
    main()

"""
Installer for the Dataplicity agent.

TODO: Disclaimer

"""

from __future__ import print_function
from __future__ import unicode_literals

import argparse
import base64
import datetime
import inspect
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
    "base_dir": "./__agent__/",
    "m2m_url": "wss://m2m.dataplicity.com",
    "api_url": "https://api.dataplicity.com",
    "dry_run": true
}
"""
# {% endif %}
settings = json.loads(SETTINGS)

SERIAL_PATH = '/opt/dataplicity/tuxtunnel/serial'
AUTH_PATH = '/opt/dataplicity/tuxtunnel/auth'
MAX_STEPS = 5


# A string template for the supervisor conf
SUPERVISOR_CONF_TEMPLATE = """

# Installed by Dataplicity Agent installer
[program:tuxtunnel]
environment=DATAPLICITY_M2M_URL="{M2M_URL}"
command={AGENT_PATH} --server-url {API_URL} run
autorestart=true
redirect_stderr=true
user=dataplicity
stdout_logfile=/var/log/tuxtunnel.log
stderr_logfile=/var/log/tuxtunnel.log

"""

LOG_PATH = "/var/log/ttagentinstall.log"
try:
    with open(LOG_PATH, 'wb'):
        pass
except IOError:
    # Probably means no permission
    pass
install_log = []


def log(text, *args, **kwargs):
    """Logs technical details, not intended for the user."""
    time_str = datetime.datetime.utcnow().ctime()
    caller = inspect.stack()[1][3]  # Get the caller function name
    log_text = text.format(*args, **kwargs)
    lines = (log_text + '\n').splitlines()

    write_lines = '\n'.join(
        "[{}] {}: {}".format(time_str, caller, line)
        for line in lines
    )

    if settings['dry_run']:
        print(write_lines)
    else:
        try:
            with open(LOG_PATH, 'a') as log_file:
                log_file.write(write_lines)
        except IOError as e:
            print(e)
            pass


def user(text, *args, **kwargs):
    """Writes progress information for the user."""
    log_text = text.format(*args, **kwargs)
    print(log_text)
    log(log_text)


def log_traceback(msg, *args, **kwargs):
    """Log a traceback."""
    tb = traceback.format_exc()
    log(msg, *args, **kwargs)
    log(tb)


def make_dir(path):
    """Make a directory if it does not exist."""
    try:
        os.makedirs(path)
    except OSError:
        log('{} (exists)', path)
    else:
        log('{} (created)', path)


def parse_args():
    """Parse command line."""
    parser = argparse.ArgumentParser(description='Dataplicity Agent Installer')
    parser.add_argument('--no-dry', action="store_true", default=False,
                        help="Do not dry run")
    parser.add_argument('--non-interactive', action="store_true", default=False,
                        help="Do not prompt the user")
    args = parser.parse_args()
    log("args={!r}", args)

    if args.no_dry:
        settings['dry_run'] = False
    return args


def main():
    """Main entry point."""
    log('-' * 70)
    log('install started')
    log('')
    try:
        args = parse_args()
        run(args)
        log('install completed')
    except Exception as e:
        log_traceback('install failed ({})', e)
    finally:
        pass


def run(args):
    """Top level procedural code to install agent."""

    user('Welcome to the Dataplicity Agent Installer')
    log_info()

    # ------------------------------------------------------------------
    show_step(1, 'extracting agent')
    agent_dir = get_agent_dir()
    make_dir(agent_dir)
    agent_path = write_agent(agent_dir, 'dataplicity')
    executable_path = get_executable_path()
    link(agent_path, executable_path)
    make_executable(agent_path)

    # ------------------------------------------------------------------
    show_step(2, "creating environment")
    create_user()

    # ------------------------------------------------------------------
    show_step(3, "installing supervisor")
    apt_get('supervisor')
    install_supervisor_conf()

    # ------------------------------------------------------------------
    show_step(4, "starting agent")
    if not settings['dry_run']:
        run_system('service', 'supervisor', 'restart')
    # TODO: Poll for version file

    # ------------------------------------------------------------------
    congratulations('TODO: URL')


def log_info():
    """Log useful system information."""
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
    log("{}", executable_path)


def make_executable(path):
    """Make a path executable."""
    os.chmod(path, 0o777)
    log(path)


def run_system(*command):
    """
    Run a system command, log output, and return a boolean indicating
    success.

    """
    command_line = ' '.join(command)
    log('run "{}"', command_line)
    try:
        output = subprocess.check_output(command)
        returncode = 0
    except subprocess.CalledProcessError as e:
        output = e.output
        returncode = e.returncode
    log(output)
    log('"{}" returned={}', command_line, returncode)
    return returncode == 0


def apt_get(package):
    """Install an apt-get package."""
    log('installing package {}', package)
    if settings['dry_run']:
        return
    return run_system('apt-get', 'install', package)


def install_supervisor_conf():
    """Install supervisor conf."""
    agent_path = get_executable_path()
    format_args = {
        "M2M_URL": settings['m2m_url'],
        "API_URL": settings['api_url'],
        "AGENT_PATH": agent_path
    }
    conf = SUPERVISOR_CONF_TEMPLATE.format(**format_args)

    log('writing supervisor conf')
    log(conf)
    log('')

    if settings['dry_run']:
        return

    with open('/etc/supervisor/conf.d/tuxtunnel.conf', 'wt') as f:
        f.write(conf)


def create_user():
    """Create a dataplicity user and apply the appropriate permissions."""

    log('creating user')
    if settings['dry_run']:
        return

    run_system('useradd', 'dataplicity')

    dataplicity_sudoer =\
        'dataplicity ALL=(ALL) NOPASSWD: /sbin/reboot'

    with open('/etc/sudoers', 'rt') as sudoers_file:
        lines = sudoers_file.read().splitlines()

    log('adding "{}" to sudoers', dataplicity_sudoer)

    if dataplicity_sudoer in lines:
        log('sudoer line present')
    else:
        log('adding sudoer line')
        try:
            with open('/etc/sudoers', 'at') as sudoers_file:
                sudoers_file.append("\n{}\n".format(dataplicity_sudoer))
        except IOError as e:
            log('unable to write to sudoers file ({})', e)


def congratulations(device_url):
    """Tell the user about install."""
    user('')
    user('Dataplicity agent is now installed!')
    user('Your device will be online in a few seconds')
    user(
        'Visit {device_url} to manage your device',
        device_url=device_url
    )


# This is a b64encoded version of the agent
# {% if INSTALLER_DATA %}{% INSTALLER_DATA %}{% else %}
with open('bin/dataplicity', 'rb') as f:
    AGENT = base64.b64encode(f.read())
# {% endif %}

if __name__ == "__main__":
    main()

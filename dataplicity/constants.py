from __future__ import print_function
from __future__ import unicode_literals

from os import environ


def get_environ_int(name, default):
    """Get an integer from the environment.

    Args:
        name (str): environment variable name
        default (int): Default if env var doesn't exist or not an integer

    Returns:
        int: Integer value of env var.
    """
    try:
        value = int(environ.get(name, default))
    except ValueError:
        return default


CONF_PATH = "/etc/dataplicity/dataplicity.conf"
SERVER_URL = environ.get("DATAPLICITY_API_URL", "https://api.dataplicity.com")
M2M_URL = environ.get("DATAPLICITY_M2M_URL", "wss://m2m.dataplicity.com/m2m/")
SERIAL_LOCATION = "/opt/dataplicity/tuxtunnel/serial"
AUTH_LOCATION = "/opt/dataplicity/tuxtunnel/auth"

# Client will reconnect if the server hasn't responded in this time
MAX_TIME_SINCE_LAST_PACKET = 100.0  # seconds or None

# Number of bytes to read at a time, when copying date over the network
# TODO: Replace this with a sensible chunk size once we identify the
# issue with ssh over Porthole
CHUNK_SIZE = 1024 * 1024

# Maximum number of services (port forward/commands/file etc)
LIMIT_SERVICES = get_environ_int("DATAPLICITY_LIMIT_SERVICES", 500)

# Maximum number of terminals (separate pool from services)
LIMIT_TERMINAL = get_environ_int("DATAPLICITY_LIMIT_TERMINAL", 100)

#  Server bust HTTP response
SERVER_BUSY = b"""HTTP/1.x 503 Server busy\r\n\r
The device is under heavy load and could not return a response.

Try increasing DATAPLICITY_LIMIT_SERVICES
"""

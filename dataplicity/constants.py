from __future__ import print_function
from __future__ import unicode_literals

from os import environ

CONF_PATH = "/etc/dataplicity/dataplicity.conf"
SERVER_URL = environ.get('DATAPLICITY_API_URL', "https://api.dataplicity.com")
M2M_URL = environ.get('DATAPLICITY_M2M_URL', "wss://m2m.dataplicity.com/m2m/")
SERIAL_LOCATION = '/opt/dataplicity/tuxtunnel/serial'
AUTH_LOCATION = '/opt/dataplicity/tuxtunnel/auth'

# Client will reconnect if the server hasn't responded in this time
MAX_TIME_SINCE_LAST_PACKET = 100.0  # seconds or None

# Number of bytes to read at a time, when copying date over the network
# TODO: Replace this with a sensible chunk size once we identify the
# issue with ssh over Porthole
CHUNK_SIZE = 1024 * 1024

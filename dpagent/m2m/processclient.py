"""

A test for remote process

"""

from __future__ import unicode_literals
from __future__ import print_function

from ..compat import raw_input

import sys

import logging
logging.basicConfig(level=logging.CRITICAL)

from .wsclient import WSClient

client = WSClient('ws://127.0.0.1:8888/m2m/', uuid=b"4bd59854-6a74-11e4-98eb-67c713d6435e")
client.start()

print("connecting")

uuid = client.wait_ready()
if uuid is None:
    print("failed to connect")
    sys.exit(-1)

print("{{{uuid}}}".format(uuid=uuid))
raw_input('Hit return when ready')


import time

try:
    channel = client.get_channel(1)
    while 1:
        while 1:
            data = channel.read(1024)
            if not data:
                break
            sys.stdout.write(data)
            sys.stdout.flush()
        time.sleep(0.1)

finally:
    client.close()

"""

IP related tools.

"""

import array
import fcntl
import socket
import struct
import sys

from .compat import PY3

# Maximum number of interfaces to return
MAX_INTERFACES = 100


def get_all_interfaces():
    """
    Returns a list of tuples, giving the network name and ipv4 address
    [('lo', '127.0.0.1'), ('eth0', '10.0.2.15'), ('eth1', '192.168.33.10')]

    Uses https://linux.die.net/man/7/netdevice system call

    May raise an IOError if platform is unsupported
    """
    _is_64bits = sys.maxsize > 2**32
    struct_size = 40 if _is_64bits else 32

    if_buffer = array.array("B", b"\0" * MAX_INTERFACES * struct_size)
    if_pointer, buffer_size = if_buffer.buffer_info()

    _socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        fh = _socket.fileno()
        ifaces_bytes = fcntl.ioctl(
            fh, 0x8912, struct.pack("iL", buffer_size, if_pointer)  # SIOCGIFCONF
        )
        if_buffer_size, _pointer = struct.unpack("iL", ifaces_bytes)

    finally:
        _socket.close()

    try:
        # tostring() was renamed to tobytes() in Python3.2
        ifaces = if_buffer.tobytes()
    except AttributeError:
        ifaces = if_buffer.tostring()

    interfaces = []
    for offset in range(0, if_buffer_size, struct_size):
        _iface = ifaces[offset : offset + struct_size]
        name, _, _ = _iface.partition(b"\0")
        ip = socket.inet_ntoa(_iface[20:24])  # struct sockaddr ifr_hwaddr;
        if not PY3:
            ip = ip.decode("utf-8")
        interfaces.append((name.decode("ascii", "replace"), ip))

    return interfaces


if __name__ == "__main__":
    # python -m dataplicity.iptools
    for name, ip in get_all_interfaces():
        print("{}\t{}".format(name, ip))

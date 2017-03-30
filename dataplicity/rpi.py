"""
Raspberry Pi specific tools.

"""

from __future__ import unicode_literals


RPI_REVISIONS = {
    'beta': 'rpi_1b',
    '0002': 'rpi_1b',
    '0003': 'rpi_1b',
    '0004': 'rpi_1b',
    '0005': 'rpi_1b',
    '0006': 'rpi_1b',
    '0007': 'rpi_1a',
    '0008': 'rpi_1a',
    '0009': 'rpi_1a',
    '000d': 'rpi_1b',
    '000e': 'rpi_1b',
    '000f': 'rpi_1b',
    '0010': 'rpi_1b_plus',
    '0011': 'rpi_cm',
    '0012': 'rpi_1a_plus',
    '0013': 'rpi_1b_plus',
    'a01041': 'rpi_2b',
    'a21041': 'rpi_2b',
    '900092': 'rpi_0',
    'a02082': 'rpi_3b',
    'a22082': 'rpi_3b',
    'a220a0': 'rpi_3_cm',
}


def get_machine_type():
    """
    Get the machine type.

    A return value of empty string ('') means 'unknown'.
    A return value of None indicates an error (possibly because its
    not running on an RPI).
    Otherwise the return value is one of the possible Dataplicity
    machine type constants.

    """
    rpi_version = None
    try:
        with open('/proc/cpuinfo', 'rb') as fp:
            for line in fp:
                if ':' not in line:
                    continue
                key, _, value = line.partition(':')
                key = key.strip().lower()
                value = value.strip().lower()
                if key == 'revision':
                    rpi_version = RPI_REVISIONS.get(value, '')
                    break
    except IOError:
        return None
    else:
        return rpi_version

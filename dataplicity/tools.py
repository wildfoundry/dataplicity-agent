from __future__ import unicode_literals
from __future__ import print_function


def resolve_value(value):
    """resolve a value which may have a file: prefix"""
    if value is None:
        return value
    value = value.strip()
    if value.startswith('file:'):
        path = value.split(':', 1)[-1]
        try:
            with open(path, 'rt') as f:
                value = f.read().strip()
        except IOError:
            value = None

    return value

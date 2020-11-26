"""
A threadsafe counter object with a maximum count.

This is to manage resources with a maximum limit.

"""

from threading import Lock


class CounterError(Exception):
    """Base class for counter errors."""


class CounterMax(Exception):
    """Count has reached the maximum"""


class Counter(object):
    """A thread safe counter."""

    def __init__(self, max_count=100):
        self._lock = Lock()
        self._value = 0
        self._max_count = max_count

    def increment(self):
        """Increment the count, get the new count."""
        with self._lock:
            if self._value == self._max_count:
                raise CounterMax("Max count reached")
            self._value += 1
            return self._value

    def decrement(self):
        """Decrement the count, get the new count."""
        with self._lock:
            if self._value <= 0:
                raise CounterError("Counter can't be decremented below 0")
            self._value -= 1
            return self._value


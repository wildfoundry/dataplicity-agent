"""
A threadsafe object to enforce limits.

Similar in purpose to a Semaphore, but simpler because we never want to block. 

"""

from threading import Lock


class LimiterError(Exception):
    """Base class for counter errors."""


class LimitReached(Exception):
    """Count has reached the maximum"""


class Limiter(object):
    """A thread safe counter."""

    def __init__(self, limit):
        self._lock = Lock()  # Doesn't need to be re-entrant
        self._limit = limit
        self._value = 0

    def increment(self):
        """Increment the count.
        
        Raises a LimitReached exception if the increment would go above the limit.        
        """
        with self._lock:
            if self._value >= self._limit:
                raise LimitReached("Max count reached")
            self._value += 1

    def decrement(self):
        """Decrement the count."""
        with self._lock:
            if self._value <= 0:
                # If this occurs it indicates a bug in the caller
                raise LimiterError("Counter can't be decremented below 0")
            self._value -= 1


"""
A threadsafe object to enforce limits.

Similar in purpose to a Semaphore, but simpler because we never want to block. 

"""
from contextlib import contextmanager
from threading import RLock


class LimiterError(Exception):
    """Base class for counter errors."""


class LimitReached(Exception):
    """Count has reached the maximum"""


@contextmanager
def limiter_context(limiter):
    # Increment the counter
    limiter.increment()
    with limiter._lock:
        try:
            # run setup code, while locked
            yield
        except Exception:
            # Decrement counter if any errors
            limiter.decrement()
            raise


class Limiter(object):
    """A thread safe counter."""

    def __init__(self, limit, name):
        self._lock = RLock()
        self._limit = limit
        self.name = name
        self._value = 0

    def __enter__(self):
        """Countext manager to increment limiter and decrement on error."""
        return limiter_context(self)

    def increment(self):
        """Increment the count.
        
        Raises a LimitReached exception if the increment would go above the limit.        
        """
        with self._lock:
            if self._value >= self._limit:
                raise LimitReached(
                    "{} limit ({}) reached".format(self.name, self._limit)
                )
            self._value += 1

    def decrement(self):
        """Decrement the count."""
        with self._lock:
            if self._value <= 0:
                # If this occurs it indicates a bug in the caller
                raise LimiterError("Counter can't be decremented below 0")
            self._value -= 1


"""
A threadsafe object to enforce limits.

Similar in purpose to a Semaphore, but simpler because we never want to block. 

"""
from contextlib import contextmanager
import logging
from threading import RLock

log = logging.getLogger("m2m")


class LimiterError(Exception):
    """Base class for counter errors."""


class LimitReached(Exception):
    """Count has reached the maximum"""


@contextmanager
def limiter_context(limiter):
    """Context manager which increments the limiter, and decrements if there is an error."""
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
    """A thread safe counter with an upper limit."""

    def __init__(self, name, limit):
        """Create limiter object.

        Args:
            name (str): Name of limiter (used in error messages)
            limit (int): Upper limit.
        """
        assert limit > 0
        self._lock = RLock()
        self.name = name
        self._limit = limit
        self._value = 0

    def __repr__(self):
        return "<limiter {!r} {}/{}>".format(self.name, self._value, self._limit)

    def __call__(self):
        """Countext manager to increment limiter and decrement on error."""
        return limiter_context(self)

    def increment(self):
        """Increment the count.

        Raises a LimitReached exception if the increment would go above the limit.
        """
        with self._lock:
            if self._value >= self._limit:
                log.warning("%r reached limit", self)
                raise LimitReached(
                    "{} limit ({}) reached".format(self.name, self._limit)
                )
            self._value += 1
            log.debug("%r incremented", self)

    def decrement(self):
        """Decrement the count."""
        with self._lock:
            if self._value <= 0:
                # If this occurs it indicates a bug in the caller
                raise LimiterError("Counter can't be decremented below 0")
            self._value -= 1
            log.debug("%r decremented", self)

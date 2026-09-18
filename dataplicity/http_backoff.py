"""HTTP Retry-After parsing and sleep helpers (Python 2.7+)."""

from __future__ import print_function
from __future__ import unicode_literals

import calendar
import logging
import random
import time

from email.utils import parsedate

log = logging.getLogger("agent.http_backoff")

# Status codes that should honour Retry-After and retry.
RETRYABLE_STATUS = frozenset((429, 502, 503, 504))

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MAX_BACKOFF = 300.0
DEFAULT_BASE_BACKOFF = 1.0


def parse_retry_after(value, now=None):
    """
    Parse a Retry-After header value.

    Accepts delta-seconds or an HTTP-date. Returns seconds to wait (>= 0),
    or None if the value cannot be parsed.
    """
    if value is None:
        return None
    try:
        text = value.decode("ascii", "ignore") if isinstance(value, bytes) else value
    except Exception:
        text = value
    if text is None:
        return None
    text = str(text).strip()
    if not text:
        return None

    try:
        seconds = float(text)
        if seconds < 0:
            return 0.0
        return seconds
    except (TypeError, ValueError):
        pass

    try:
        parsed = parsedate(text)
        if not parsed:
            return None
        target = calendar.timegm(parsed)
        if now is None:
            now = time.time()
        return max(0.0, float(target) - float(now))
    except Exception:
        return None


def compute_backoff_seconds(
    attempt,
    retry_after_header=None,
    base=DEFAULT_BASE_BACKOFF,
    maximum=DEFAULT_MAX_BACKOFF,
    jitter=True,
):
    """
    Combine Retry-After (when present) with exponential backoff + optional jitter.

    ``attempt`` is 1-based (first retry after a failure is attempt=1).
    """
    exp = min(maximum, max(base, base * (2 ** max(0, int(attempt) - 1))))
    header_delay = parse_retry_after(retry_after_header)
    delay = exp if header_delay is None else max(exp, header_delay)
    delay = min(maximum, delay)
    if jitter and delay > 0:
        delay = delay + random.uniform(0.0, min(1.0, delay * 0.1))
    return delay


def sleep_backoff(seconds):
    """Sleep for ``seconds`` (no-op when <= 0)."""
    try:
        delay = float(seconds)
    except (TypeError, ValueError):
        return
    if delay > 0:
        log.debug("backing off for %.2fs", delay)
        time.sleep(delay)

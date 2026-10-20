"""Long backoff for deleted-device / revoked-token auth failures.

Mirrors remote-desktop PR #48: on auth failure jump to a 5 minute floor
and grow up to 1 hour, honouring a larger Retry-After when present.
"""

from __future__ import print_function
from __future__ import unicode_literals

import calendar
import logging
import random
import time
from email.utils import parsedate

from .compat import HTTPError

log = logging.getLogger("agent")

# JSON-RPC device.check_auth messages for gone / revoked credentials.
AUTH_FAILURE_MESSAGES = frozenset(
    (
        "authorization failed",
        "invalid credentials",
        "unknown device",
    )
)
AUTH_FAILURE_STATUS = frozenset((401, 403, 404))
DEFAULT_AUTH_BACKOFF = 300.0
DEFAULT_AUTH_MAX_BACKOFF = 3600.0

try:
    _monotonic = time.monotonic
except AttributeError:  # pragma: no cover - Python < 3.3
    _monotonic = time.time


def parse_retry_after(value, now=None):
    """Parse Retry-After as delta-seconds or HTTP-date. Returns seconds >= 0, or None."""
    if not value:
        return None
    val = str(value).strip()
    if not val:
        return None
    try:
        return max(0.0, float(val))
    except (TypeError, ValueError):
        pass
    try:
        parsed = parsedate(val)
        if not parsed:
            return None
        stamp = calendar.timegm(parsed)
        if now is None:
            now = time.time()
        return max(0.0, stamp - float(now))
    except Exception:
        return None


def compute_auth_backoff_seconds(
    attempt,
    retry_after_header=None,
    base=DEFAULT_AUTH_BACKOFF,
    maximum=DEFAULT_AUTH_MAX_BACKOFF,
    jitter=True,
):
    """Exponential auth backoff. ``attempt`` is 1-based."""
    exp = min(maximum, max(base, base * (2 ** max(0, int(attempt) - 1))))
    header_delay = parse_retry_after(retry_after_header)
    delay = exp if header_delay is None else max(exp, header_delay)
    delay = min(maximum, delay)
    if jitter and delay > 0:
        delay = delay + random.uniform(0.0, min(1.0, delay * 0.1))
    return delay


def header_retry_after(headers):
    if not headers:
        return None
    try:
        return headers.get("Retry-After") or headers.get("retry-after")
    except Exception:
        return None


def is_auth_failure_status(status_code):
    if status_code is None:
        return False
    try:
        return int(status_code) in AUTH_FAILURE_STATUS
    except Exception:
        return False


def is_auth_failure_message(message):
    if not message:
        return False
    try:
        return str(message).strip().lower() in AUTH_FAILURE_MESSAGES
    except Exception:
        return False


def is_auth_failure_exception(exc):
    """True when the server says the device/token is gone or unauthorized."""
    if exc is None:
        return False

    # JSON-RPC RemoteError / RemoteMethodError from device.check_auth
    message = getattr(exc, "message", None)
    if message is None and hasattr(exc, "args") and exc.args:
        message = exc.args[0]
    if is_auth_failure_message(message):
        return True

    # HTTP 401/403/404 wrapped by JSONRPC as ServerUnreachableError
    original = getattr(exc, "original", None)
    if isinstance(original, HTTPError):
        return is_auth_failure_status(getattr(original, "code", None))
    if isinstance(exc, HTTPError):
        return is_auth_failure_status(getattr(exc, "code", None))
    return False


def retry_after_from_exception(exc):
    """Best-effort Retry-After from an HTTPError (direct or wrapped)."""
    if exc is None:
        return None
    original = getattr(exc, "original", None)
    for candidate in (original, exc):
        if isinstance(candidate, HTTPError):
            headers = getattr(candidate, "headers", None)
            return header_retry_after(headers)
    return None


class AuthBackoffGate:
    """Gate associate / sync attempts after deleted-device auth failures."""

    def __init__(
        self,
        base=DEFAULT_AUTH_BACKOFF,
        maximum=DEFAULT_AUTH_MAX_BACKOFF,
    ):
        self.base = float(base)
        self.maximum = float(maximum)
        self.attempt = 0
        self.next_mono = 0.0

    def ready(self, now=None):
        if now is None:
            now = _monotonic()
        return float(now) >= self.next_mono

    def record_success(self, now=None):
        if now is None:
            now = _monotonic()
        self.attempt = 0
        self.next_mono = float(now)
        return 0.0

    def record_auth_failure(self, retry_after_header=None, now=None, jitter=True):
        """Long backoff for auth failures (5m floor, 1h cap by default)."""
        if now is None:
            now = _monotonic()
        now = float(now)
        self.attempt += 1
        delay = compute_auth_backoff_seconds(
            self.attempt,
            retry_after_header,
            base=self.base,
            maximum=self.maximum,
            jitter=jitter,
        )
        self.next_mono = now + delay
        return delay

    def reset(self):
        self.attempt = 0
        self.next_mono = 0.0

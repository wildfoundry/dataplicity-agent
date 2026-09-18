"""
Persistent m2m websocket reconnect with exponential back-off.

The pinned lomond already waits between reconnects, but older builds capped
at 30s and could still feel like a reconnect storm under auth failure /
router stress. This wrapper uses the agent's own min/max wait so every failed
connect backs off locally, with a hard floor of 1 second (never immediate).

If the server already sends Retry-After on a rejected upgrade (router unnamed
IP block, etc.), we honour it as a floor — but we never require it. Auth
failures on the JSON-RPC side remain HTTP 200 errors; those are throttled in
``M2MManager.set_identity``, not via Retry-After.
"""

from __future__ import print_function
from __future__ import unicode_literals

from email.utils import mktime_tz, parsedate_tz
from random import random
import logging
import threading
import time

from lomond import events

from .. import constants


log = logging.getLogger("m2m")


def _parse_retry_after(value):
    """Parse a Retry-After header when present; return None if absent/invalid."""
    if value is None:
        return None
    try:
        value = value.decode("ascii", "ignore") if isinstance(value, bytes) else value
    except Exception:
        pass
    value = str(value).strip()
    if not value:
        return None
    try:
        retry_after = float(value)
    except ValueError:
        parsed = parsedate_tz(value)
        if parsed is None:
            return None
        retry_after = mktime_tz(parsed) - time.time()
    if retry_after < 0:
        return 0.0
    return retry_after


def persist(
    websocket,
    poll=5,
    min_wait=None,
    max_wait=None,
    ping_rate=None,
    ping_timeout=None,
    exit_event=None,
):
    """Run a websocket with local exponential back-off after every disconnect.

    Same yield contract as ``lomond.persist.persist``. The wait always happens
    from local constants; Retry-After only raises the floor when already set.
    """
    if min_wait is None:
        min_wait = constants.M2M_RECONNECT_MIN_WAIT
    if max_wait is None:
        max_wait = constants.M2M_RECONNECT_MAX_WAIT
    if ping_rate is None:
        ping_rate = constants.M2M_PING_RATE
    if ping_timeout is None:
        ping_timeout = constants.M2M_PING_TIMEOUT
    if exit_event is None:
        exit_event = threading.Event()

    # Never reconnect immediately — even a mis-set env var of 0 must wait.
    min_wait = max(1.0, float(min_wait))
    max_wait = max(min_wait, float(max_wait))

    retries = 0
    random_wait = max(0.0, float(max_wait) - float(min_wait))
    while True:
        retries += 1
        retry_after = None
        for event in websocket.connect(
            poll=poll, ping_rate=ping_rate, ping_timeout=ping_timeout
        ):
            if event.name == "ready":
                retries = 0
            elif event.name == "rejected":
                response = getattr(event, "response", None)
                if response is not None:
                    retry_after = _parse_retry_after(response.get("retry-after"))
                status = getattr(response, "status_code", None) if response else None
                log.warning(
                    "m2m websocket upgrade rejected (status=%s): %s",
                    status,
                    getattr(event, "reason", ""),
                )
            yield event

        # Always wait locally. Optional Retry-After only lengthens the wait.
        wait_for = float(min_wait) + random() * min(random_wait, 2 ** retries)
        if retry_after is not None:
            wait_for = max(wait_for, float(retry_after))
        wait_for = max(float(min_wait), min(float(max_wait), wait_for))
        log.info("m2m reconnect back-off %.1fs (attempt %s)", wait_for, retries)
        yield events.BackOff(wait_for)
        if exit_event.wait(wait_for):
            break

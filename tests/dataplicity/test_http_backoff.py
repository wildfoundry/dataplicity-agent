from __future__ import print_function
from __future__ import unicode_literals

import time
from email.utils import formatdate

from dataplicity import http_backoff


def test_parse_retry_after_seconds():
    assert http_backoff.parse_retry_after("12") == 12.0
    assert http_backoff.parse_retry_after("0") == 0.0
    assert http_backoff.parse_retry_after("") is None
    assert http_backoff.parse_retry_after(None) is None


def test_parse_retry_after_http_date():
    future = time.time() + 30
    header = formatdate(timeval=future, usegmt=True)
    delay = http_backoff.parse_retry_after(header, now=time.time())
    assert delay is not None
    assert 25.0 <= delay <= 35.0


def test_compute_backoff_prefers_header_when_larger():
    delay = http_backoff.compute_backoff_seconds(
        1, retry_after_header="45", base=1.0, maximum=300, jitter=False
    )
    assert delay == 45.0


def test_compute_backoff_without_header_uses_exponential():
    delay = http_backoff.compute_backoff_seconds(
        3, retry_after_header=None, base=1.0, maximum=300, jitter=False
    )
    assert delay == 4.0

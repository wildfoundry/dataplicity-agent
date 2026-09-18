from __future__ import print_function
from __future__ import unicode_literals

import json
import logging

from . import constants
from .compat import HTTPError, Request, urlopen, text_type, quote
from .http_backoff import (
    RETRYABLE_STATUS,
    compute_backoff_seconds,
    sleep_backoff,
)


log = logging.getLogger("agent")


def _header_get(headers, name):
    """Read a header from urllib response/error headers (Py2 + Py3)."""
    if headers is None:
        return None
    try:
        if hasattr(headers, "get"):
            value = headers.get(name)
            if value is not None:
                return value
            # Case-insensitive fallback for dict-like headers.
            for key, val in headers.items():
                if str(key).lower() == name.lower():
                    return val
    except Exception:
        pass
    try:
        return headers.getheader(name)
    except Exception:
        return None


class ProtocolError(Exception):
    """Errors where the server didn't return the correct response"""


class ServerUnreachableError(Exception):
    """Can't reach JSONRPC server"""

    def __init__(self, url, original):
        self.url = url
        self.original = original
        _error_format = "unable to contact JSONRPC server '{url}' ({original})"
        _error = _error_format.format(url=url, original=original)
        super(ServerUnreachableError, self).__init__(_error)


class InvalidResponseError(ProtocolError):
    """Probably not JSON in response"""


class JSONRPCError(Exception):
    """Base class for exceptions returned from the server"""

    def __init__(self, method, code, data, message):
        self.method = method
        self.code = code
        self.data = data
        self.message = message
        super(JSONRPCError, self).__init__(message)


class RemoteError(JSONRPCError):
    """One of the generic error types defined in ErrorCode"""


class RemoteMethodError(JSONRPCError):
    """An error returned from the server"""


class ErrorCode(object):
    """Enumeration of JSONRPC error codes"""

    parse_error = -32700
    invalid_request = -32600
    method_not_found = -32601
    invalid_params = -32602
    internal_error = -32603

    to_str = {
        -32700: "Parse error",
        -32600: "Invalid Request",
        -32601: "Method not found",
        -32602: "Invalid params",
        -32603: "Internal error",
    }


class Batch(object):
    """An object that stores a batch of rpc calls

    May be used as a context manager

        with client.batch() as batch:
            batch.call("method1", foo="bar")
            batch.call("method2", foo="baz")

    Method call results are stored in `results` which maps the call id on to results.
    Errors are contained in `errors` which maps the call id on to a dictionary with error code / message

    """

    def __init__(self, client):
        self.client = client
        self.calls = []
        self.sent = False
        self.responses = None
        self.errors = None
        self.results = None
        self.ids_used = set()
        self.methods = {}
        self._abandoned = False
        super(Batch, self).__init__()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if not exc_type and not self._abandoned:
            self.send()

    def call(self, method, **params):
        """Add a call to the batch, using a default id."""
        call = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self.client.new_call_id(),
        }
        self.calls.append(call)
        self.methods[call["id"]] = method

    def call_with_id(self, call_id, method, **params):
        """Add a call to the batch with a supplied id."""
        if call_id in self.ids_used:
            raise ValueError("duplicate call id in batch")
        call = {"jsonrpc": "2.0", "method": method, "params": params, "id": call_id}
        self.calls.append(call)
        self.ids_used.add(call_id)
        self.methods[call["id"]] = method

    def notify(self, method, **params):
        call = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        self.calls.append(call)

    def send(self):
        response_json = self.client._send(self.calls)
        self.sent = True
        response = json.loads(response_json)

        if not isinstance(response, list):
            raise ProtocolError("Expected a list of response from the server")

        self.responses = [
            (r.get("error", None), r.get("result", None)) for r in response
        ]
        self.errors = {r["id"]: r["error"] for r in response if "error" in r}
        self.results = {r["id"]: r for r in response if "id" in r and "error" not in r}

    def get_result(self, call_id, default=Ellipsis):
        """Get a result from the batch, potentially raising rpc errors."""
        if call_id in self.results:
            return self.results[call_id].get("result", None)
        elif call_id in self.errors:
            if default is Ellipsis:
                self.client._handle_error(self.methods[call_id], self.errors[call_id])
            else:
                return default
        else:
            raise KeyError("No such call_id in response")

    def check(self, *call_ids):
        """Check call IDs for exceptions, discard results."""
        for call_id in call_ids:
            self.get_result(call_id)

    def abandon(self, reason=None):
        """Mark batch as 'abandoned' (will not be sent)."""
        self._abandoned = True


class JSONRPC(object):
    """A client for a JSONRPC server."""

    unknown_error_msg = "the server did not supply further information"
    # Edge-visible device id for CloudFront / WAF blocks. Not a secret.
    DEVICE_SERIAL_HEADER = "X-Device-Serial"

    def __init__(self, url, timeout=None):
        self.url = url
        self.call_id = 1
        self.timeout = constants.JSONRPC_TIMEOUT if timeout is None else timeout
        self.device_serial = None

    def set_device_serial(self, serial):
        """Attach the device serial to subsequent API requests for edge filtering."""
        self.device_serial = serial or None

    def new_call_id(self):
        self.call_id += 1
        return self.call_id

    def _request_url(self):
        """API URL with serial= when known (CloudFront/WAF can match query args)."""
        if not self.device_serial:
            return self.url
        sep = "&" if "?" in self.url else "?"
        return self.url + sep + "serial=" + quote(str(self.device_serial), safe="")

    def _send(self, call):
        call_json = json.dumps(call)
        # Py2 returns bytes, Py3 returns unicode str
        if isinstance(call_json, text_type):
            call_json = call_json.encode("utf-8")
        log.debug("JSONRPC request %i Kb", len(call_json) // 1000)

        request = Request(self._request_url(), data=call_json)
        request.add_header("Content-Type", "application/json")
        if self.device_serial:
            request.add_header(self.DEVICE_SERIAL_HEADER, str(self.device_serial))

        min_wait = max(1.0, float(constants.JSONRPC_RETRY_MIN_WAIT))
        max_wait = max(min_wait, float(constants.JSONRPC_RETRY_MAX_WAIT))
        max_attempts = 3
        last_error = None
        for attempt in range(1, max_attempts + 1):
            url_file = None
            try:
                try:
                    url_file = urlopen(request, timeout=self.timeout)
                    response_json = url_file.read().decode("utf-8")
                finally:
                    if url_file is not None:
                        url_file.close()
            except HTTPError as exc:
                status = getattr(exc, "code", None)
                last_error = exc
                headers = getattr(exc, "headers", None) or getattr(exc, "hdrs", None)
                retry_after = _header_get(headers, "Retry-After")
                if status in RETRYABLE_STATUS and attempt < max_attempts:
                    delay = compute_backoff_seconds(
                        attempt,
                        retry_after_header=retry_after,
                        base=min_wait,
                        maximum=max_wait,
                    )
                    log.warning(
                        "JSONRPC HTTP %s (attempt %s/%s); Retry-After=%s; waiting %.1fs",
                        status,
                        attempt,
                        max_attempts,
                        retry_after,
                        delay,
                    )
                    sleep_backoff(delay)
                    continue
                raise ServerUnreachableError(self.url, exc)
            except Exception as exc:
                last_error = exc
                if attempt < max_attempts:
                    delay = compute_backoff_seconds(
                        attempt,
                        retry_after_header=None,
                        base=min_wait,
                        maximum=max_wait,
                    )
                    log.warning(
                        "JSONRPC transport error (attempt %s/%s): %s; waiting %.1fs",
                        attempt,
                        max_attempts,
                        exc,
                        delay,
                    )
                    sleep_backoff(delay)
                    continue
                raise ServerUnreachableError(self.url, exc)

            log.debug(response_json[:1000])
            return response_json

        raise ServerUnreachableError(self.url, last_error or Exception("unknown"))

    def call(self, method, **params):
        """Call a remote method."""
        call_id = self.new_call_id()
        call = {"jsonrpc": "2.0", "method": method, "params": params, "id": call_id}
        response_json = self._send(call)
        try:
            response = json.loads(response_json)
        except:
            log.error("unable to decode %s", repr(response_json)[:100])
            raise InvalidResponseError("unable to decode response as JSON")

        if "jsonrpc" not in response or "id" not in response:
            raise ProtocolError("Invalid response from server")

        if response["jsonrpc"] != "2.0":
            raise ProtocolError("Client only understands JSONRPC v2.0")

        if response["id"] != call_id:
            raise ProtocolError(
                "Invalid response from the server, 'id' field does not match"
            )

        if "error" in response:
            error = response["error"]
            self._handle_error(method, error)

        return response.get("result", None)

    def notify(self, method, **params):
        """Send a notification to the server."""
        notify = {"jsonrpc": "2.0", "method": method, "params": params}
        self._send(notify)

    def batch(self):
        """Create a batch object that can be used to send multiple calls / notifications."""
        return Batch(self)

    def _handle_error(self, method, error):
        code = error.get("code")
        if code in ErrorCode.to_str:
            raise RemoteError(
                method,
                code,
                error.get("data", None),
                error.get("message", ErrorCode.to_str[code]),
            )
        raise RemoteMethodError(
            method,
            code,
            error.get("data", None),
            error.get("message", self.unknown_error_msg),
        )

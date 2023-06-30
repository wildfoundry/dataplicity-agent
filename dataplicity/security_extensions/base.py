import logging
import requests
import json
import typing

from .commands.proc import Proc
from .commands.netstat import Netstat
from collections import defaultdict

if typing.TYPE_CHECKING:
    from typing import Callable, Text


log = logging.getLogger("agent")


DISABLED = 0
DISCOVERY_MODE = 1
ALERT_MODE = 2


class SecurityExtensions:
    """Manages security extensions."""

    def __init__(self, client):
        self.client = client
        self.enabled = True

        # 'seen events' won't trigger an immediate send.
        self._seen_events = defaultdict(set)

        # pending to be sent to server
        self._pending = defaultdict(list)
        self._counter = 0

        self.mode = DISCOVERY_MODE

    @classmethod
    def init(cls, client):
        sec_ext = cls(client)
        return sec_ext

    def __repr__(self):
        # type: () -> Text
        return "SecurityExtensions(enabled=%r)" % self.enabled

    def _reset_pending(self):
        """After constants.<pending> all data related of how many times a """
        # pending to be sent to server
        self._pending = defaultdict(list)
        self._counter = 0

    def get_named_tuple(self, kind):
        if kind == "proc":
            return Proc().get_data_model()
        elif kind == "netstat":
            return Netstat().get_data_model()

    def _get_commands_enabled(self):
        commands = [
            Proc(),
            Netstat()
        ]

        return commands

    def poll(self):

        if not self._seen_events:
            self.load_events_data_from_device()

        commands = self._get_commands_enabled()

        for cmd in commands:
            # an event is a process, connection, etc.
            events = cmd.execute()
            log.debug("Found %s event(s): %s", len(events), events)
            self.send_detected_events(cmd.kind, list(events))

    def load_events_data_from_device(self):
        # type: () -> None
        log.debug("Starting initial load IDS data")
        headers = {"DA_TOKEN": f"{self.client.device_token}"}

        response = requests.get(
            "%s/events/anomalous/" % self.client.rpc_url,
            headers=headers
        )

        ids_data = response.json()
        if not ids_data:
            log.warning("No ids loaded.")
            return

        if response.status_code != 200:
            log.warning("Error loading ids: %s", response.json())
            return

        for key, values in ids_data.items():
            NamedTuple = self.get_named_tuple(key)
            self._seen_events[key].update(
                # timestamp=None because we don't mind about timestamp
                set(NamedTuple(None, *row) for row in values)
                )
            log.warning("Loaded %s items for %s", len(self._seen_events[key]), key)

    def _parse_data(self, kind, data):
        # self.pending is a dictionary that count how many times
        # something has been seen.
        result = []
        for row in data:
            _data = row._asdict()
            #_data["seen"] = self._pending[kind][row]
            result.append(_data)
        return json.dumps(result)

    def send_detected_events(self, kind, events):
        # type: (bytes, list) -> None
        json_data = {
            "kind": kind,
            "payload": self._parse_data(kind, events)
        }
        headers = {"DA_TOKEN": f"{self.client.device_token}"}
        response = requests.post(
            "%s/events/" % self.client.rpc_url, json=json_data, headers=headers,
            )
        #log.warning("PARSED EVENTS TO SEND: %s / \n response: %s", json_data, response)

    def send_detected_events_ORIG(self, kind, events, number_of_samples):
        # type: (bytes, bytes, int) -> None

        parsed_events = self._parse_data(kind, events)
        with self.client.remote.batch() as batch:
            batch.call_with_id(
                "authenticate_result",
                "device.check_auth",
                device_class="tuxtunnel",
                serial=self.client.serial,
                auth_token=self.client.auth_token,
            )
            batch.call(
                "ids.add_events_data",
                kind=kind,
                number_of_samples=number_of_samples,
                events=parsed_events
            )

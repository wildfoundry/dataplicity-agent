from __future__ import unicode_literals
from __future__ import print_function

import logging
import platform
from threading import Event, Lock
import os
import random
import sys
import time

from ._version import __version__
from . import constants
from . import device_meta
from . import jsonrpc
from .auth_backoff import (
    AuthBackoffGate,
    is_auth_failure_exception,
    retry_after_from_exception,
)
from .clockcheck import ClockCheckThread
from .directory_scanner import DirectoryScanner
from .disk_tools import disk_usage
from .m2mmanager import M2MManager
from .portforward import PortForwardManager
from .remote_directory import RemoteDirectory
from .tags import get_tag_list, TagError
import six

log = logging.getLogger("agent")


class Client(object):
    """Dataplicity client."""

    def __init__(
        self,
        rpc_url=None,  # type: str
        m2m_url=None,  # type: str
        serial=None,  # type: str
        auth_token=None,  # type: str
        remote_directory_path=None,  # type: str
    ):
        # type: (...) -> None
        self.rpc_url = rpc_url or constants.SERVER_URL
        self.m2m_url = m2m_url or constants.M2M_URL

        if "?" not in self.m2m_url:
            self.m2m_url += "?features=" + ",".join(constants.M2M_FEATURES)

        self.auth_token = auth_token
        self.serial = serial
        self.remote_directory_path = remote_directory_path

        self._sync_lock = Lock()
        self._sent_meta = False
        self.exit_event = Event()
        # Shared quiet period after deleted-device / revoked-token auth fails.
        self.auth_gate = AuthBackoffGate()
        self._init()
        self._tag_list = None

    @classmethod
    def _read(cls, path):
        """Read contents of a file, strip whitespace."""
        path = os.path.expanduser(path)
        with open(path, "rt") as fh:
            data = fh.read().strip()
        return data

    def _init(self):
        try:
            log.info("dataplicity %s", __version__)
            log.info("python executable=%s", sys.executable)
            log.info("python version=%s", sys.version.replace("\n", " "))
            log.info("uname=%s", " ".join(platform.uname()))

            self.remote = jsonrpc.JSONRPC(self.rpc_url)
            self.serial = self.serial or self._read(constants.SERIAL_LOCATION)
            self.auth_token = self.auth_token or self._read(constants.AUTH_LOCATION)
            self.remote_directory_path = (
                self.remote_directory_path or constants.REMOTE_DIRECTORY_LOCATION
            )
            log.info("remote_directory=%s", self.remote_directory_path)

            self.poll_rate_seconds = 60
            self.disk_poll_rate_seconds = 60 * 60
            self.next_disk_poll_time = time.time()

            log.info("m2m=%s", self.m2m_url)
            log.info("api=%s", self.rpc_url)
            log.info("serial=%s", self.serial)
            log.info("poll=%s", self.poll_rate_seconds)

            self.directory_scanner = DirectoryScanner(self.remote_directory_path)
            self.remote_directory = RemoteDirectory(
                self.remote_directory_path, self.directory_scanner
            )
            self.m2m = M2MManager.init(
                self, self.remote_directory, m2m_url=self.m2m_url
            )
            self.port_forward = PortForwardManager.init(self)

        except Exception:
            log.exception("failed to initialize client")
            raise

    def run_forever(self):
        """Run the client "forever"."""
        clock_check_thread = ClockCheckThread()
        clock_check_thread.start()

        try:
            self.poll()
            while not self.exit_event.wait(self.poll_rate_seconds):
                self.poll()
        except SystemExit:
            log.debug("exit requested")
            return
        except KeyboardInterrupt:
            log.debug("user exit")
            return
        finally:
            clock_check_thread.running = False
            clock_check_thread.join()
            log.debug("closing")
            self.close()
            log.debug("goodbye")

    def exit(self):
        """Exit the agent."""
        self.exit_event.set()

    def disk_poll(self):
        now = time.time()

        if now >= self.next_disk_poll_time:
            self.next_disk_poll_time = now + self.disk_poll_rate_seconds
            if not self.auth_gate.ready():
                return
            disk_space = disk_usage("/")

            with self.remote.batch() as batch:
                batch.call_with_id(
                    "authenticate_result",
                    "device.check_auth",
                    device_class="tuxtunnel",
                    serial=self.serial,
                    auth_token=self.auth_token,
                )
                batch.call_with_id(
                    "set_disk_space_result",
                    "device.set_disk_space",
                    disk_capacity=disk_space.total,
                    disk_used=disk_space.used,
                )

    def tag_poll(self):
        """Gets the tag list for get_tag_list() and sends to the server"""
        try:
            tag_list = get_tag_list()
        except TagError:
            return

        try:
            if tag_list != self._tag_list:
                if not self.auth_gate.ready():
                    return
                log.debug("new machine tags: %r", tag_list)
                with self.remote.batch() as batch:
                    batch.call_with_id(
                        "authenticate_result",
                        "device.check_auth",
                        device_class="tuxtunnel",
                        serial=self.serial,
                        auth_token=self.auth_token,
                    )
                    batch.call_with_id(
                        "set_machine_defined_tags_result",
                        "device.set_machine_defined_tags",
                        tag_list=tag_list,
                    )
                batch.get_result("authenticate_result")
                batch.get_result("set_machine_defined_tags_result")
        except jsonrpc.JSONRPCError as error:
            if self._handle_auth_failure(error, "set tag list"):
                return None
            log.error(
                'unable to set tag list ("%s"=%s, "%s")',
                error.method,
                error.code,
                error.message,
            )
            return None
        except jsonrpc.ServerUnreachableError as error:
            if self._handle_auth_failure(error, "set tag list"):
                return None
            log.debug("set tag list failed: %s", error)
            return None
        except Exception as error:
            log.error("set tag list failed: %s", error)
            return None
        else:
            # Success! Set cached tag list
            self.auth_gate.record_success()
            self._tag_list = tag_list

    def poll(self):
        """Called at regular intervals."""
        t = time.time()
        log.debug("poll t=%.02fs", t)
        try:
            self.disk_poll()
        except Exception as e:
            log.error("disk poll failed %s", e)

        try:
            self.tag_poll()
        except Exception as error:
            log.error("tag poll failed %s", error)

        self.sync()

    def close(self):
        """Perform shutdown."""
        pass

    @classmethod
    def make_sync_id(cls):
        """Make a random sync ID."""
        sync_id = "".join(
            random.choice("abcdefghijklmnopqrstuvwxyz") for _ in six.moves.xrange(12)
        )
        return sync_id

    def sync(self):
        """Sync with server."""
        try:
            with self._sync_lock:
                self._sync()
        except Exception as e:
            if self._handle_auth_failure(e, "sync"):
                return
            log.error("sync failed %s", e)

    def _handle_auth_failure(self, exc, context):
        """Apply long auth backoff; return True when handled as auth failure."""
        if not is_auth_failure_exception(exc):
            return False
        delay = self.auth_gate.record_auth_failure(
            retry_after_header=retry_after_from_exception(exc)
        )
        log.warning(
            "%s unauthorized/gone (%s); long backoff %.1fs "
            "(skipping retries; re-register to recover)",
            context,
            exc,
            delay,
        )
        return True

    def _sync(self):
        """Perform sync."""
        # Syncing is a much simpler process in Dataplicity agent,
        # than previous versions.
        start = time.time()
        sync_id = self.make_sync_id()
        try:
            if not self._sent_meta:
                if not self.auth_gate.ready():
                    return
                with self.remote.batch() as batch:
                    batch.call_with_id(
                        "authenticate_result",
                        "device.check_auth",
                        device_class="tuxtunnel",
                        serial=self.serial,
                        auth_token=self.auth_token,
                        sync_id=sync_id,
                    )
                    self._sync_meta(batch)
                batch.get_result("authenticate_result")
                self.auth_gate.record_success()
                self._check_meta(batch)

        finally:
            elapsed = time.time() - start
            log.debug("sync complete %0.2fs", elapsed)

    def _sync_meta(self, batch):
        """Sync meta information regarding host device."""
        try:
            meta = device_meta.get_meta()
            log.debug("syncing meta %r", meta)
        except:
            log.exception("error getting meta")
        else:
            batch.call_with_id(
                "set_agent_version_result",
                "device.set_agent_version",
                agent_version=meta["agent_version"],
            )
            batch.call_with_id(
                "set_machine_revision_result",
                "device.set_machine_revision",
                revision_code=meta["machine_revision"],
            )
            batch.call_with_id(
                "set_model_name_result",
                "device.set_model_name",
                model_name=meta["model_name"],
            )
            batch.call_with_id(
                "set_os_version_result",
                "device.set_os_version",
                os_version=meta["os_version"],
            )
            batch.call_with_id(
                "set_uname_result", "device.set_uname", uname=meta["uname"]
            )
            batch.call_with_id(
                "set_ip_addresses_result",
                "device.set_ip_addresses",
                ip_list=meta["ip_list"],
            )

    def _check_meta(self, batch):
        """Check previously sent meta information."""
        log.debug("checking meta")
        if self._sent_meta:
            log.debug("meta was previously sent")
            return
        try:
            batch.check(
                "set_agent_version_result",
                "set_machine_revision_result",
                "set_model_name_result",
                "set_os_version_result",
                "set_uname_result",
                "set_ip_addresses_result",
            )
        except Exception as e:
            log.warning("failed to set device meta (%s)", e)
        else:
            # Success! Don't send again.
            self._sent_meta = True
            log.debug("sent meta")

    def set_m2m_identity(self, identity):
        """
        Tell the server of our m2m identity, return the identity if it was set,
        or None if it could not be set.

        """
        if self.auth_token is None:
            return None
        if not self.auth_gate.ready():
            return None

        try:
            log.debug(
                "notifying server (%s) of m2m identity (%s)",
                self.remote.url,
                identity or "<None>",
            )
            with self.remote.batch() as batch:
                batch.call_with_id(
                    "authenticate_result",
                    "device.check_auth",
                    device_class="tuxtunnel",
                    serial=self.serial,
                    auth_token=self.auth_token,
                )
                batch.call_with_id(
                    "associate_result",
                    "m2m.associate",
                    identity=identity.decode("utf-8") or "",
                )
            # These methods may potentially throw JSONRPCErrors
            batch.get_result("authenticate_result")
            batch.get_result("associate_result")
        except jsonrpc.JSONRPCError as e:
            if self._handle_auth_failure(e, "m2m.associate"):
                return None
            log.error(
                'unable to associate m2m identity ("%s"=%s, "%s")',
                e.method,
                e.code,
                e.message,
            )
            return None
        except jsonrpc.ServerUnreachableError as e:
            if self._handle_auth_failure(e, "m2m.associate"):
                return None
            log.debug("set m2m identity failed, %s", e)
            return None
        except Exception as error:
            log.error("unable to set m2m identity: %s", error, exc_info=False)
            return None
        else:
            # If we made it here the server has acknowledged it received the identity
            self.auth_gate.record_success()
            log.debug("server received m2m identity %s", identity)
            return identity

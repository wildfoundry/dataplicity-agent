from __future__ import unicode_literals
from __future__ import print_function

import logging
from threading import Event, Lock
import random
import time

from . import constants
from . import device_meta
from . import settings
from .jsonrpc import JSONRPC

log = logging.getLogger('dpagent')


class Client(object):
    """Dataplicity client."""

    def __init__(self, conf_path, rpc_url=None):
        self.conf_path = conf_path
        self.rpc_url = rpc_url
        self._sync_lock = Lock()
        self._sent_meta = False
        self.exit_event = Event()
        self._init()

    def _init(self):
        try:
            conf = self.conf = settings.read(self.conf_path)
            if self.rpc_url is None:
                self.rpc_url = conf.get(
                    'server',
                    'url',
                    constants.SERVER_URL
                )

            self.remote = JSONRPC(self.rpc_url)
            self.serial = conf.get('device', 'serial')
            log.debug('serial=%s', self.serial)
            self.auth_token = conf.get('device', 'auth')
            self.poll_rate_seconds = conf.get_float("daemon", "poll", 60.0)
            log.debug('poll=%s', self.poll_rate_seconds)
        except:
            log.exception('failed to initialize client')
            raise

    def run_forever(self):
        """Run the client "forever"."""
        try:
            self.poll()
            while not self.exit_event.wait(self.poll_rate_seconds):
                self.poll()
        except SystemExit:
            log.debug('exit requested')
            return
        except KeyboardInterrupt:
            log.debug('user exit')
            return
        finally:
            log.debug('closing')
            self.close()
            log.debug('goodbye')

    def poll(self):
        """Called at regulat intervals."""
        t = time.time()
        log.debug('poll t=%.02fs', t)
        self.sync()

    def close(self):
        """Perform shutdown."""
        pass

    @classmethod
    def make_sync_id(self):
        """Make a random sync ID."""
        sync_id = ''.join(
            random.choice('abcdefghijklmnopqrstuvwxyz') for _ in xrange(12)
        )
        return sync_id

    def sync(self):
        try:
            with self._sync_lock:
                self._sync()
        except Exception as e:
            log.error("sync failed %s", e)

    def _sync(self):
        start = time.time()
        sync_id = self.make_sync_id()
        try:
            with self.remote.batch() as batch:
                batch.call_with_id(
                    'authenticate_result',
                    'device.check_auth',
                    device_class='tuxtunnel',
                    serial=self.serial,
                    auth_token=self.auth_token,
                    sync_id=sync_id
                )

                self._sync_m2m(batch)

                if not self._sent_meta:
                    self._sync_meta(batch)

            # get_result will throw exceptions with (hopefully) helpful error messages if they fail
            batch.get_result('authenticate_result')

        finally:
            ellapsed = time.time() - start
            log.debug('sync complete %0.2fs', ellapsed)

    def _sync_meta(self, batch):
        try:
            meta = device_meta.get_meta()
        except:
            self.log.exception('error getting meta')
        else:
            batch.call_with_id(
                'set_agent_version_result',
                'device.set_agent_version',
                agent_version=meta['agent_version']
            )
            batch.call_with_id(
                'set_machine_type_result',
                'device.set_machine_type',
                machine_type=meta['machine_type'] or 'other'
            )
            batch.call_with_id(
                'set_os_version_result',
                'device.set_os_version',
                os_version=meta['os_version']
            )
            batch.call_with_id(
                'set_uname_result',
                'device.set_uname',
                uname=meta['uname']
            )

    def _sync_m2m(self, batch):
        log.debug("TODO: sync_m2m")
        pass

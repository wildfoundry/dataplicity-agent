import pytest
from dataplicity import client as mclient
from dataplicity import device_meta
from mock import patch
from freezegun import freeze_time
from datetime import datetime
import random


@pytest.fixture
def serial_file(tmpdir):
    serial_file = tmpdir.join("serial")
    serial_file.write("test-serial")
    with patch('dataplicity.constants.SERIAL_LOCATION', str(serial_file)):
        yield str(serial_file)


@pytest.fixture
def auth_file(tmpdir):
    auth_file = tmpdir.join("auth")
    auth_file.write("test-auth")
    with patch('dataplicity.constants.AUTH_LOCATION', str(auth_file)):
        yield str(auth_file)


def test_client_initialization(auth_file, serial_file):
    """ this function tests 'succesful' initialization of the client
    """
    mclient.Client()


def test_client_unsuccesful_init(tmpdir):
    """ the client won't start if the file is missing.
        serial file is read first, so we have to fake the location there in
        order to raise IOError.
    """
    non_existing_path = tmpdir.join("non-existing-file")
    with patch(
        'dataplicity.constants.SERIAL_LOCATION', str(non_existing_path)
    ):
        with pytest.raises(IOError):
            mclient.Client()


def test_system_exit_call(serial_file, auth_file, mocker):
    """ test client initialization with error handling
    """
    client = mclient.Client()

    def poll_which_raises(self):
        raise SystemExit

    def poll_which_raises_keyboardint(self):
        raise KeyboardInterrupt

    # this attaches to client.close() method which should be called at the end
    # of run_forever. The method won't be monkeypatched, but we'll be able
    # to check whether the method was called or not.
    mocker.spy(client, 'close')

    with patch('dataplicity.client.Client.poll', poll_which_raises):
        client.run_forever()
        assert client.close.call_count == 1

    with patch(
        'dataplicity.client.Client.poll', poll_which_raises_keyboardint
    ):
        client.run_forever()
        assert client.close.call_count == 2


@freeze_time("2017-01-03 11:00:00", tz_offset=0)
def test_disk_poll(serial_file, auth_file):
    """ test code for disk_poll
    """
    client = mclient.Client()
    client.disk_poll()

    assert datetime.utcfromtimestamp(
        client.next_disk_poll_time) == datetime(2017, 1, 3, 12, 00)


def test_client_sync_id_generation(mocker):
    """ check sync_id generation
    """
    mocker.spy(random, 'choice')
    sync_id = mclient.Client.make_sync_id()
    assert len(sync_id) == 12
    assert random.choice.call_args('abcdefghijklmnopqrstuvwxyz')


def test_client_sync_with_error(serial_file, auth_file, caplog, httpserver):
    """
    """
    client = mclient.Client(rpc_url=httpserver.url)
    client.sync()

    # teardown for meta cache
    device_meta._META_CACHE = None
    assert 'sync failed' in caplog.text

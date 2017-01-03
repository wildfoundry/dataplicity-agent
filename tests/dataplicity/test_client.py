import pytest
from dataplicity import client as mclient
from mock import patch


def test_client_initialization(tmpdir):
    """ this function tests 'succesful' initialization of the client
    """
    serial_file = tmpdir.join("serial")
    auth_file = tmpdir.join("auth")
    serial_file.write("test-serial")
    auth_file.write("test-auth")

    with patch('dataplicity.constants.SERIAL_LOCATION', str(serial_file)):
        with patch('dataplicity.constants.AUTH_LOCATION', str(auth_file)):
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

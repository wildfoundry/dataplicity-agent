import pytest
from mock import patch


@pytest.fixture
def serial_file(tmpdir):
    """ fixture for creating an fake serial file
    """
    serial_file = tmpdir.join("serial")
    serial_file.write("test-serial")
    with patch('dataplicity.constants.SERIAL_LOCATION', str(serial_file)):
        yield str(serial_file)


@pytest.fixture
def auth_file(tmpdir):
    """ fixture for creating an fake auth file
    """
    auth_file = tmpdir.join("auth")
    auth_file.write("test-auth")
    with patch('dataplicity.constants.AUTH_LOCATION', str(auth_file)):
        yield str(auth_file)

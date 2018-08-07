from dataplicity.rpi import get_machine_revision
from mock import patch
import six


REVISION_TEMPLATE = '\nRevision: %s'


""" Unfortunetely, we can't use mock_open from mock library, because
    the underlying code uses an iterator, which mock_open doesn't implement.
    There is a brief solution which might work for python3, but not for python2
    provided here:
    http://stackoverflow.com/questions/24779893/customizing-unittest-mock-mock-open-for-iteration
"""


class FileContentIterator(six.Iterator):
    """ this is a replacement for mock_open which supports iterations.
    """
    def __init__(self, file_contents):
        self.file_contents = file_contents.split('\n')
        self.index = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.index < len(self.file_contents):
            self.index += 1
            return self.file_contents[self.index - 1]
        raise StopIteration()


class MockOpenContext(object):
    """ this class is used to be able to call open() like a context decorator
    """
    def __init__(self, file_contents):
        self._ctx = FileContentIterator(file_contents)

    def __enter__(self, ):
        return self._ctx

    def __exit__(self, *args):
        pass


def test_get_machine_revision():
    """ test for get_machine_revision function
    """

    def mock_open(file_contents):
        """ mock for open() for a situation where the file does exist.
        """
        def inner(file_path, mode):
            return MockOpenContext(file_contents)

        return inner

    def mock_open_ioerror(file_path, mode):
        """ method to intentionally raise a IOError, to test for code path
            which returns None as a revision ID
        """
        raise IOError

    def builtin_open_name():
        return '{}.open'.format(six.moves.builtins.__name__)

    REVISION = 'abc123'
    with patch(
        builtin_open_name(),
        mock_open(REVISION_TEMPLATE % REVISION),
        create=True
    ):
        assert get_machine_revision() == REVISION

    # if the file doesn't exist, the version should be None
    with patch(
        builtin_open_name(),
        mock_open_ioerror,
        create=True
    ):
        assert get_machine_revision() is None

from dataplicity import device_meta
from mock import patch


def test_get_os_version():
    with patch(
        'distro.name', lambda: "test-distro"
    ):
        with patch("distro.version", lambda: "1.0.0"):
            with patch("distro.codename", lambda: ""):
                assert 'test-distro 1.0.0' == device_meta.get_os_version()


def test_get_uname():
    fake_uname = list(map(str, range(6)))
    with patch(
        'platform.uname',
        lambda: fake_uname,
    ):
        assert ' '.join(fake_uname) == device_meta.get_uname()


@patch('dataplicity.rpi.get_machine_revision', lambda: '')
def test_get_meta():
    """ test for get_meta function.
        as this function calls get_machine_revision underneath (which we test
        separately), we temporarily monkey-patch the output to empty string
    """
    # initially, _META_CACHE should be empty
    assert device_meta._META_CACHE is None

    # collect the test metadata
    fake_uname = list(map(str, range(6)))
    with patch('platform.uname', lambda: fake_uname):
        _meta = device_meta.get_meta()
        # now, _META_CACHE should be populated
        assert device_meta._META_CACHE is not None
        assert ' '.join(fake_uname) == _meta['uname']

    # even with some changed values, what is inside the cache should be
    # returned.
    fake_uname_altered = list(map(str, range(6, 12)))
    with patch('platform.uname', lambda: fake_uname_altered):
        _meta = device_meta.get_meta()
        assert device_meta._META_CACHE['uname'] == ' '.join(fake_uname)

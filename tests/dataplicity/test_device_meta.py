from dataplicity import device_meta
from mock import patch


def test_get_os_version():
    with patch(
        'platform.linux_distribution',
        lambda: ('test-distro', '1.0.0', ''),
    ):
        assert 'test-distro 1.0.0' == device_meta.get_os_version()


def test_get_uname():
    fake_uname = list(map(str, range(6)))
    with patch(
        'platform.uname',
        lambda: fake_uname,
    ):
        assert ' '.join(fake_uname) == device_meta.get_uname()


@patch('dataplicity.rpi.get_machine_type', lambda: '')
def test_get_meta():
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

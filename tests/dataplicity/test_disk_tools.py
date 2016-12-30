import os

import six
from dataplicity.disk_tools import disk_usage, sdiskusage, usage_percent


def test_usage_percent():
    """ test for usage_percent
    """
    # intiger division - should return 0
    assert 5.88235294117647 == usage_percent(1, 17)
    # float division
    assert 5.88235294117647 == usage_percent(1, 17.)
    # rounding
    assert 5.8824 == usage_percent(1, 17., _round=4)
    # cover for ZeroDivision error
    assert 0 == usage_percent(1, 0)
    assert 0.0 == usage_percent(1, 0.)


def test_disk_usage(tmpdir):
    """ test for disk_usage function
    """
    # append unicode to the temporary directory name
    path = str(tmpdir) + "/" + six.unichr(233)
    os.mkdir(path)

    _disk_usage = disk_usage(path)
    assert type(_disk_usage) is sdiskusage
    assert hasattr(_disk_usage, 'total')

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
    def prepare_utf8_path(tmpdir):
        subdir = b"\xce\x94"  # greek capital Delta
        if six.PY2:
            # this mangling with unicode and str is necesary, because we want
            # to actually force a UnicodeEncodeError. In order to do that, we
            # have to pass a unicode. However, when we do the chain to .mkdir()
            # then it calls __fspath__ underneath, therefore it has to receive
            # a string rather than unicode. Therefore, the whole procedure is
            # as following:
            # 1) Pass a string to mkdir()
            # 2) convert the LocalPath object to string
            # 3) convert the string to unicode, in order to force a
            #    UnicodeEncodeError inside the disk_usage method
            return unicode(str(tmpdir.mkdir(subdir)), "utf-8")
        elif six.PY3:
            # this is very similar to PY2 branch, except that there is no
            # unicode object in python3. However, please notice that b"\xce\x94"
            # will be treated as bytes rather than string in python3, which
            # in return will raise Exception inside mkdir. Therefore what we do
            # is:
            # 1) Decode subdir (bytes) into utf-8 string
            # 2) convert tmpdir (LocalPath) to string object
            return str(tmpdir.mkdir(subdir.decode("utf-8")))

    utf8_subdir = prepare_utf8_path(tmpdir)

    _disk_usage = disk_usage(utf8_subdir)

    assert isinstance(_disk_usage, sdiskusage)
    assert hasattr(_disk_usage, 'total')

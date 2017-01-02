# -*- coding: utf-8
from dataplicity.m2m.bencode import encode, EncodingError
import pytest
import six


def test_bencode_encoder():
    assert encode({}) == six.b('de')  # empty dict
    assert encode({b'foo': 'bar'}) == six.b('d3:foo3:bare')
    assert encode({
        b'foo': 'bar',
        b'fooo': 'bbar'
    }) == six.b('d3:foo3:bar4:fooo4:bbare')
    assert encode([]) == six.b('le')  # empty list
    assert encode(()) == six.b('le')  # empty list
    assert encode([1, 2, 3]) == six.b('li1ei2ei3ee')
    assert encode([1, 'foo']) == six.b('li1e3:fooe')
    assert encode(1) == six.b('i1e')
    # utf-8 string
    assert encode(b'a\xc5\xbc') == six.b('3:a\xc5\xbc')
    assert encode("aż") == six.b("3:a\xc5\xbc")
    with pytest.raises(EncodingError):
        encode(1.38)
    # since bytes == str in python2, this exception won't be raised
    if six.PY3:
        with pytest.raises(EncodingError):
            encode({'foo': 'bar'})

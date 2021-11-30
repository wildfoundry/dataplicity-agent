# -*- coding: utf-8
from dataplicity.m2m.bencode import encode, decode, EncodingError, DecodeError
import pytest


def test_bencode_encoder():
    """ test bencoding capabilities
    """
    assert encode({}) == b'de'  # empty dict
    assert encode({b'foo': 'bar'}) == b'd3:foo3:bare'
    assert encode({
        b'foo': 'bar',
        b'fooo': 'bbar'
    }) == b'd3:foo3:bar4:fooo4:bbare'
    assert encode([]) == b'le'  # empty list
    assert encode(()) == b'le'  # empty list
    assert encode([1, 2, 3]) == b'li1ei2ei3ee'
    assert encode([1, 'foo']) == b'li1e3:fooe'
    assert encode(1) == b'i1e'
    # make sure that the numbers are encoded as bytes. This line would always
    # return true in python2, but will have a meaning in python3
    assert isinstance(encode(1), bytes)
    # utf-8 string
    assert encode(b'a\xc5\xbc') == b'3:a\xc5\xbc'
    assert encode("aż") == b"3:a\xc5\xbc"
    with pytest.raises(EncodingError):
        encode(1.38)
    # since bytes == str in python2, this exception won't be raised
    with pytest.raises(EncodingError):
        encode({u'foo': 'bar'})

    assert encode(-41) == b"i-41e"


def test_bencode_decoder():
    """ test decoding capabilities of bencode module
    """
    assert decode(b'de') == {}
    assert decode(b'i-41e') == -41
    assert decode(b'd3:foo3:bare') == {b'foo': b'bar'}
    assert decode(b'd3:foo3:bar4:fooo4:bbare') == {
        b'foo': b'bar', b'fooo': b'bbar'}
    with pytest.raises(DecodeError) as exc:
        decode(b'i.123e')
    assert str(exc.value) == 'illegal digit in size'
    assert decode(b'le') == []
    assert decode(b'li1ei2ee') == [1, 2]
    assert decode(b'13:aaaaaaaaaaa\xc5\xbc') == b'aaaaaaaaaaa\xc5\xbc'

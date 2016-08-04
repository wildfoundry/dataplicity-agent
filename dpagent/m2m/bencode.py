from __future__ import print_function
from __future__ import unicode_literals

"""
Encode / Decode Bencode (http://en.wikipedia.org/wiki/Bencode)

"""

import io
import sys

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

if PY3:
    number_types = (int,)
    text_type = str
else:
    number_types = (long, int)
    text_type = unicode


class EncodingError(ValueError):
    pass


class DecodeError(Exception):
    pass


class DecoderError(Exception):
    """Exception occurred with the data being decoded"""
    (
        PRECEDING_ZERO_IN_SIZE,
        MAX_SIZE_REACHED,
        ILLEGAL_DIGIT_IN_SIZE,
        ILLEGAL_DIGIT
    ) = range(4)

    error_text = {
        PRECEDING_ZERO_IN_SIZE: "PRECEDING_ZERO_IN_SIZE",
        MAX_SIZE_REACHED: "MAX_SIZE_REACHED",
        ILLEGAL_DIGIT_IN_SIZE: "ILLEGAL_DIGIT_IN_SIZE",
        ILLEGAL_DIGIT: "ILLEGAL_DIGIT"
    }

    def __init__(self, code, text):
        self.code = code
        self.text = text
        super(DecoderError, self).__init__()

    def __str__(self):
        return "{} (#{}), {}".format(DecoderError.error_text[self.code], self.code, self.text)


def encode(obj):
    """Encode to Bencode, return bytes"""
    binary = []
    append = binary.append

    def add_encode(obj):
        if isinstance(obj, bytes):
            append(b"{}:{}".format(len(obj), obj))
        elif isinstance(obj, text_type):
            obj = obj.encode('utf-8')
            append(b"{}:{}".format(len(obj), obj))
        elif isinstance(obj, number_types):
            append(b"i{}e".format(obj))
        elif isinstance(obj, (list, tuple)):
            append(b"l")
            for item in obj:
                add_encode(item)
            append(b'e')
        elif isinstance(obj, dict):
            append(b'd')
            keys = sorted(obj.keys())
            for k in keys:
                if not isinstance(k, bytes):
                    raise EncodingError("dict keys must be bytes")
                add_encode(k)
                add_encode(obj[k])
            append(b'e')
        else:
            raise EncodingError('value {!r} can not be encoded in Bencode'.format(obj))

    add_encode(obj)
    return b''.join(binary)


def decode(data):
    """Decode Bencode, return an object."""
    assert isinstance(data, bytes), "decode takes bytes"
    return _decode(io.BytesIO(data).read)


def _decode(read):
    """Decode bebcode, `read` should be a callable that returns number of bytes."""
    # TODO: Some input validation
    obj_type = read(1)
    if obj_type == b'e':
        return None
    if obj_type == b'i':
        number_bytes = b''
        while 1:
            c = read(1)
            if not c.isdigit():
                if c != b'e':
                    raise DecodeError('illegal digit in size')
                break
            number_bytes += c
        number = int(number_bytes)
        return number
    elif obj_type == b'l':
        l = []
        while 1:
            i = _decode(read)
            if i is None:
                break
            l.append(i)
        return l
    elif obj_type == b'd':
        kv = []
        while 1:
            k = _decode(read)
            if k is None:
                break
            v = _decode(read)
            kv.append((k, v))
        return dict(kv)
    else:
        size_bytes = obj_type
        while 1:
            c = read(1)
            if c == b':':
                break
            size_bytes += c
        size = int(size_bytes)
        return read(size)


class StringDecoder(object):
    """
    A bencode stream decoder.

    Turns a bencode string stream in to a number of discreet strings.

    """

    def __init__(self, max_size=None):
        """
        A benstring-stream decoder object.

        max_size -- The maximum size of a benstring encoded string, after which
        a DecoderError will be throw. A value of None (the default) indicates
        that there should be no maximum string size.

        """
        self.max_size = max_size

        self.data_pos = 0
        self.string_start = 0
        self.size_string = b""
        self.data_size = None
        self.remaining_bytes = 0
        self.data_out = io.BytesIO()

    def __str__(self):
        if self.data_size is None:
            count = len(self.size_string)
        else:
            count = self.data_out.tell()
        return "<benstring decoder, {} bytes in buffer>".format(count)

    def peek_buffer(self):
        """Return any bytes not used by decoder."""
        return self.data_out.getvalue()

    def reset(self):
        """Reset decoder to initial state, and discards any cached stream data."""
        self.data_pos = 0
        self.string_start = 0
        self.size_string = b""
        self.data_size = None
        self.remaining_bytes = 0

        self.data_out.truncate(0)
        self.data_out.seek(0)

    def feed(self, data):
        """
        A generator that yields 0 or more strings from the given data.

        data -- A string containing complete or partial benstring data.

        """
        if not isinstance(data, bytes):
            raise ValueError("data should be of type 'bytes'")

        self.data_pos = 0
        self.string_start = 0

        while self.data_pos < len(data):

            if self.data_size is None:
                c = data[self.data_pos]
                self.data_pos += 1

                if not len(self.size_string):
                    self.string_start = self.data_pos - 1

                if c in b"0123456789":
                    if self.size_string == b'0':
                        raise DecoderError(DecoderError.PRECEDING_ZERO_IN_SIZE,
                                           "Preceding zeros in size field illegal")
                    self.size_string += c
                    if self.max_size is not None and int(self.size_string) > self.max_size:
                        raise DecoderError(DecoderError.MAX_SIZE_REACHED,
                                           "Maximum size of benstring exceeded")

                elif c == b":":
                    if not len(self.size_string):
                        raise DecoderError(DecoderError.ILLEGAL_DIGIT_IN_SIZE,
                                           "Illegal digit ({!r}) in size field".format(c))
                    self.data_size = int(self.size_string)
                    self.remaining_bytes = self.data_size
                else:
                    raise DecoderError(DecoderError.ILLEGAL_DIGIT_IN_SIZE,
                                       "Illegal digit ({!r}) in size field".format(c))

            elif self.data_size is not None:
                get_bytes = min(self.remaining_bytes, len(data) - self.data_pos)
                chunk = data[self.data_pos:self.data_pos + get_bytes]

                whole_string = len(chunk) == self.data_size

                if not whole_string:
                    self.data_out.write(chunk)

                self.data_pos += get_bytes
                self.remaining_bytes -= get_bytes

                if self.remaining_bytes == 0:

                    if whole_string:
                        yield_data = chunk
                    else:
                        yield_data = self.data_out.getvalue()
                        self.data_out.truncate(0)
                        self.data_out.seek(0)

                    self.data_size = None
                    self.size_string = b""
                    self.remaining_bytes = 0
                    yield yield_data


if __name__ == '__main__':

    import unittest

    class Testbenstring(unittest.TestCase):

        def setUp(self):
            self.test_data = b"benstring module by Will McGugan"
            self.encoded_data = b"9:benstring6:module2:by4:Will7:McGugan"

        def test_decoder(self):
            encoded_data = self.encoded_data

            for step in range(1, len(encoded_data)):
                i = 0
                chunks = []
                while i < len(encoded_data):
                    chunks.append(encoded_data[i:i + step])
                    i += step

                decoder = StringDecoder()

                decoded_data = []
                for chunk in chunks:
                    for s in decoder.feed(chunk):
                        decoded_data.append(s)

                self.assertEqual(decoded_data, self.test_data.split())

    unittest.main()

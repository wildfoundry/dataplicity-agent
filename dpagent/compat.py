"""
Python 2/3 compatibility layer

Base on the following post:

http://lucumr.pocoo.org/2013/5/21/porting-to-python-3-redux/

"""

import sys

# Use these flags for code for a particular PY version
PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

# Basic types and builtine
if PY2:
    text_type = unicode
    binary_type = str
    string_types = (basestring,)
    xrange = xrange
    unichr = unichr
    int_types = (int, long)
    py2bytes = lambda s: s.encode('utf-8')
    number_types = (int, long, float)
    next_method_name = "next"
    raw_input = raw_input
else:
    text_type = str
    binary_type = bytes
    xrange = range
    string_types = (str, bytes)
    unichr = chr
    int_types = (int,)
    py2bytes = lambda s: s
    number_types = (int, float)
    next_method_name = "__next__"
    raw_input = input

# Use these functions for iterating over keys / values / items
if PY2:
    iterkeys = lambda d: d.iterkeys()
    itervalues = lambda d: d.itervalues()
    iteritems = lambda d: d.iteritems()
else:
    iterkeys = lambda d: iter(d.keys())
    itervalues = lambda d: iter(d.values())
    iteritems = lambda d: iter(d.items())


# These functions have been re-arranges in PY3
if PY2:
    import urlparse
    from urlparse import urlparse, parse_qs, urlunparse
    from urllib import urlencode, quote
    from itertools import izip_longest as zip_longest
    from urllib2 import urlopen, HTTPError
    import Queue as queue
else:
    from urllib.parse import urlparse, parse_qs, urlunparse
    from urllib.parse import urlencode, quote
    from itertools import zip_longest
    from urllib.request import urlopen, HTTPError
    import queue


# pickle is the C version on PY3
if PY2:
    import cPickle as pickle
else:
    import pickle


# For classes that convert to a unicode string, return unicode from __str__
# and decorate with this function
if PY2:
    def implements_to_string(cls):
        cls.__unicode__ = cls.__str__
        cls.__str__ = lambda x: x.__unicode__().encode('utf-8')
        return cls
else:
    implements_to_string = lambda x: x

# To implement an iterator, call the next method __next__ and decorate the class
# with the following
if PY2:
    def implements_iterator(cls):
        cls.next = cls.__next__
        del cls.__next__
        return cls
else:
    implements_iterator = lambda x: x

# If a class converts to a bool, call the method __bool__, and decorate with this function
if PY2:
    def implements_bool(cls):
        cls.__nonzero__ = cls.__bool__
        del cls.__bool__
        return cls
else:
    def implements_bool(cls):
        return cls


def with_metaclass(meta, *bases):
    class metaclass(meta):
        __call__ = type.__call__
        __init__ = type.__init__

        def __new__(cls, name, this_bases, d):
            if this_bases is None:
                return type.__new__(cls, name, (), d)
            return meta(name, bases, d)
    return metaclass('temporary_class', None, {})

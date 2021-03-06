#!/usr/bin/env python

"""
Unit tests for salt/ext/monitor/parser/yaml.py.
"""

import doctest
import imp
import salt
import sys
import unittest

# Create mock salt.log module used by salt.ext.monitor.parsers
code = '''
def getLogger(*args, **kwargs):
    pass
def trace(*args, **kwargs):
    pass
'''
salt.log = imp.new_module('log')
exec code in salt.log.__dict__
sys.modules['salt.log'] = salt.log

import salt.ext.monitor.parsers

def dummy(*args, **kwargs):
    pass

class MockMonitor(object):
    def __init__(self):
        self.opts = {}
        self.functions = {'test.echo': dummy}

class TestYaml(unittest.TestCase):

    def setUp(self):
        self.parser = salt.ext.monitor.parsers.get_parser(MockMonitor())

    def _test_expand(self, intext, expected):
        self.assertEqual(self.parser._expand_references(intext), expected)

    def _test_call(self, intext, expected):
        self.assertEqual(self.parser._expand_call(intext), expected)

    def _test_conditional(self, incond, inactions, expected):
        actual = self.parser._expand_conditional(incond, inactions)
        self.assertEqual(actual, expected)

    def test_doc(self):
        doctest.testmod(salt.ext.monitor)

    def test_plain_text_passthrough(self):
        self._test_expand('salt.cmd',    'salt.cmd')      # passthrough
        self._test_expand('sys.argv[0]', 'sys.argv[0]')   # unquoted
        self._test_expand('123',         '123')           # text
        self._test_expand('abc',         'abc')
        self._test_expand('abc 123',     'abc 123')
        self._test_expand('3.14159265',  '3.14159265')

    def test_quoting(self):
        self._test_expand("'123'",       "'123'")
        self._test_expand("'abc'",       "'abc'")
        self._test_expand("'abc 123'",   "'abc 123'")
        self._test_expand('"abc 123"',   "'abc 123'")
        self._test_expand("bob's stuff", "bob's stuff")
        self._test_expand('say "what?"', 'say "what?"')
        self._test_expand("'",            "'")
        self._test_expand("''",           "''")

    def test_escape_sequences(self):
        self._test_expand('\\', '\\')                 # escape at end of string
        self._test_expand('\\abc', '\\abc')           # escape non-special char
        self._test_expand('\\\\', '\\')               # escape escape char
        self._test_expand('\\$', '$')                 # escape reference
        self._test_expand('\\$value', '$value')       # escape reference
        self._test_expand('\\${value}', '${value}')   # escape reference

    def test_reserved_chars(self):
        self._test_expand('{}', '{}')                       # not formatting
        self._test_expand('abc{}123', 'abc{}123')           # not formatting
        self._test_expand("'{$x}'", "'{{{}}}'.format(x)")   # needs escape
        self._test_expand("'}$x{'", "'}}{}{{'.format(x)")   # needs escape
        self._test_expand("'$x {}'", "'{} {{}}'.format(x)") # needs escape

    def test_simple_references(self):
        self._test_expand('$value', 'value')            # unquoted variable
        self._test_expand('${value}', 'value')          # unquoted variable
        self._test_expand("'$value'", 'str(value)')     # just quoted variable
        self._test_expand("'${value}'", 'str(value)')   # just quoted variable
        self._test_expand("'v=$v'", "'v={}'.format(v)") # quoted var plus text

    def test_multiple_references(self):
        self._test_expand('$key=$value', 'key=value')         # e.g. kwargs param
        self._test_expand('${key}=${value}', 'key=value')     # e.g. kwargs param
        self._test_expand("'$key=$value'", "'{}={}'.format(key, value)")
        self._test_expand("'${key}=${value}'", "'{}={}'.format(key, value)")
        self._test_expand("${value['available']}/${value['total']}",
                          "value['available']/value['total']")
        self._test_expand("'${value['available']}/${value['total']}'",
                          "'{}/{}'.format(value['available'], value['total'])")

    def test_expression_references(self):
        self._test_expand("${value['available']<1024*1024}",
                          "value['available']<1024*1024")
        self._test_expand("${value['available']}<1024*1024",
                          "value['available']<1024*1024")

    def test_conditional_expansion(self):
        self._test_expand("if value['available'] * 100 / value['total'] < 90:",
                          "if value['available'] * 100 / value['total'] < 90:")
        self._test_expand("if ${value['available']} * 100 / ${value['total']} < 90:",
                          "if value['available'] * 100 / value['total'] < 90:")
        self._test_expand("if ${value['available'] * 100} / ${value['total']} < 90:",
                          "if value['available'] * 100 / value['total'] < 90:")
        self._test_expand("if ${value['available'] * 100 / value['total']} < 90:",
                          "if value['available'] * 100 / value['total'] < 90:")

    def test_expand_call(self):
        self._test_call("test.echo",
                        "_run('test.echo', [])")
        self._test_call("test.echo 'hello, world'",
                        "_run('test.echo', ['hello, world'])")
        self._test_call("test.echo '${value[\"available\"]/(1024*1024)} MB ${value[\"available\"]*100/value[\"total\"]}%'",
                        "_run('test.echo', ['{} MB {}%'.format(value[\"available\"]/(1024*1024), "\
                                    "value[\"available\"]*100/value[\"total\"])])")

    def test_expand_conditional(self):
        self._test_conditional("${value['available']} > 100", [],
                               [ "if value['available'] > 100:",
                                 "    pass" ])

        self._test_conditional("${value['available']} > 100 and ${value['total']} < 1000",
                               [ "test.echo \"${value['available']} too low\"" ],
                               [ "if value['available'] > 100 and value['total'] < 1000:",
                                 "    _run('test.echo', ['{} too low'.format(value['available'])])" ])

def test_suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

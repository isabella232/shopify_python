import sys

import astroid
import pylint.testutils
import pytest

from shopify_python import google_styleguide


class TestGoogleStyleGuideChecker(pylint.testutils.CheckerTestCase):

    CHECKER_CLASS = google_styleguide.GoogleStyleGuideChecker

    def test_importing_function_fails(self):
        root = astroid.builder.parse("""
        from os.path import join
        from io import FileIO
        from os import environ
        from nonexistent_package import nonexistent_module
        def fnc():
            from other_nonexistent_package import nonexistent_module
        """)
        import_nodes = list(root.nodes_of_class(astroid.ImportFrom))
        tried_to_import = [
            'os.path.join',
            'io.FileIO',
            'os.environ',
            'nonexistent_package.nonexistent_module',
            'other_nonexistent_package.nonexistent_module',
        ]
        with self.assertAddsMessages(*[
            pylint.testutils.Message('import-modules-only', node=node, args={'child': child})
            for node, child in zip(import_nodes, tried_to_import)
        ]):
            self.walk(root)

    def test_importing_modules_passes(self):
        root = astroid.builder.parse("""
        from __future__ import unicode_literals  # Test default option to ignore __future__
        from xml import dom
        from xml import sax
        def fnc():
            from xml import dom
        """)
        with self.assertNoMessages():
            self.walk(root)

    def test_importing_relatively_fails(self):
        root = astroid.builder.parse("""
        from . import string
        from .. import string, os
        """)
        with self.assertAddsMessages(
            pylint.testutils.Message('import-full-path', node=root.body[0], args={'module': '.string'}),
            pylint.testutils.Message('import-full-path', node=root.body[1], args={'module': '.string'}),
            pylint.testutils.Message('import-full-path', node=root.body[1], args={'module': '.os'}),
        ):
            self.walk(root)

    def test_global_variables(self):
        root = astroid.builder.parse("""
        module_var, other_module_var = 10
        another_module_var = 1
        __version__ = '0.0.0'
        CONSTANT = 10
        _OTHER_CONSTANT = sum(x)
        Point = namedtuple('Point', ['x', 'y'])
        _Point = namedtuple('_Point', ['x', 'y'])
        class MyClass(object):
            class_var = 10
        """)
        with self.assertAddsMessages(
            pylint.testutils.Message(
                'global-variable', node=root.body[0].targets[0].elts[0], args={'name': 'module_var'}),
            pylint.testutils.Message(
                'global-variable', node=root.body[0].targets[0].elts[1], args={'name': 'other_module_var'}),
            pylint.testutils.Message(
                'global-variable', node=root.body[1].targets[0], args={'name': 'another_module_var'}),
        ):
            self.walk(root)

    @pytest.mark.skipif(sys.version_info >= (3, 0), reason="Tests code that is Python 3 incompatible")
    def test_using_archaic_raise_fails(self):
        root = astroid.builder.parse("""
        raise MyException, 'Error message'
        raise 'Error message'
        """)
        node = root.body[0]
        message = pylint.testutils.Message('two-arg-exception', node=node)
        with self.assertAddsMessages(message):
            self.walk(root)

    @pytest.mark.skipif(sys.version_info < (3, 0), reason="Tests code that is Python 2 incompatible")
    def test_using_reraise_passes(self):
        root = astroid.builder.parse("""
        try:
            x = 1
        except Exception as exc:
            raise MyException from exc
        """)
        with self.assertNoMessages():
            self.walk(root)

    def test_catch_standard_error_fails(self):
        root = astroid.builder.parse("""
        try:
            pass
        except StandardError:
            pass
        """)
        node = root.body[0].handlers[0]
        message = pylint.testutils.Message('catch-standard-error', node=node)
        with self.assertAddsMessages(message):
            self.walk(root)

    def test_catch_blank_passes(self):
        root = astroid.builder.parse("""
        try:
            pass
        except:
            pass
        """)
        with self.assertAddsMessages():
            self.walk(root)

    def test_try_exc_fnly_complexity(self):
        root = astroid.builder.parse("""
        try:
            a = [x for x in range(0, 10) if x < 5]
            a = sum((x * 2 for x in a)) + (a ** 2)
        except AssertionError as assert_error:
            if set(assert_error).startswith('Division by zero'):
                raise MyException(assert_error, [x for x in range(0, 10) if x < 5])
            else:
                a = [x for x in range(0, 10) if x < 5]
                raise
        finally:
            a = [x for x in range(0, 10) if x < 5]
            a = sum((x * 2 for x in a))
        """)
        try_finally = root.body[0]
        try_except = try_finally.body[0]
        with self.assertAddsMessages(
            pylint.testutils.Message('finally-too-long', node=try_finally, args={'found': 24}),
            pylint.testutils.Message('try-too-long', node=try_except, args={'found': 28}),
            pylint.testutils.Message('except-too-long', node=try_except.handlers[0], args={'found': 39}),
        ):
            self.walk(root)
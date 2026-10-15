import unittest

from src.parser import parse_name


class EmptyNameTests(unittest.TestCase):
    def test_empty_and_whitespace(self):
        for value in ("", "  "):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_name(value)


class ValidNameTests(unittest.TestCase):
    def test_normalized_name(self):
        self.assertEqual(parse_name(" Ada "), "Ada")

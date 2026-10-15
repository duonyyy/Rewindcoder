import unittest

from src.reader import read_rows


class TsvTests(unittest.TestCase):
    def test_preserves_meaningful_space(self):
        self.assertEqual(read_rows(" A \tB \n", "\t"), [[" A ", "B "]])


class CsvTests(unittest.TestCase):
    def test_trims_csv(self):
        self.assertEqual(read_rows(" A , B \n", ","), [["A", "B"]])

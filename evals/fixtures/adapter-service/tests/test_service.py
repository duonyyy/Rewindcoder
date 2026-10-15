import unittest

from src.service import invoice_total


class NegativeAmountTests(unittest.TestCase):
    def test_rejects_negative(self):
        with self.assertRaises(ValueError):
            invoice_total([2, -1])


class ExistingCallerTests(unittest.TestCase):
    def test_positive_and_zero(self):
        self.assertEqual(invoice_total([2, 0, 3]), 5)

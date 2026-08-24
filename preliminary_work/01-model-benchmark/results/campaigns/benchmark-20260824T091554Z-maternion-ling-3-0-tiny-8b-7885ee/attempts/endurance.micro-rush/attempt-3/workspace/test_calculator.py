import unittest

from calculator import add


class CalculatorTest(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(19, 23), 42)


if __name__ == '__main__':
    unittest.main()

import unittest

from qpcodec.qp import QpError, decode, encode


class EncodeTest(unittest.TestCase):
    def test_plain_ascii(self):
        self.assertEqual(encode("hello"), b"hello")

    def test_empty(self):
        self.assertEqual(encode(""), b"")

    def test_space_and_newline(self):
        self.assertEqual(encode("a b"), b"a b")

    def test_high_byte(self):
        self.assertEqual(encode(b"\xff"), b"=FF")


class DecodeTest(unittest.TestCase):
    def test_plain_ascii(self):
        self.assertEqual(decode("hello"), b"hello")

    def test_hex_escape(self):
        self.assertEqual(decode("=FF"), b"\xff")

    def test_empty(self):
        self.assertEqual(decode(""), b"")

    def test_rejects_bad_escape(self):
        with self.assertRaises(QpError):
            decode("=ZZ")

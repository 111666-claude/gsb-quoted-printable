import random
import unittest

from qpcodec import reference
from qpcodec.qp import QpError, decode, encode


class ReferenceComparisonTest(unittest.TestCase):
    def test_random_roundtrip_against_reference(self):
        """1 万份随机字节串：编码结果逐字节一致，且都能解回原值。"""
        rng = random.Random(20260928)
        for _ in range(10000):
            data = bytes(rng.randrange(256) for _ in range(rng.randrange(0, 160)))
            wrap = rng.choice([4, 5, 6, 8, 13, 76, rng.randrange(4, 120)])
            mine = encode(data, wrap=wrap)
            theirs = reference.ref_encode(data, wrap=wrap)
            self.assertEqual(mine, theirs)
            self.assertEqual(decode(mine), data)
            self.assertEqual(reference.ref_decode(theirs), data)
            self.assertEqual(decode(mine), reference.ref_decode(mine))

    def test_error_offsets_match_reference(self):
        """随机非法输入：两边都报错，且偏移与消息一致。"""
        rng = random.Random(7)
        alphabet = b"=09AZaz\n\r \t\x00\x7f\xff"
        for _ in range(3000):
            text = bytes(rng.choice(alphabet) for _ in range(rng.randrange(0, 30)))
            err_mine = err_theirs = None
            try:
                mine = decode(text)
            except QpError as error:
                err_mine = error
            try:
                theirs = reference.ref_decode(text)
            except QpError as error:
                err_theirs = error
            if err_mine is None and err_theirs is None:
                self.assertEqual(mine, theirs)
                continue
            self.assertIsNotNone(err_mine, text)
            self.assertIsNotNone(err_theirs, text)
            self.assertEqual(err_mine.offset, err_theirs.offset, text)
            self.assertEqual(str(err_mine), str(err_theirs), text)

    def test_samples_against_reference(self):
        samples = [
            b"",
            b"=",
            b"hello world",
            b"a b \t c",
            bytes(range(256)),
            b"\n\r\t ",
            b"a" * 76,
            b"=" * 100,
        ]
        for data in samples:
            for wrap in (4, 5, 76):
                self.assertEqual(encode(data, wrap=wrap), reference.ref_encode(data, wrap=wrap))
                text = encode(data, wrap=wrap)
                self.assertEqual(decode(text), reference.ref_decode(text))


if __name__ == "__main__":
    unittest.main()

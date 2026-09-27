import io
import random
import re
import unittest
from contextlib import redirect_stdout, redirect_stderr

from qpcodec.cli import main as cli_main
from qpcodec.qp import QpError, decode, decode_chunks, encode, encode_chunks
from qpcodec.reference import RefError, ref_decode, ref_encode

HEX_ESCAPE = re.compile(rb"=[0-9A-Fa-f]{2}")


def random_bytes(rng, size):
    # 偏重边界字符：=、换行、空白、不可打印字节
    pool = b"ab =\n\t\r\x00\xff\x7f~Z09"
    return bytes(rng.choice(pool) if rng.random() < 0.5 else rng.randrange(256)
                 for _ in range(size))


def assert_well_formed(testcase, encoded, wrap):
    """编码结果的形态不变量：行宽、软换行位置、无裸 =。"""
    for line in encoded.split(b"\n"):
        testcase.assertLessEqual(len(line), wrap)
        body = line[:-1] if line.endswith(b"=") else line
        pos = 0
        while True:
            at = body.find(b"=", pos)
            if at < 0:
                break
            testcase.assertRegex(body[at:at + 3], HEX_ESCAPE,
                                 "裸 = 或被拆开的转义：%r" % body)
            pos = at + 3


class EncodeTest(unittest.TestCase):
    def test_plain_ascii(self):
        self.assertEqual(encode("hello"), b"hello")

    def test_empty(self):
        self.assertEqual(encode(""), b"")

    def test_space_and_newline(self):
        self.assertEqual(encode("a b"), b"a b")

    def test_high_byte(self):
        self.assertEqual(encode(b"\xff"), b"=FF")

    def test_equals_is_escaped(self):
        self.assertEqual(encode(b"="), b"=3D")
        self.assertEqual(encode(b"a=b"), b"a=3Db")

    def test_trailing_whitespace_is_escaped(self):
        self.assertEqual(encode(b"a \n"), b"a=20\n")
        self.assertEqual(encode(b"a\t\nb"), b"a=09\nb")
        self.assertEqual(encode(b"a  \t"), b"a=20=20=09")
        self.assertEqual(encode(b"a b "), b"a b=20")

    def test_wrap_soft_breaks(self):
        encoded = encode(b"x" * 100, wrap=76)
        self.assertEqual(encoded, b"x" * 75 + b"=\n" + b"x" * 25)
        assert_well_formed(self, encoded, 76)

    def test_wrap_never_splits_escape(self):
        encoded = encode(b"\xff" * 40, wrap=8)
        for line in encoded.split(b"\n"):
            self.assertLessEqual(len(line), 8)
        self.assertEqual(encoded.count(b"=FF"), 40)
        assert_well_formed(self, encoded, 8)

    def test_wrap_minimum(self):
        encoded = encode(b"\xff\xff", wrap=4)
        self.assertEqual(encoded, b"=FF=\n=FF")
        with self.assertRaises(QpError):
            encode(b"a", wrap=3)

    def test_deterministic(self):
        data = random_bytes(random.Random(7), 500)
        self.assertEqual(encode(data), encode(data))


class DecodeTest(unittest.TestCase):
    def test_plain_ascii(self):
        self.assertEqual(decode("hello"), b"hello")

    def test_hex_escape(self):
        self.assertEqual(decode("=FF"), b"\xff")
        self.assertEqual(decode("=3D"), b"=")

    def test_empty(self):
        self.assertEqual(decode(""), b"")

    def test_soft_break(self):
        self.assertEqual(decode("ab=\ncd"), b"abcd")
        self.assertEqual(decode("=\n"), b"")
        self.assertEqual(decode("a=\nb=\nc"), b"abc")

    def test_rejects_bad_escape(self):
        with self.assertRaises(QpError):
            decode("=ZZ")

    def test_error_offsets(self):
        cases = [
            ("ab=ZZ", 2),    # 非十六进制
            ("=A", 0),       # 不足两位
            ("x=", 1),       # 行尾孤立 =
            ("=", 0),
            ("abc=A", 3),
            ("a\x01b", 1),   # 非法字符
            ("ok\x7f", 2),
            ("=0g", 0),
        ]
        for text, offset in cases:
            with self.subTest(text=text):
                with self.assertRaises(QpError) as ctx:
                    decode(text)
                self.assertEqual(ctx.exception.offset, offset)
                self.assertIn(str(offset), str(ctx.exception))


class RoundTripTest(unittest.TestCase):
    def test_samples(self):
        samples = [b"", b"=", b"==", b"a=\nb", b" \t", b"\n", b"\n\n",
                   b"trail \n", b"\xff\x00\x7f", b"x" * 200, b"a=b=c"]
        for data in samples:
            with self.subTest(data=data):
                self.assertEqual(decode(encode(data)), data)

    def test_random_roundtrip(self):
        rng = random.Random(1024)
        for _ in range(2000):
            data = random_bytes(rng, rng.randrange(0, 80))
            wrap = rng.choice([4, 5, 8, 20, 76])
            self.assertEqual(decode(encode(data, wrap=wrap)), data)


class ReferenceCrossCheckTest(unittest.TestCase):
    """与参考实现逐字节比对：编码结果、解码结果、错误偏移。"""

    def test_encode_matches_reference(self):
        rng = random.Random(20260928)
        for _ in range(10000):
            data = random_bytes(rng, rng.randrange(0, 100))
            wrap = rng.choice([4, 5, 7, 16, 76])
            self.assertEqual(encode(data, wrap=wrap), ref_encode(data, wrap=wrap))

    def test_decode_matches_reference(self):
        rng = random.Random(555)
        for _ in range(10000):
            data = random_bytes(rng, rng.randrange(0, 100))
            text = encode(data, wrap=rng.choice([4, 76]))
            self.assertEqual(decode(text), ref_decode(text))

    def test_error_offsets_match_reference(self):
        rng = random.Random(99)
        # 构造容易出错的 QP 文本：大量 =、伪十六进制、非法字节
        pool = b"=AZ09g \n\x01\x7f\xff"
        for _ in range(10000):
            text = bytes(rng.choice(pool) for _ in range(rng.randrange(0, 30)))
            try:
                expected = ref_decode(text)
            except RefError as ref_err:
                with self.assertRaises(QpError) as ctx:
                    decode(text)
                self.assertEqual(ctx.exception.offset, ref_err.offset,
                                 "偏移不一致：%r" % text)
            else:
                self.assertEqual(decode(text), expected)


class StreamingTest(unittest.TestCase):
    @staticmethod
    def chunked(data, rng, max_size=17):
        chunks = []
        while data:
            size = rng.randrange(1, max_size)
            chunks.append(data[:size])
            data = data[size:]
        return chunks or [b""]

    def test_encode_chunked_matches_one_shot(self):
        rng = random.Random(31337)
        for _ in range(300):
            data = random_bytes(rng, rng.randrange(0, 300))
            wrap = rng.choice([4, 9, 76])
            chunks = self.chunked(data, rng)
            self.assertEqual(b"".join(encode_chunks(chunks, wrap=wrap)),
                             encode(data, wrap=wrap))

    def test_decode_chunked_matches_one_shot(self):
        rng = random.Random(41414)
        for _ in range(300):
            data = random_bytes(rng, rng.randrange(0, 300))
            text = encode(data, wrap=rng.choice([4, 76]))
            chunks = self.chunked(text, rng)
            self.assertEqual(b"".join(decode_chunks(chunks)), decode(text))

    def test_decode_chunked_error_offset_is_global(self):
        chunks = [b"ab", b"=", b"ZZ"]
        with self.assertRaises(QpError) as ctx:
            b"".join(decode_chunks(chunks))
        self.assertEqual(ctx.exception.offset, 2)

    def test_large_stream(self):
        rng = random.Random(6)
        data = random_bytes(rng, 4 * 1024 * 1024)
        encoded = encode(data)
        self.assertEqual(decode(encoded), data)
        assert_well_formed(self, encoded, 76)


class CliTest(unittest.TestCase):
    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli_main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_encode_hex_escapes_equals(self):
        code, out, _ = self.run_cli(["--encode-hex", "3D"])
        self.assertEqual((code, out), (0, "=3D\n"))

    def test_decode_soft_break(self):
        code, out, _ = self.run_cli(["--decode", r"ab=\ncd"])
        self.assertEqual((code, out), (0, "61626364\n"))

    def test_wrap_option(self):
        code, out, _ = self.run_cli(["--encode-hex", "78" * 100, "--wrap", "76"])
        self.assertEqual(code, 0)
        lines = out.rstrip("\n").split("\n")
        self.assertTrue(all(len(line) <= 76 for line in lines))
        self.assertEqual(len(lines), 2)

    def test_decode_error_reports_offset(self):
        code, _, err = self.run_cli(["--decode", "ab=ZZ"])
        self.assertEqual(code, 1)
        self.assertIn("2", err)

    def test_no_args(self):
        code, _, err = self.run_cli([])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()

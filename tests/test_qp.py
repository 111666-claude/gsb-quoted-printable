import unittest

from qpcodec.qp import QpError, decode, encode, iter_decode, iter_encode


def assert_no_bare_equals(case, out):
    """除行尾软换行的 = 外，每个 = 都必须带两位十六进制。"""
    at = 0
    while at < len(out):
        if out[at:at + 1] == b"=":
            if out[at + 1:at + 2] == b"\n":
                at += 2
                continue
            case.assertRegex(out[at + 1:at + 3].decode("ascii"), r"^[0-9A-F]{2}$")
            at += 3
        else:
            at += 1


class EncodeTest(unittest.TestCase):
    def test_plain_ascii(self):
        self.assertEqual(encode("hello"), b"hello")

    def test_empty(self):
        self.assertEqual(encode(""), b"")
        self.assertEqual(encode(b""), b"")

    def test_space_mid_line(self):
        self.assertEqual(encode("a b"), b"a b")

    def test_high_byte(self):
        self.assertEqual(encode(b"\xff"), b"=FF")

    def test_equals_sign_escaped(self):
        self.assertEqual(encode(b"="), b"=3D")
        self.assertEqual(encode(b"a=b"), b"a=3Db")

    def test_trailing_space_escaped(self):
        self.assertEqual(encode(b"a "), b"a=20")

    def test_trailing_tab_escaped(self):
        self.assertEqual(encode(b"a\t"), b"a=09")

    def test_newline_escaped(self):
        self.assertEqual(encode(b"a\nb"), b"a=0Ab")

    def test_printable_passthrough(self):
        text = bytes(c for c in range(0x21, 0x7F) if c != 0x3D)
        self.assertEqual(encode(text, wrap=len(text) + 1), text)
        self.assertEqual(encode(b"hello world!"), b"hello world!")

    def test_wrap_soft_breaks(self):
        data = b"a" * 100
        out = encode(data, wrap=76)
        lines = out.split(b"\n")
        for line in lines:
            self.assertLessEqual(len(line), 76)
        for line in lines[:-1]:
            self.assertTrue(line.endswith(b"="))
        self.assertFalse(lines[-1].endswith(b"="))
        self.assertEqual(decode(out), data)

    def test_wrap_never_splits_escape(self):
        data = bytes(range(256)) * 4
        for wrap in (4, 5, 7, 10, 76):
            out = encode(data, wrap=wrap)
            for line in out.split(b"\n"):
                self.assertLessEqual(len(line), wrap)
            assert_no_bare_equals(self, out)
            self.assertEqual(decode(out), data)

    def test_wrap_minimum(self):
        out = encode(b"\xff" * 5, wrap=4)
        self.assertEqual(out, b"=FF=\n" * 4 + b"=FF")
        self.assertEqual(decode(out), b"\xff" * 5)

    def test_wrap_rejects_too_small(self):
        with self.assertRaises(ValueError):
            encode(b"a", wrap=3)

    def test_trailing_ws_before_wrap(self):
        data = b"a" * 74 + b" " + b"b" * 10
        out = encode(data, wrap=76)
        for line in out.split(b"\n"):
            body = line[:-1] if line.endswith(b"=") else line
            self.assertFalse(body.endswith((b" ", b"\t")))
            self.assertLessEqual(len(line), 76)
        self.assertEqual(decode(out), data)

    def test_trailing_ws_carry_to_next_line(self):
        # 行尾空格转义后本行放不下，=20 要挪到下一行行首
        data = b"a" * 74 + b" " + b"b"
        out = encode(data, wrap=76)
        self.assertEqual(out, b"a" * 74 + b"=\n=20b")
        self.assertEqual(decode(out), data)

    def test_deterministic(self):
        data = bytes(range(256))
        self.assertEqual(encode(data), encode(data))
        self.assertEqual(encode(data, wrap=13), encode(data, wrap=13))


class DecodeTest(unittest.TestCase):
    def test_plain_ascii(self):
        self.assertEqual(decode("hello"), b"hello")

    def test_hex_escape(self):
        self.assertEqual(decode("=FF"), b"\xff")

    def test_lowercase_hex(self):
        self.assertEqual(decode("=ff"), b"\xff")

    def test_equals_roundtrip(self):
        self.assertEqual(decode("=3D"), b"=")

    def test_empty(self):
        self.assertEqual(decode(""), b"")

    def test_soft_break(self):
        self.assertEqual(decode("ab=\ncd"), b"abcd")

    def test_soft_break_crlf(self):
        self.assertEqual(decode("ab=\r\ncd"), b"abcd")

    def test_soft_break_only(self):
        self.assertEqual(decode("=\n"), b"")

    def test_error_offsets(self):
        for text, offset in [
            ("=ZZ", 0),
            ("ab=ZZ", 2),
            ("ab=A", 2),
            ("ab=", 2),
            ("ab=1Z", 2),
            ("a=\rbc", 1),
            ("ab=\r", 2),
        ]:
            with self.assertRaises(QpError) as ctx:
                decode(text)
            self.assertEqual(ctx.exception.offset, offset, text)
            self.assertIn(str(offset), str(ctx.exception))

    def test_illegal_char_offset(self):
        for data, offset in [(b"ab\x00cd", 2), (b"\xff", 0), (b"a\x7fb", 1), (b"\x0b", 0)]:
            with self.assertRaises(QpError) as ctx:
                decode(data)
            self.assertEqual(ctx.exception.offset, offset, data)

    def test_roundtrip_samples(self):
        samples = [
            b"",
            b"hello",
            b"=",
            bytes(range(256)),
            b"a=b\n c \t",
            b" " * 200,
            b"\xff" * 100,
        ]
        for data in samples:
            for wrap in (4, 9, 76):
                self.assertEqual(decode(encode(data, wrap=wrap)), data)


class StreamingTest(unittest.TestCase):
    def test_chunked_encode_matches_one_shot(self):
        data = bytes(range(256)) * 4
        for size in (1, 2, 3, 7, 64, 1024):
            chunks = [data[i:i + size] for i in range(0, len(data), size)]
            self.assertEqual(b"".join(iter_encode(chunks, wrap=13)), encode(data, wrap=13))

    def test_chunked_decode_matches_one_shot(self):
        text = encode(bytes(range(256)), wrap=11) + b"=\r\n=3d"
        for size in (1, 2, 3, 7, 64):
            chunks = [text[i:i + size] for i in range(0, len(text), size)]
            self.assertEqual(b"".join(iter_decode(chunks)), decode(text))

    def test_chunked_decode_error_offset_is_absolute(self):
        with self.assertRaises(QpError) as ctx:
            b"".join(iter_decode([b"ab", b"=", b"Z", b"Z"]))
        self.assertEqual(ctx.exception.offset, 2)

    def test_large_streaming_roundtrip(self):
        chunk = bytes(range(256)) * 4096  # 1 MB
        encoded = b"".join(iter_encode([chunk] * 4, wrap=76))
        for line in encoded.split(b"\n"):
            self.assertLessEqual(len(line), 76)
        decoded = b"".join(
            iter_decode([encoded[i:i + 65536] for i in range(0, len(encoded), 65536)])
        )
        self.assertEqual(decoded, chunk * 4)


if __name__ == "__main__":
    unittest.main()

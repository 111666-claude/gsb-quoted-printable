"""quoted-printable：=XX 转义与软换行。只用标准库。

口径：
- 0x3D 一律编码为 =3D；解码时 =XX 还原为对应字节。
- 行尾的 = 加换行是软换行，解码时两者都丢掉。
- 编码按 wrap（默认 76）软换行，只在行尾断行，不拆 =XX。
- 行尾空白（空格/制表符）编码为 =20/=09。
- 解码严格校验，错误带字节偏移。
"""

_TAB = 0x09
_LF = 0x0A
_SPACE = 0x20
_EQUALS = 0x3D
_HEX = frozenset(b"0123456789abcdefABCDEF")

MIN_WRAP = 4  # 至少要放得下 =XX 加行尾的 =


class QpError(Exception):
    """QP 内容不合法，带字节偏移。"""

    def __init__(self, message, offset=None):
        super().__init__(message)
        self.message = message
        self.offset = offset

    def __str__(self):
        if self.offset is None:
            return self.message
        return "偏移 %d：%s" % (self.offset, self.message)


def _check_wrap(wrap):
    if wrap < MIN_WRAP:
        raise QpError("wrap 至少为 %d（要放得下 =XX 与行尾的 =）" % MIN_WRAP)


def _tokens(line):
    """把一行输入（不含换行）拆成编码单元，每个单元 1 或 3 字节。"""
    trail = len(line)
    while trail > 0 and line[trail - 1] in (_SPACE, _TAB):
        trail -= 1
    for index, byte in enumerate(line):
        if byte in (_SPACE, _TAB):
            if index < trail:
                yield bytes([byte])
            else:
                yield b"=%02X" % byte
        elif 0x20 <= byte <= 0x7E and byte != _EQUALS:
            yield bytes([byte])
        else:
            yield b"=%02X" % byte


def _encode_line(line, wrap):
    """编码一行输入，按 wrap 软换行，逐片产出。"""
    limit = wrap - 1  # 行尾要留给软换行的 =
    current = bytearray()
    for token in _tokens(line):
        if current and len(current) + len(token) > limit:
            yield bytes(current) + b"=\n"
            current = bytearray()
        current += token
    if current:
        yield bytes(current)


def encode_chunks(chunks, wrap=76):
    """流式编码：吃字节块迭代器，逐片产出 QP 文本。内存 O(一行)。"""
    _check_wrap(wrap)
    buffer = bytearray()
    lines_seen = 0
    for chunk in chunks:
        if isinstance(chunk, str):
            chunk = chunk.encode("utf-8")
        buffer += chunk
        while True:
            newline = buffer.find(b"\n")
            if newline < 0:
                break
            line = bytes(buffer[:newline])
            del buffer[:newline + 1]
            if lines_seen:
                yield b"\n"
            yield from _encode_line(line, wrap)
            lines_seen += 1
    if lines_seen:
        yield b"\n"
    yield from _encode_line(bytes(buffer), wrap)


def encode(data, wrap=76):
    """把字节串编码成 QP 文本。"""
    return b"".join(encode_chunks([data], wrap))


def _decode_segment(data, base):
    """解码一段完整（不以半个转义结尾）的 QP 文本，base 是全局偏移起点。"""
    out = bytearray()
    at = 0
    end = len(data)
    while at < end:
        byte = data[at]
        if byte == _EQUALS:
            if at + 1 < end and data[at + 1] == _LF:
                at += 2  # 软换行：= 与换行都丢掉
                continue
            if at + 1 >= end:
                raise QpError("行尾孤立的 =（软换行需要 = 后紧跟换行）", base + at)
            if at + 2 >= end:
                raise QpError("= 后不足两位十六进制", base + at)
            pair = data[at + 1:at + 3]
            if pair[0] not in _HEX or pair[1] not in _HEX:
                raise QpError("= 后不是两位十六进制：%s" % pair.decode("ascii", "replace"),
                              base + at)
            out.append(int(pair, 16))
            at += 3
        elif byte in (_TAB, _LF) or 0x20 <= byte <= 0x7E:
            out.append(byte)
            at += 1
        else:
            raise QpError("非法字符 0x%02X" % byte, base + at)
    return bytes(out)


def decode_chunks(chunks):
    """流式解码：吃 QP 文本块迭代器，逐片产出字节。内存 O(1)（除输出）。"""
    carry = b""
    base = 0  # carry 首字节在全文中的偏移
    for chunk in chunks:
        if isinstance(chunk, str):
            chunk = chunk.encode("ascii")
        data = carry + chunk
        hold = 0
        if data.endswith(b"="):
            hold = 1
        elif len(data) >= 2 and data[-2] == _EQUALS:
            hold = 2
        if hold:
            body, carry = data[:-hold], data[-hold:]
        else:
            body, carry = data, b""
        if body:
            yield _decode_segment(body, base)
            base += len(body)
    if carry:
        yield _decode_segment(carry, base)


def decode(data):
    """把 QP 文本解码成字节串。"""
    return b"".join(decode_chunks([data]))

"""quoted-printable：=XX 转义与软换行。只用标准库。

口径（与 README 一致）：

- 编码：0x3D 与所有不可打印字节写成 =XX；行尾的空格/制表符写成 =20/=09；
  按 wrap 列软换行（行尾 "=" 加换行），不把一个 =XX 拆到两行。
- 解码：=XX 还原成字节；行尾 =\\n 或 =\\r\\n 是软换行，两者都丢掉；
  = 后不是两位十六进制、行尾孤立 =、非法字符都报 QpError（带偏移）。
- iter_encode / iter_decode 是单遍流式接口，内存 O(一行)；
  encode / decode 是它们的一次性包装。
"""

MIN_WRAP = 4  # 至少要放得下 =XX（3 列）加行尾软换行的 =（1 列）

_HEX_VALUE = {}
for _c in b"0123456789":
    _HEX_VALUE[_c] = _c - 0x30
for _c in b"abcdef":
    _HEX_VALUE[_c] = _c - 0x61 + 10
for _c in b"ABCDEF":
    _HEX_VALUE[_c] = _c - 0x41 + 10

_SINGLE = tuple(bytes((b,)) for b in range(256))
_ESCAPE = tuple(b"=%02X" % b for b in range(256))
_TOKENS = tuple(
    _SINGLE[b]
    if (b in (0x20, 0x09) or (0x21 <= b <= 0x7E and b != 0x3D))
    else _ESCAPE[b]
    for b in range(256)
)


class QpError(Exception):
    """qp 内容不合法。offset 是出错字节在输入里的偏移。"""

    def __init__(self, message, offset):
        super().__init__(message)
        self.message = message
        self.offset = offset

    def __str__(self):
        return "%s（偏移 %d）" % (self.message, self.offset)


def _close_line(line, cap):
    """关闭一行：行尾空格/制表符转义成 =20/=09。

    返回 (行内容, 放不下的转义 token 或 None)；放不下的 token 归下一行行首。
    """
    if line and line[-1] in (0x20, 0x09):
        esc = _ESCAPE[line[-1]]
        del line[-1]
        if len(line) + 3 <= cap:
            line += esc
            return bytes(line), None
        return bytes(line), esc
    return bytes(line), None


def iter_encode(chunks, wrap=76):
    """单遍流式编码。chunks 是 bytes/str 的可迭代对象，逐行产出 bytes。"""
    if wrap < MIN_WRAP:
        raise ValueError("wrap 必须 >= %d（要放得下 =XX 和行尾的 =）" % MIN_WRAP)
    cap = wrap - 1  # 给行尾软换行的 "=" 留一列，保证每行（含 =）<= wrap
    tokens = _TOKENS
    line = bytearray()
    for chunk in chunks:
        if isinstance(chunk, str):
            chunk = chunk.encode("utf-8")
        for byte in chunk:
            token = tokens[byte]
            while len(line) + len(token) > cap:
                body, carry = _close_line(line, cap)
                yield body + b"=\n"
                line.clear()
                if carry is not None:
                    line += carry
            line += token
    if line:
        body, carry = _close_line(line, cap)
        if carry is None:
            yield body
        else:
            yield body + b"=\n"
            yield carry


def encode(data, wrap=76):
    """一次性编码。data 是 bytes 或 str。"""
    return b"".join(iter_encode((data,), wrap))


def iter_decode(chunks):
    """单遍流式解码。chunks 是 bytes/str 的可迭代对象，逐块产出 bytes。"""
    state = 0  # 0 正常 / 1 看到 = / 2 看到 = 加一位十六进制 / 3 看到 =\r
    eq_offset = 0
    hi = 0
    offset = 0
    hex_value = _HEX_VALUE
    for chunk in chunks:
        if isinstance(chunk, str):
            chunk = chunk.encode("utf-8")
        out = bytearray()
        for byte in chunk:
            if state == 0:
                if byte == 0x3D:
                    eq_offset = offset
                    state = 1
                elif byte in (0x09, 0x0A, 0x0D) or 0x20 <= byte <= 0x7E:
                    out.append(byte)
                else:
                    raise QpError("非法字符 0x%02X" % byte, offset)
            elif state == 1:
                if byte == 0x0A:
                    state = 0
                elif byte == 0x0D:
                    state = 3
                elif byte in hex_value:
                    hi = hex_value[byte]
                    state = 2
                else:
                    raise QpError("= 后必须是两位十六进制或软换行", eq_offset)
            elif state == 2:
                if byte in hex_value:
                    out.append(hi * 16 + hex_value[byte])
                    state = 0
                else:
                    raise QpError("= 后必须是两位十六进制", eq_offset)
            else:
                if byte == 0x0A:
                    state = 0
                else:
                    raise QpError("软换行的 \\r 后必须是 \\n", eq_offset)
            offset += 1
        if out:
            yield bytes(out)
    if state == 1:
        raise QpError("行尾孤立的 =", eq_offset)
    if state == 2:
        raise QpError("= 后只有一位十六进制", eq_offset)
    if state == 3:
        raise QpError("软换行的 \\r 后必须是 \\n", eq_offset)


def decode(data):
    """一次性解码。data 是 bytes 或 str。"""
    return b"".join(iter_decode((data,)))

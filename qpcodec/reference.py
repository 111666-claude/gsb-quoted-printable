"""参考实现：按规范逐步处理，优先清晰而非速度。

与 qpcodec.qp 的流式实现独立编写，用于测试里逐字节对照
（编码结果、解码结果、错误偏移都必须一致）。
"""

from .qp import QpError

_HEX = "0123456789ABCDEFabcdef"


def _token(byte):
    """一个字节 -> 一个 token：可打印字符原样，其余 =XX。"""
    if byte in (0x20, 0x09) or (0x21 <= byte <= 0x7E and byte != 0x3D):
        return chr(byte)
    return "=%02X" % byte


def _fix_line_end(line, cap):
    """行尾空格/制表符转义成 =20/=09；本行放不下就交给下一行行首。"""
    if line and line[-1] in " \t":
        esc = "=%02X" % ord(line[-1])
        head = line[:-1]
        if len(head) + 3 <= cap:
            return head + esc, ""
        return head, esc
    return line, ""


def ref_encode(data, wrap=76):
    """逐步编码：先逐字节展开成 token，再贪心成行，最后加软换行拼接。"""
    if isinstance(data, str):
        data = data.encode("utf-8")
    if wrap < 4:
        raise ValueError("wrap 必须 >= 4（要放得下 =XX 和行尾的 =）")
    cap = wrap - 1  # 给行尾软换行的 "=" 留一列

    tokens = [_token(byte) for byte in data]

    lines = []
    current = ""
    for token in tokens:
        while len(current) + len(token) > cap:
            fixed, carry = _fix_line_end(current, cap)
            lines.append(fixed)
            current = carry
        current += token
    fixed, carry = _fix_line_end(current, cap)
    lines.append(fixed)
    if carry:
        lines.append(carry)

    return "=\n".join(lines).encode("ascii")


def ref_decode(data):
    """逐步解码：按下标扫描，=XX 还原、软换行丢弃、非法输入带偏移报错。"""
    if isinstance(data, str):
        data = data.encode("utf-8")
    out = bytearray()
    at = 0
    size = len(data)
    while at < size:
        byte = data[at]
        if byte != 0x3D:
            if byte in (0x09, 0x0A, 0x0D) or 0x20 <= byte <= 0x7E:
                out.append(byte)
                at += 1
                continue
            raise QpError("非法字符 0x%02X" % byte, at)
        if at + 1 >= size:
            raise QpError("行尾孤立的 =", at)
        first = data[at + 1]
        if first == 0x0A:
            at += 2
            continue
        if first == 0x0D:
            if at + 2 < size and data[at + 2] == 0x0A:
                at += 3
                continue
            raise QpError("软换行的 \\r 后必须是 \\n", at)
        if chr(first) not in _HEX:
            raise QpError("= 后必须是两位十六进制或软换行", at)
        if at + 2 >= size:
            raise QpError("= 后只有一位十六进制", at)
        second = data[at + 2]
        if chr(second) not in _HEX:
            raise QpError("= 后必须是两位十六进制", at)
        out.append(int(chr(first) + chr(second), 16))
        at += 3
    return bytes(out)

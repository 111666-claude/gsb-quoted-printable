"""参考实现：严格按规范逐字节、逐行处理，用于和 qpcodec.qp 对照。

刻意写得直白（不求快），作为「规范本身」的可读形态。只用标准库。
"""

_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


class RefError(Exception):
    """参考实现的解码错误，带字节偏移。"""

    def __init__(self, message, offset):
        super().__init__(message)
        self.message = message
        self.offset = offset


def ref_encode(data, wrap=76):
    if isinstance(data, str):
        data = data.encode("utf-8")
    if wrap < 4:
        raise RefError("wrap 至少为 4", -1)
    out = []
    for index, line in enumerate(data.split(b"\n")):
        if index:
            out.append("\n")
        # 第一步：找出行尾空白（空格/制表符）的起点
        trail = len(line)
        while trail > 0 and line[trail - 1] in (0x20, 0x09):
            trail -= 1
        # 第二步：逐字节决定编码形态
        pieces = []
        for i, byte in enumerate(line):
            if byte in (0x20, 0x09):
                # 行内空白原样，行尾空白转义
                pieces.append(chr(byte) if i < trail else "=%02X" % byte)
            elif 0x20 <= byte <= 0x7E and byte != 0x3D:
                pieces.append(chr(byte))  # 可打印且非 = 原样
            else:
                pieces.append("=%02X" % byte)  # 其余（含 = 与行尾空白）转义
        # 第三步：贪心装行，每行留一个位置给软换行的 =
        current = ""
        for piece in pieces:
            if current and len(current) + len(piece) > wrap - 1:
                out.append(current + "=\n")
                current = ""
            current += piece
        if current:
            out.append(current)
    return "".join(out).encode("ascii")


def ref_decode(data):
    if isinstance(data, str):
        data = data.encode("ascii")
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        byte = data[i]
        if byte == 0x3D:  # '='
            if i + 1 < n and data[i + 1] == 0x0A:
                i += 2  # 软换行：= 与换行都丢掉
                continue
            if i + 1 >= n:
                raise RefError("行尾孤立的 =", i)
            if i + 2 >= n:
                raise RefError("= 后不足两位十六进制", i)
            if chr(data[i + 1]) not in _HEX_DIGITS or chr(data[i + 2]) not in _HEX_DIGITS:
                raise RefError("= 后不是两位十六进制", i)
            out.append(int(data[i + 1:i + 3], 16))
            i += 3
        elif byte in (0x09, 0x0A) or 0x20 <= byte <= 0x7E:
            out.append(byte)
            i += 1
        else:
            raise RefError("非法字符 0x%02X" % byte, i)
    return bytes(out)

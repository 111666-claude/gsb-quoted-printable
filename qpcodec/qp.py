"""quoted-printable：=XX 转义与软换行。只用标准库。"""

import string

PRINTABLE = set(bytes(string.printable, "ascii")) - {0x0b, 0x0c}


class QpError(Exception):
    """qp 内容不合法。缺陷：不带位置。"""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def encode(data):
    """编码。缺陷：不转义等号本身，也不做 76 列的软换行。"""
    if isinstance(data, str):
        data = data.encode("utf-8")
    out = bytearray()
    for byte in data:
        if byte in PRINTABLE:
            out.append(byte)
        else:
            out.extend(("=%02X" % byte).encode("ascii"))
    return bytes(out)


def decode(data):
    """解码。缺陷：不认软换行（'=\\n'），也不校验 = 后面必须是两位十六进制。"""
    if isinstance(data, str):
        data = data.encode("ascii")
    out = bytearray()
    at = 0
    while at < len(data):
        byte = data[at]
        if byte == 0x3D and at + 2 < len(data):
            try:
                out.append(int(data[at + 1:at + 3], 16))
            except ValueError:
                raise QpError("= 后面不是两位十六进制")
            at += 3
            continue
        out.append(byte)
        at += 1
    return bytes(out)

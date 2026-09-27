"""quoted-printable 编解码。"""

from .qp import QpError, decode, encode, iter_decode, iter_encode

__all__ = ["QpError", "decode", "encode", "iter_decode", "iter_encode"]

"""quoted-printable 编解码。"""

from .qp import QpError, decode, decode_chunks, encode, encode_chunks

__all__ = ["QpError", "decode", "decode_chunks", "encode", "encode_chunks"]

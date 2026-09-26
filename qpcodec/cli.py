"""命令行入口：按十六进制输入输出，方便核对字节。"""

import argparse
import sys

from .qp import QpError, decode, encode


def build_parser():
    parser = argparse.ArgumentParser(prog="quoted-printable", description="QP 编解码")
    parser.add_argument("--encode-hex", help="把这段十六进制编码成 QP")
    parser.add_argument("--decode", help="把这段 QP 文本解码成十六进制")
    parser.add_argument("--wrap", type=int, default=76, help="软换行宽度（默认 76）")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.encode_hex:
            print(encode(bytes.fromhex(args.encode_hex)).decode("ascii"))
            return 0
        if args.decode is not None:
            text = args.decode.replace("\\n", "\n")
            print(decode(text).hex())
            return 0
    except (QpError, ValueError) as error:
        print("错误：%s" % error, file=sys.stderr)
        return 1
    print("错误：需要 --encode-hex 或 --decode", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

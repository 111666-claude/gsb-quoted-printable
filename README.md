# quoted-printable

quoted-printable 编解码（`=XX` 转义与软换行），只用 Python 标准库。

```
python3 -m qpcodec.cli --encode-hex 3D
python3 -m qpcodec.cli --decode "ab=\ncd"
python3 -m unittest discover -s tests -v
```

## 口径（README 为准）

- **`=` 本身必须转义成 `=3D`**：`--encode-hex 3D` 现在直接输出 `=`，按口径应该是 `=3D`。
- **软换行要认**：行尾的 `=` 加换行表示续行，解码时要把两者都丢掉（不产生任何字节）。
  `--decode "ab=\ncd"` 现在输出 `61620c64`（把 `=\n` 当成 `=0C`），按口径应该是 `61626364`（即 `abcd`）。
- 编码要按 `--wrap`（默认 76）软换行：只在**行尾**断，且不许把一个 `=XX` 拆到两行；
  编码结果里除了行尾的 `=` 与换行，不出现裸 `=`。
- 解码要校验：`=` 后面必须是两位十六进制（`=ZZ`、`=A`、行尾孤立的 `=` 都要报错并给偏移）。
- 不变量：`decode(encode(x)) == x`（任意字节串）；`encode` 的每行长度 ≤ wrap；同一输入重复结果相同。
- 规模：100 MB 单遍流式编解码，内存 O(一行)。

## 现在的行为

- `=`（0x3D）与不可打印字节一律转义成 `=XX`；行尾空白转义成 `=20`/`=09`。
- 解码认软换行：行尾的 `=` 加换行被丢掉（`ab=\ncd` → `abcd`）。
- `--wrap N`（默认 76）生效：只在行尾断行，不拆开 `=XX`，除行尾的 `=` 与换行外没有裸 `=`。
- 解码严格校验：`=ZZ`、`=A`、行尾孤立 `=`、非法字符都报错并给出字节偏移。
- 流式接口 `encode_chunks` / `decode_chunks`：单遍处理，内存 O(一行)。

## 计划新增的能力

```
--wrap N        软换行宽度（默认 76）
--encode-hex    用十六进制传输入，便于复现
```

## 输出

```
QP 文本 / 十六进制
```

## 目录

```
qpcodec/qp.py   编解码与校验
qpcodec/cli.py  命令行入口
tests/          unittest 用例
```

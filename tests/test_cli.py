import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "qpcodec.cli", *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


class CliTest(unittest.TestCase):
    def test_encode_hex_equals(self):
        result = run_cli("--encode-hex", "3D")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "=3D\n")

    def test_decode_soft_break(self):
        result = run_cli("--decode", "ab=\\ncd")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "61626364\n")

    def test_wrap_option(self):
        result = run_cli("--encode-hex", "41" * 100, "--wrap", "10")
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.rstrip("\n").split("\n")
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(len(line), 10)

    def test_decode_error_reports_offset(self):
        result = run_cli("--decode", "=ZZ")
        self.assertEqual(result.returncode, 1)
        self.assertIn("偏移", result.stderr)

    def test_empty_encode(self):
        result = run_cli("--encode-hex", "")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "\n")

    def test_no_args(self):
        result = run_cli()
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()

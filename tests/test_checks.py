import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/collab/scripts"))
from collablib.checks import capture_check, OUTPUT_LIMIT


class CheckExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def run_code(self, code, timeout=5):
        return capture_check([sys.executable, "-c", code], self.temp.name, timeout)

    def test_noisy_check_is_drained_without_retaining_unlimited_output(self):
        out, code = self.run_code("import sys; sys.stdout.buffer.write(b'x' * 3000000)")
        self.assertEqual(code, 0)
        self.assertLessEqual(len(out), OUTPUT_LIMIT + 100)
        self.assertIn(b"[output truncated]", out)

    def test_timeout_is_finite_and_keeps_output(self):
        before = time.monotonic()
        out, code = self.run_code("import time; print('starting', flush=True); time.sleep(60)", timeout=1)
        self.assertEqual(code, 124)
        self.assertLess(time.monotonic() - before, 12)
        self.assertIn(b"starting", out)
        self.assertIn(b"timed out", out)

    def test_internal_credentials_and_fault_injection_are_not_inherited(self):
        with mock.patch.dict(os.environ, {"COLLAB_TOKEN": "private", "COLLAB_TEST_CRASH": "after_wal"}):
            out, code = self.run_code("import os; print(os.getenv('COLLAB_TOKEN'), os.getenv('COLLAB_TEST_CRASH'))")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), b"None None")

    def test_failure_and_nonexistent_command_are_recorded(self):
        out, code = self.run_code("import sys; print('failure'); sys.exit(7)")
        self.assertEqual(code, 7)
        self.assertIn(b"failure", out)
        _, code = capture_check([str(Path(self.temp.name) / "missing-executable")], self.temp.name, 1)
        self.assertEqual(code, 127)


if __name__ == "__main__":
    unittest.main()

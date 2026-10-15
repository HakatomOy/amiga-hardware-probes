import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_rom


class RunRomProvenanceTests(unittest.TestCase):
    def test_hash_is_taken_before_process_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "copperline.exe"
            binary.write_bytes(b"running build")
            launched = []

            def fake_popen(command, **kwargs):
                launched.append(command)
                binary.write_bytes(b"replacement build")
                return "process"

            with patch.object(run_rom.subprocess, "Popen", fake_popen):
                proc, binary_sha256 = run_rom._popen_with_binary_hash(
                    binary, [str(binary)], cwd=root)

            self.assertEqual(proc, "process")
            self.assertEqual(launched, [[str(binary)]])
            self.assertEqual(binary_sha256, hashlib.sha256(b"running build").hexdigest())
            self.assertNotEqual(binary_sha256, run_rom._sha256(binary))

    def test_changed_binary_is_recorded_then_capture_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            binary = out / "copperline.exe"
            binary.write_bytes(b"replacement build")
            original_hash = hashlib.sha256(b"running build").hexdigest()

            with self.assertRaisesRegex(RuntimeError, "binary changed during the run"):
                run_rom._write_invocation(
                    out, binary, [str(binary)], original_hash, 1.25)

            invocation = json.loads((out / "invocation.json").read_text())
            self.assertEqual(invocation["binary_sha256"], original_hash)
            self.assertTrue(invocation["binary_changed_during_run"])
            self.assertEqual(invocation["wall_seconds"], 1.25)

    def test_unchanged_binary_is_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            binary = out / "copperline.exe"
            binary.write_bytes(b"same build")
            digest = run_rom._sha256(binary)

            run_rom._write_invocation(out, binary, [str(binary)], digest, 2.0)

            invocation = json.loads((out / "invocation.json").read_text())
            self.assertEqual(invocation["binary_sha256"], digest)
            self.assertFalse(invocation["binary_changed_during_run"])


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from tools import run_rom_irq_latency as diagnostic


class IRQLatencyRunnerTests(unittest.TestCase):
    def test_popen_receives_override_and_original_is_restored(self):
        runner = diagnostic.run_rom.subprocess
        original = runner.Popen
        calls = []

        def fake_popen(*args, **kwargs):
            calls.append((args, kwargs))
            return "process"

        runner.Popen = fake_popen
        try:
            result = diagnostic._invoke_with_latency(
                lambda: runner.Popen(["copperline"], env={"KEEP": "yes"}), 5)
            self.assertEqual(result, "process")
            self.assertEqual(calls[0][1]["env"], {
                "KEEP": "yes", "COPPERLINE_IRQ_LATENCY_CCK": "5"})
            self.assertIs(runner.Popen, fake_popen)
        finally:
            runner.Popen = original

    def test_original_popen_is_restored_when_callback_raises(self):
        runner = diagnostic.run_rom.subprocess
        original = runner.Popen
        runner.Popen = lambda *args, **kwargs: None
        fake_original = runner.Popen
        try:
            with self.assertRaisesRegex(RuntimeError, "expected"):
                diagnostic._invoke_with_latency(
                    lambda: (_ for _ in ()).throw(RuntimeError("expected")), 3)
            self.assertIs(runner.Popen, fake_original)
        finally:
            runner.Popen = original

    def test_latency_bounds_are_enforced(self):
        for value in (-1, 17, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                diagnostic._validate_latency(value)
        diagnostic._validate_latency(0)
        diagnostic._validate_latency(16)

    def test_outputs_are_marked_diagnostic_without_changing_command_or_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            binary = out / "copperline.exe"
            binary.write_bytes(b"binary")
            manifest = {"source_id": "original", "trial_count": 12}
            invocation = {"command": ["copperline", "rom.bin"],
                          "binary_sha256": "original-hash", "wall_seconds": 3.0}
            results = {"metadata": {"source_id": "original"}, "records": []}
            (out / "build-manifest.json").write_text(json.dumps(manifest))
            (out / "invocation.json").write_text(json.dumps(invocation))
            (out / "results.json").write_text(json.dumps(results))

            diagnostic._mark_diagnostic(out, binary, 4)

            marked_manifest = json.loads((out / "build-manifest.json").read_text())
            marked_invocation = json.loads((out / "invocation.json").read_text())
            marked_results = json.loads((out / "results.json").read_text())
            marker = json.loads((out / "diagnostic.json").read_text())
            self.assertEqual(marked_manifest["source_id"], "original")
            self.assertTrue(marked_manifest["diagnostic_only"])
            self.assertEqual(marked_manifest["diagnostic_irq_latency_cck"], 4)
            self.assertEqual(marked_invocation["command"], invocation["command"])
            self.assertEqual(marked_invocation["binary_sha256"], "original-hash")
            self.assertEqual(marked_results["metadata"]["source_id"], "original")
            self.assertTrue(marked_results["metadata"]["diagnostic_only"])
            self.assertFalse(marker["accepted_as_final_comparison"])
            self.assertEqual(marker["environment_override"], {
                "COPPERLINE_IRQ_LATENCY_CCK": "4"})


if __name__ == "__main__":
    unittest.main()

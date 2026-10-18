import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import rom_results
from tests.test_compare_captures import fixture

SPEC = importlib.util.spec_from_file_location("replay_accuracy", Path(__file__).parents[1] / "tools/replay_accuracy.py")
replay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay)


class ReplayAccuracyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        reference = self.root / "captures/hardware"
        reference.mkdir(parents=True)
        self.write_results(reference)
        archive = self.root / "build/rom"
        archive.mkdir(parents=True)
        (archive / "manifest.json").write_text("{}")
        self.binary = self.root / "source.exe"
        self.binary.write_bytes(b"immutable executable snapshot")
        self.config = self.root / "machine.toml"
        self.config.write_text("[machine]\n")
        self.out = self.root / "replay"
        self.args = ["--binary", str(self.binary), "--config", str(self.config), "--out", str(self.out)]

    @staticmethod
    def write_results(folder):
        data = fixture()
        meta, rows = rom_results.decode(data)
        (folder / "results.bin").write_bytes(data)
        (folder / "results.json").write_text(json.dumps({"metadata": meta, "records": rows}))

    def invoke(self, runner):
        with patch.object(replay, "ROOT", self.root), patch.object(replay, "SUITES", {"cia-irq": ("rom", "captures/hardware")}), patch.object(replay.run_rom, "run", runner), contextlib.redirect_stdout(io.StringIO()) as output:
            status = replay.main(self.args)
        return status, output.getvalue()

    def test_replay_uses_snapshot_and_returns_only_summary(self):
        def run(binary, destination, config, archive):
            self.assertNotEqual(binary, self.binary)
            self.assertEqual(binary.read_bytes(), self.binary.read_bytes())
            destination.mkdir()
            self.write_results(destination)
            print("verbose runner evidence")
        status, output = self.invoke(run)
        self.assertEqual(status, 0)
        self.assertNotIn("verbose runner", output)
        summary = json.loads((self.out / "summary.json").read_text())
        self.assertEqual(summary["suites"]["cia-irq"]["raw_counts"]["match"], 3)
        self.assertIn("verbose runner", (self.out / "cia-irq.log").read_text())

    def test_failure_preserves_log_and_produces_bounded_error(self):
        def fail(*args):
            print("original diagnostic")
            raise RuntimeError("failed " + "x" * 10000)
        status, output = self.invoke(fail)
        self.assertEqual(status, 2)
        self.assertLess(len(output), 1000)
        self.assertIn("original diagnostic", (self.out / "cia-irq.log").read_text())
        self.assertIn("error", json.loads((self.out / "summary.json").read_text())["suites"]["cia-irq"])

    def test_existing_output_is_never_overwritten(self):
        self.out.mkdir()
        with self.assertRaises(FileExistsError):
            self.invoke(lambda *args: self.fail("runner must not start"))

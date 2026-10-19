import importlib.util
import json
from pathlib import Path
import tempfile
import struct
import unittest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("save_reference", ROOT / "tools/save_reference.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ReferenceTests(unittest.TestCase):
    def test_unverified_restore_is_rejected_before_output_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            src = Path(folder)
            (src / "build-manifest.json").write_text("{}")
            (src / "restoration.json").write_text(json.dumps(dict(restored_verified=False)))
            out = src / "reference"
            with self.assertRaisesRegex(ValueError, "restoration"):
                mod.save(src, out, "pending", "unknown")
            self.assertFalse(out.exists())

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "capture"
            (source / "capture").mkdir(parents=True)
            packet = bytearray(104)
            packet[:8] = b"A5RBCP01"
            struct.pack_into(">HHIII", packet, 8, 1, 40, 1, 104, 0)
            struct.pack_into(">4H", packet, 56, 0xa000, 0xffff, 1, 1)
            struct.pack_into(">I", packet, 20, (-sum(struct.unpack(">26I", packet))) & 0xffffffff)
            (source / "capture/results.bin").write_bytes(packet)
            (source / "build-manifest.json").write_text(json.dumps(dict(
                source_id="00"*32, trial_count=1, trials=[[0]*6], rom_sha256="11"*32)))
            (source / "restoration.json").write_text(json.dumps(dict(
                restored_verified=True, reset_release_verified=True, errors=[])))
            out = Path(folder) / "reference"
            first = mod.save(source, out, "pending", "unknown")
            self.assertEqual(first["record_count"], 1)
            original = (out / "results.bin").read_bytes()
            with self.assertRaises(FileExistsError):
                mod.save(source, out, "changed", "changed")
            self.assertEqual((out / "results.bin").read_bytes(), original)

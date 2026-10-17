import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools import run_onerom_live as live


class FakeOneROM:
    def __init__(self):
        self.memory = bytes((index * 17 + 3) & 0xFF for index in range(live.ROM_BYTES))
        self.pin_states = []
        self.commands = []

    def run(self, command, **_kwargs):
        self.commands.append(command)
        args = command[1:]
        if args[:2] == ["--serial", "SERIAL-1"]:
            args = args[2:]
        if args[:2] == ["inspect", "info"]:
            return SimpleNamespace(returncode=0, stdout="Serial: SERIAL-1\n", stderr="")
        if args[:1] == ["peek"]:
            output = Path(args[args.index("--output") + 1])
            output.write_bytes(self.memory)
            return SimpleNamespace(returncode=0, stdout="read ok\n", stderr="")
        if args[:2] == ["control", "pin"]:
            self.pin_states.append(args[args.index("--state") + 1])
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args[:3] == ["control", "poke", "live"]:
            payload = Path(args[args.index("--input") + 1]).read_bytes()
            self.memory = payload
            return SimpleNamespace(returncode=0, stdout="write ok\n", stderr="")
        raise AssertionError(f"unexpected OneROM command: {command}")


class FakeChild:
    pid = 43210

    def __init__(self, returncode=None):
        self.returncode = returncode

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            raise AssertionError("fake child should be stopped by the injected tree killer")
        return self.returncode


def make_romdir(root):
    romdir = root / "roms"
    romdir.mkdir()
    source_id = "a1" * 32
    normal = bytearray((index * 13 + 7) & 0xFF for index in range(live.ROM_BYTES))
    # The result header layout is magic + 16 bytes through the three longwords,
    # followed by the source fingerprint at offset +24.
    header_at = 0x1000
    normal[header_at:header_at + 8] = b"A5RBCP01"
    normal[header_at + 24:header_at + 56] = bytes.fromhex(source_id)
    normal = bytes(normal)
    swapped = live._swap_words(normal)
    (romdir / "a500-timing-rom.bin").write_bytes(normal)
    (romdir / "a500-timing-rom-onerom.bin").write_bytes(swapped)
    manifest = {
        "source_id": source_id,
        "rom_sha256": hashlib.sha256(normal).hexdigest(),
        "onerom_sha256": hashlib.sha256(swapped).hexdigest(),
        "trial_count": 1,
    }
    (romdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return romdir


class LiveOneROMTests(unittest.TestCase):
    def test_wrong_manifest_hash_fails_before_output_or_hardware(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            romdir = make_romdir(root)
            manifest_path = romdir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["rom_sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            fake = FakeOneROM()
            out = root / "capture"

            with self.assertRaisesRegex(ValueError, "rom_sha256"):
                live.collect_live("onerom", romdir, out, runner=fake.run)

            self.assertFalse(out.exists())
            self.assertEqual(fake.commands, [])

    def test_failed_collection_restores_fresh_live_backup_under_reset(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            romdir = make_romdir(root)
            fake = FakeOneROM()
            backup = fake.memory
            out = root / "capture"
            child_commands = []

            def fail_to_start(command, **_kwargs):
                child_commands.append(command)
                raise OSError("simulated collector launch failure")

            with self.assertRaisesRegex(OSError, "simulated collector"):
                live.collect_live("onerom", romdir, out, serial="SERIAL-1",
                                  runner=fake.run, popen_factory=fail_to_start)

            self.assertEqual(fake.memory, backup)
            self.assertEqual(fake.pin_states, ["low", "low", "z"])
            restoration = json.loads((out / "restoration.json").read_text(encoding="utf-8"))
            self.assertTrue(restoration["write_attempted"])
            self.assertTrue(restoration["restored_verified"])
            self.assertTrue(restoration["reset_release_verified"])
            self.assertEqual(restoration["backup_sha256"], hashlib.sha256(backup).hexdigest())
            self.assertEqual((out / "live-before.bin").read_bytes(), backup)
            self.assertIn("--serial", child_commands[0])
            self.assertIn("SERIAL-1", child_commands[0])

    def test_early_receiver_failure_restores_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            romdir = make_romdir(root)
            fake = FakeOneROM()
            backup = fake.memory
            out = root / "capture"
            child = FakeChild(returncode=9)

            with self.assertRaisesRegex(RuntimeError, "before receiver readiness"):
                live.collect_live(
                    "onerom", romdir, out, runner=fake.run,
                    popen_factory=lambda *_args, **_kwargs: child,
                )

            self.assertEqual(fake.memory, backup)
            restoration = json.loads((out / "restoration.json").read_text(encoding="utf-8"))
            self.assertTrue(restoration["restored_verified"])
            self.assertTrue(restoration["reset_release_verified"])

    def test_collection_timeout_kills_only_child_tree_then_restores(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            romdir = make_romdir(root)
            fake = FakeOneROM()
            backup = fake.memory
            out = root / "capture"
            child = FakeChild()
            clock = [0.0]
            killed = []

            def spawn(_command, **_kwargs):
                capture = out / "capture"
                capture.mkdir()
                (capture / "invocation.json").write_text("{}", encoding="utf-8")
                (capture / "console.log").write_bytes(b"")
                return child

            def kill_tree(process):
                killed.append(process.pid)
                process.returncode = -9

            def sleep_for(seconds):
                clock[0] += seconds

            with self.assertRaisesRegex(TimeoutError, "collection exceeded"):
                live.collect_live(
                    "onerom", romdir, out, timeout=1, runner=fake.run,
                    popen_factory=spawn, tree_killer=kill_tree,
                    sleep_fn=sleep_for, monotonic_fn=lambda: clock[0],
                )

            self.assertEqual(killed, [child.pid])
            self.assertEqual(fake.memory, backup)
            restoration = json.loads((out / "restoration.json").read_text(encoding="utf-8"))
            self.assertTrue(restoration["restored_verified"])
            self.assertTrue(restoration["reset_release_verified"])


if __name__ == "__main__":
    unittest.main()

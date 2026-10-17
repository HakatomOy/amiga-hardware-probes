from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import compare_b_hold


class CompareBHoldTests(unittest.TestCase):
    def _write_capture(self, root, name, *, source_id="11" * 32,
                       descriptor_mutation=None, word_mutation=None):
        folder = root / name
        folder.mkdir()
        descriptor_base = [48, 0, 48, 0, 0]
        rows = []
        data = bytearray(64 + 8 * 40)
        data[:8] = b"A5RBCP01"
        struct.pack_into(">HHIII", data, 8, 1, 40, 8, len(data), 0)
        data[24:56] = bytes.fromhex(source_id)
        struct.pack_into(">4H", data, 56, 0xA000, 0xFFFF, 1, 1)
        for repeat in range(8):
            descriptor = descriptor_base.copy()
            if descriptor_mutation is not None:
                descriptor[1] = descriptor_mutation
            row = descriptor + [repeat] + [0] * 14
            if word_mutation:
                word_index, mask = word_mutation
                if repeat == 0:
                    row[word_index] ^= mask
            struct.pack_into(">20H", data, 64 + repeat * 40, *row)
            rows.append(row)
        words = struct.unpack(">" + "I" * (len(data) // 4), data)
        struct.pack_into(">I", data, 20, (-sum(words)) & 0xFFFFFFFF)
        (folder / "results.bin").write_bytes(data)
        manifest = {
            "source_id": source_id,
            "trial_count": len(rows),
            "trials": [row[:6] for row in rows],
        }
        (folder / "build-manifest.json").write_text(json.dumps(manifest))
        return folder

    def test_compares_all_eight_dmaconr_reads_including_offset_34_flags(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hardware = self._write_capture(root, "hardware")
            emulator = self._write_capture(
                root, "emulator", word_mutation=(17, (1 << 14) | (1 << 13))
            )
            report = compare_b_hold.compare(hardware, [emulator])
        result = report["emulators"][0]
        self.assertEqual(report["record_layout"]["dmaconr_byte_offsets"], list(range(20, 36, 2)))
        self.assertEqual(result["dmaconr_read_mismatch_rows"]["+34"], 1)
        self.assertEqual(result["dmaconr_flag_mismatch_counts"]["bbusy"], 1)
        self.assertEqual(result["dmaconr_flag_mismatch_counts"]["bzero"], 1)

    def test_rejects_source_id_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hardware = self._write_capture(root, "hardware")
            emulator = self._write_capture(root, "emulator", source_id="22" * 32)
            with self.assertRaisesRegex(ValueError, "source_id mismatch"):
                compare_b_hold.compare(hardware, [emulator])

    def test_rejects_descriptor_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hardware = self._write_capture(root, "hardware")
            emulator = self._write_capture(root, "emulator", descriptor_mutation=1)
            with self.assertRaisesRegex(ValueError, "Descriptor/count mismatch"):
                compare_b_hold.compare(hardware, [emulator])

    def test_loads_json_capture_when_raw_binary_is_absent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hardware = self._write_capture(root, "hardware")
            emulator = self._write_capture(root, "emulator")
            raw = (emulator / "results.bin").read_bytes()
            rows = [struct.unpack_from(">20H", raw, 64 + index * 40)
                    for index in range(8)]
            records = []
            for row in rows:
                record = {name: row[index] for index, name in enumerate(compare_b_hold.FIELD_NAMES)
                          if index not in (14, 15)}
                record["saved_pc_offset"] = (row[14] << 16) | row[15]
                records.append(record)
            (emulator / "results.bin").unlink()
            (emulator / "results.json").write_text(json.dumps({
                "metadata": {"source_id": "11" * 32, "record_count": 8},
                "records": records,
            }))
            report = compare_b_hold.compare(hardware, [emulator])
        self.assertEqual(report["emulators"][0]["exact_mismatch_rows"], 0)
        self.assertEqual(report["emulators"][0]["validation_level"], "json_and_manifest")

    def test_reports_repeat_variation_without_rejecting_capture(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hardware = self._write_capture(root, "hardware", word_mutation=(17, 0x2000))
            emulator = self._write_capture(root, "emulator")
            report = compare_b_hold.compare(hardware, [emulator])
        stability = report["hardware_repeat_stability"]
        self.assertEqual(stability["group_count"], 1)
        self.assertEqual(stability["unstable_group_count"], 1)
        self.assertEqual(stability["groups_with_word_variation_by_byte_offset"]["+34"], 1)


if __name__ == "__main__":
    unittest.main()

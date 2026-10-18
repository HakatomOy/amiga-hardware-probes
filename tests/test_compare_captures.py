import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

import compare_captures as cc
import rom_results


def fixture():
    data = bytearray(64 + 3 * 40)
    data[:8] = b"A5RBCP01"
    struct.pack_into(">HHIII", data, 8, 1, 40, 3, len(data), 0)
    data[24:56] = bytes(range(32))
    struct.pack_into(">4H", data, 56, 0, 0, 0, 1)
    for i in range(3):
        words = [51, 0, 0, 0, i, 0] + [0] * 14
        words[13] = 2
        words[17] = 1
        struct.pack_into(">20H", data, 64 + i * 40, *words)
    checksum = -sum(struct.unpack(">" + str(len(data) // 4) + "I", data)) & 0xffffffff
    struct.pack_into(">I", data, 20, checksum)
    return bytes(data)


class CompareCapturesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.a = self.write("hardware")
        self.b = self.write("candidate")

    def write(self, name):
        folder = self.root / name
        folder.mkdir()
        data = fixture()
        meta, rows = rom_results.decode(data)
        (folder / "results.bin").write_bytes(data)
        (folder / "results.json").write_text(json.dumps({"metadata": meta, "records": rows}))
        return folder

    def compare(self):
        return cc.compare(cc.load_capture(self.a), cc.load_capture(self.b))

    def edit_json_only(self, change):
        path = self.b / "results.json"
        doc = json.loads(path.read_text())
        change(doc)
        path.write_text(json.dumps(doc))

    def test_identical_captures_have_complete_accounting(self):
        self.assertEqual(self.compare()["counts"], dict(total=3, match=3, mismatch=0, missing=0, invalid=0))

    def test_corrupted_binary_is_rejected(self):
        path = self.b / "results.bin"
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "Checksum"):
            cc.load_capture(self.b)

    def test_edited_json_cannot_hide_behind_binary(self):
        self.edit_json_only(lambda d: d["records"][0].update(counter=9))
        with self.assertRaisesRegex(ValueError, "JSON differs"):
            cc.load_capture(self.b)

    def test_removed_row_reported_for_json_only_input(self):
        (self.b / "results.bin").unlink()
        self.edit_json_only(lambda d: d["records"].pop(1))
        report = self.compare()
        self.assertEqual(report["counts"]["missing"], 1)
        self.assertEqual(report["counts"]["total"], 3)
        self.assertEqual(cc.load_capture(self.b)["declared_count_delta"], 1)

    def test_launch_shift_is_visible_without_hidden_alignment(self):
        (self.b / "results.bin").unlink()
        self.edit_json_only(lambda d: d["records"][1].update(launch_beam=1, irq_beam=1))
        report = self.compare()
        self.assertEqual(report["counts"]["mismatch"], 1)
        self.assertEqual(report["patterns"][0]["fields"], ["launch_beam", "irq_beam"])
        self.assertEqual(report["first_divergence"]["case"], "51:0:0:0:1:0")

    def test_duplicates_and_bad_status_are_invalid(self):
        (self.b / "results.bin").unlink()
        self.edit_json_only(lambda d: d["records"].append(copy.deepcopy(d["records"][0])))
        self.edit_json_only(lambda d: d["records"][1].update(status=1))
        self.assertEqual(self.compare()["counts"]["invalid"], 2)

    def test_source_mismatch_rejected(self):
        (self.b / "results.bin").unlink()
        self.edit_json_only(lambda d: d["metadata"].update(source_id="ff" * 32))
        with self.assertRaisesRegex(ValueError, "source_id mismatch"):
            self.compare()

    def test_event_shift_and_removal_first_divergence_window(self):
        key = "51:0:0:0:0:0"
        events = [{"time": i * 10, "event": "irq", "level": 2} for i in range(6)]
        for folder in (self.a, self.b):
            (folder / "events.json").write_text(json.dumps({"unit": "CCK", "cases": {key: events}}))
        changed = copy.deepcopy(events)
        changed[2]["time"] += 1
        changed.pop(4)
        (self.b / "events.json").write_text(json.dumps({"unit": "CCK", "cases": {key: changed}}))
        result = cc.compare(cc.load_capture(self.a), cc.load_capture(self.b), key, 1)
        trace = result["detail"]["trace"]
        self.assertEqual(trace["first_divergence_index"], 2)
        self.assertEqual(trace["start_index"], 1)
        self.assertEqual(len(trace["candidate"]), 3)
        self.assertEqual(trace["candidate"][1]["time"], 21)
        self.assertEqual(result["counts"]["mismatch"], 1)
        self.assertEqual(result["first_divergence"]["trace"]["first_divergence_index"], 2)
        changed = copy.deepcopy(events)
        changed.pop(2)
        (self.b / "events.json").write_text(json.dumps({"unit": "CCK", "cases": {key: changed}}))
        trace = cc.compare(cc.load_capture(self.a), cc.load_capture(self.b), key, 1)["detail"]["trace"]
        self.assertEqual(trace["first_divergence_index"], 2)

    def test_missing_trace_explicit_and_unknown_case_rejected(self):
        left, right = cc.load_capture(self.a), cc.load_capture(self.b)
        self.assertFalse(cc.compare(left, right, "51:0:0:0:0:0")["detail"]["trace"]["available"])
        with self.assertRaisesRegex(ValueError, "absent"):
            cc.compare(left, right, "51:0:0:0:9:0")

    def test_invalid_capture_has_machine_readable_report(self):
        (self.b / "results.bin").write_bytes(b"damaged")
        out = self.root / "report.json"
        code = cc.main(["--hardware", str(self.a), "--copperline", str(self.b), "--out", str(out)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.read_text())["invalid_capture_count"], 1)

    def test_opposite_deltas_are_separate_patterns(self):
        (self.b / "results.bin").unlink()
        reference = cc.load_capture(self.a)
        reference["records"]["51:0:0:0:1:0"]["counter"] = 4
        self.edit_json_only(lambda d: d["records"][0].update(counter=2))
        self.edit_json_only(lambda d: d["records"][1].update(counter=2))
        patterns = cc.compare(reference, cc.load_capture(self.b))["patterns"]
        self.assertEqual(len(patterns), 2)
        self.assertEqual({p["candidate_minus_hardware"]["counter"] for p in patterns}, {-2, 2})

    def test_malformed_container_and_empty_matrix_rejected(self):
        (self.b / "results.json").write_text("[]")
        with self.assertRaisesRegex(ValueError, "metadata"):
            cc.load_capture(self.b)
        (self.b / "results.bin").unlink()
        (self.b / "results.json").write_text("[]")
        with self.assertRaisesRegex(ValueError, "metadata"):
            cc.load_capture(self.b)
        meta, _ = rom_results.decode(fixture())
        (self.b / "results.json").write_text(json.dumps({"metadata": meta, "records": []}))
        with self.assertRaisesRegex(ValueError, "no observations"):
            cc.load_capture(self.b)

    def test_output_cannot_overwrite_inputs_or_related_files(self):
        for name in ("results.json", "results.bin", "events.json"):
            path = self.a / name
            before = path.read_bytes() if path.exists() else None
            with self.assertRaises(SystemExit) as raised:
                cc.main(["--hardware", str(self.a), "--copperline", str(self.b), "--out", str(path)])
            self.assertEqual(raised.exception.code, 2)
            self.assertEqual(path.read_bytes() if path.exists() else None, before)

    def test_eligible_mismatch_patterns_exclude_launch_noise(self):
        (self.b / "results.bin").unlink()
        self.edit_json_only(lambda d: d["records"][0].update(launch_beam=1))
        self.edit_json_only(lambda d: d["records"][1].update(counter=2))
        eligible = self.compare()["kind51_exact_launch_patterns"]
        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0]["fields"], ["counter"])

    def test_same_row_missing_everywhere_cannot_succeed(self):
        for folder in (self.a, self.b):
            (folder / "results.bin").unlink()
            path = folder / "results.json"
            document = json.loads(path.read_text())
            document["records"].pop()
            path.write_text(json.dumps(document))
        self.assertEqual(cc.main(["--hardware", str(self.a), "--copperline", str(self.b), "--out", str(self.root / "incomplete.json")]), 1)


if __name__ == "__main__":
    unittest.main()

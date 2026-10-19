import unittest
import tempfile
from pathlib import Path

import build_cia_hardware_verify as builder
import compare_cia_hardware as comparator


def row(kind=52):
    return dict(kind=kind, target=0, variant=0, phase=1, delay=4, repeat=0,
                launch_beam=0x4000, launch_ref=65525, end_beam=0x4020, end_ref=65524,
                counter=1, icr=0x40, irq_beam=0, irq_level=0x40,
                saved_pc_offset=0x3fff, status=0, aux=0x40,
                second_counter_or_beam=0, second_icr_or_level=65523)


class CIAHardwareVerifyTests(unittest.TestCase):
    def test_matrix_is_unique_and_contains_controls(self):
        rows = builder.trials()
        self.assertEqual(len(rows), 2272)
        self.assertEqual(len(set(rows)), len(rows))
        self.assertEqual(sum(r[0] == 52 for r in rows), 528)
        self.assertEqual(sum(r[0] == 53 for r in rows), 1600)
        self.assertEqual(sum(r[0] == 54 for r in rows), 144)
        self.assertTrue(any(r[:4] == (53, 1, 3, 4) for r in rows))
        self.assertEqual({r[-1] for r in rows}, {0, 1})

    def test_changed_serial_value_is_detected(self):
        a = row()
        result = comparator.compare([a], [dict(a, counter=9)])
        self.assertEqual(result["counts"]["mismatch"], 1)
        self.assertEqual(result["patterns"][0]["differences"], (("SP_and_IR", 0, 8),))
        self.assertEqual(comparator.compare([a], [dict(a, counter=3)])["counts"]["match"], 1)

    def test_pb_parity_change_and_missing_result_are_visible(self):
        a = row(53)
        self.assertEqual(comparator.compare([a], [dict(a, icr=0)])["counts"]["mismatch"], 1)
        self.assertEqual(comparator.compare([a], [])["counts"]["missing"], 1)

    def test_shifted_underflow_is_not_aligned_away(self):
        a = row()
        result = comparator.compare([a], [dict(a, launch_ref=a["launch_ref"]-1)])
        self.assertEqual(result["counts"]["different_underflow_brackets"], 1)
        self.assertEqual(result["counts"]["comparable"], 0)
        self.assertEqual(result["different_underflow_patterns"][0]["underflow_counts"], (("launch_ref", 10, 11),))

    def test_selected_irq_route_is_compared_without_unrelated_bits(self):
        a = row()
        self.assertEqual(comparator.compare([a], [dict(a, irq_beam=0x20)])["counts"]["match"], 1)
        result = comparator.compare([a], [dict(a, irq_beam=0x8)])
        self.assertEqual(result["counts"]["mismatch"], 1)
        self.assertEqual(result["patterns"][0]["differences"][0][0], "selected_INTREQ_before_ICR")

    def test_serial_stable_brackets_and_toggle_hypotheses(self):
        a = row()
        a["end_ref"] = a["launch_ref"]
        result = comparator.summarize([a])
        self.assertEqual(result["serial"][0]["stable_uf_with_sp_clear"], [10])
        b = dict(row(53), variant=1, aux=0, icr=0x40)
        group = comparator.summarize([b])["pb"][0]
        self.assertEqual(group["retained_initial_parity_failures"], 1)
        self.assertEqual(group["start_high_parity_failures"], 0)

    def test_corrupt_capture_is_rejected(self):
        source = Path(__file__).resolve().parents[1] / "references/cia-output-serial-v4-run1/results.bin"
        packet = bytearray(source.read_bytes())
        packet[-1] ^= 1
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "results.bin"
            path.write_bytes(packet)
            with self.assertRaises(ValueError):
                comparator.load(path)

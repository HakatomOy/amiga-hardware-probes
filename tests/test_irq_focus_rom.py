import hashlib
import unittest
from pathlib import Path

import build_irq_focus_rom as focus


class IRQFocusBuilderTests(unittest.TestCase):
    def test_default_matrix_is_unique_and_fits_payload(self):
        rows = focus.irq_focus_rows()
        self.assertEqual(len(rows), 8 * 4 * 64 + 4 * 41)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertLessEqual(len(rows), focus.MAX_ROWS)
        self.assertLessEqual(len(rows), focus.MAX_PAYLOAD_ROWS)
        self.assertEqual({row[0] for row in rows}, {43})
        self.assertEqual({row[1] for row in rows}, set(focus.DEFAULT_TARGETS))
        self.assertEqual({row[2] for row in rows}, {0})
        self.assertEqual({row[3] for row in rows}, set(range(4)))
        self.assertEqual({row[4] for row in rows}, set(range(64)))
        self.assertEqual({row[5] for row in rows}, {0})
        stop_delays = {row[4] for row in rows if row[1] == 10}
        self.assertEqual(stop_delays, set(range(focus.SAFE_STOP_MAX_DELAY + 1)))

    def test_selection_and_repeats_form_the_expected_cartesian_matrix(self):
        rows = focus.irq_focus_rows((10, 0), (3, 5), repeats=2)
        self.assertEqual(len(rows), 2 * 4 * 2 * 2)
        self.assertEqual({row[1] for row in rows}, {0, 10})
        self.assertEqual({row[3] for row in rows}, set(range(4)))
        self.assertEqual({row[4] for row in rows}, {3, 5})
        self.assertEqual({row[5] for row in rows}, {0, 1})
        self.assertEqual(len(rows), len(set(rows)))

    def test_stop_rows_are_capped_and_unsafe_only_selection_is_rejected(self):
        rows = focus.irq_focus_rows((1, 10), range(39, 43))
        by_target = {
            target: {row[4] for row in rows if row[1] == target}
            for target in (1, 10)
        }
        self.assertEqual(by_target[1], {39, 40, 41, 42})
        self.assertEqual(by_target[10], {39, 40})
        with self.assertRaisesRegex(ValueError, "target 10 STOP requires"):
            focus.irq_focus_rows((10,), range(41, 64))

    def test_all_targets_have_unique_labels_and_default_excludes_divides(self):
        target_ids = [row["target"] for row in focus.TARGETS]
        labels = [row["name"] for row in focus.TARGETS]
        self.assertEqual(target_ids, list(range(11)))
        self.assertEqual(len(labels), len(set(labels)))
        self.assertIn("COPER", focus.TARGETS[0]["name"])
        self.assertIn("Copper", focus.TARGETS[0]["description"])
        self.assertEqual(set(focus.DEFAULT_TARGETS), {0, 1, 2, 3, 4, 5, 6, 7, 10})
        self.assertEqual(focus.parse_targets("0, 8,10"), (0, 8, 10))

    def test_metadata_records_selection_provenance_and_descriptor_shape(self):
        rows = focus.irq_focus_rows((0, 10), range(2), repeats=2)
        snapshot = [dict(path="build_irq_focus_rom.py", sha256="b" * 64)]
        metadata = focus.irq_focus_metadata(rows, (0, 10), range(2), 2, snapshot)
        self.assertEqual(metadata["suite"], "irq_focus")
        self.assertEqual(metadata["row_count"], 32)
        self.assertEqual(metadata["delays"], [0, 1])
        self.assertEqual(metadata["repeats"], 2)
        self.assertEqual(metadata["phase_values"], list(range(4)))
        self.assertEqual(metadata["descriptor_fields"],
                         ["kind", "target", "variant", "phase", "delay", "repeat"])
        self.assertEqual(metadata["variant"]["variant"], 0)
        self.assertEqual(metadata["variant"]["name"], "COPER_INTREQ_mask_0x0010")
        self.assertEqual([item["target"] for item in metadata["targets"]], [0, 10])
        self.assertEqual(metadata["source_snapshot"], snapshot)
        self.assertEqual(metadata["measurement"]["kernel_base"], "0xf95000")
        self.assertEqual(metadata["measurement"]["kernel_slot_stride"], "0x400")
        self.assertEqual(metadata["measurement"]["straight_line_nops"], 128)
        self.assertEqual(metadata["measurement"]["entry_launch_offset"], 12)
        self.assertEqual(metadata["safe_stop_max_delay"], 40)
        self.assertEqual(metadata["source_sha256"], hashlib.sha256(
            Path(focus.__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest())

    def test_invalid_selections_and_oversized_matrices_are_rejected(self):
        for targets, delays, repeats in (
                ((), (0,), 1), ((11,), (0,), 1), ((0, 0), (0,), 1),
                ((0,), (), 1), ((0,), (96,), 1), ((0,), (0, 0), 1),
                ((0,), (0,), 0)):
            with self.subTest(targets=targets, delays=delays, repeats=repeats):
                with self.assertRaises(ValueError):
                    focus.irq_focus_rows(targets, delays, repeats)
        with self.assertRaises(ValueError):
            focus.irq_focus_rows((0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10), range(64))

    def test_cli_parsers_reject_bad_values(self):
        for value in ("", "1,1", "11", "x"):
            with self.subTest(value=value):
                with self.assertRaises(Exception):
                    focus.parse_targets(value)
        for value in ("1..0", "-1..2", "0..96", "bad"):
            with self.subTest(value=value):
                with self.assertRaises(Exception):
                    focus.parse_delays(value)


if __name__ == "__main__":
    unittest.main()

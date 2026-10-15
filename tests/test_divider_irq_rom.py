import unittest

from pathlib import Path
import hashlib

import build_divider_irq_rom as divider


class DividerIRQBuilderTests(unittest.TestCase):
    def test_default_matrix_fits_builder_memory_and_stays_below_row_limit(self):
        rows = divider.divider_irq_rows()
        self.assertEqual(len(rows), 2560)
        self.assertLessEqual(len(rows), divider.MAX_ROWS)
        self.assertLessEqual(len(rows), divider.MAX_PAYLOAD_ROWS)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual({row[0] for row in rows}, {20})
        self.assertEqual({row[1] for row in rows}, {0, 3})
        self.assertEqual({row[3] for row in rows}, set(range(4)))
        self.assertEqual({row[4] for row in rows}, set(range(64)))
        self.assertEqual({row[5] for row in rows}, {0})

    def test_operand_table_covers_sign_cases_and_overflow_categories(self):
        operands = divider.divider_irq_operands()
        divs = {row["variant"]: row for row in operands["DIVS"]}
        self.assertEqual(set(divs), set(range(1, 9)))
        self.assertEqual([(divs[i]["dividend"], divs[i]["divisor"]) for i in range(1, 6)],
                         [(100, 3), (100, -3), (-100, 3), (-100, -3), (0, -3)])
        self.assertEqual((divs[6]["dividend"], divs[6]["divisor"]), (100000, -2))
        actual_early_overflow = {
            variant: (abs(divs[variant]["dividend"]) >> 16)
            >= abs(divs[variant]["divisor"])
            for variant in (6, 7, 8)
        }
        self.assertEqual(actual_early_overflow, {6: False, 7: True, 8: True})
        self.assertEqual({variant for variant, early in actual_early_overflow.items() if early},
                         {variant for variant in (6, 7, 8)
                          if divs[variant]["overflow"] == "absolute_early"})
        divu = {row["variant"]: row for row in operands["DIVU"]}
        self.assertEqual(set(divu), {1, 2})
        self.assertIn("unsigned", divu[2]["description"])

    def test_kind20_asm_uses_operand_table_and_clears_stale_irq_after_alignment(self):
        asm = (Path(__file__).resolve().parents[1] / "src/rom/experiment.asm").read_text()
        trial = asm.split("divirq_sign_trial:", 1)[1].split("irq_paths_trial:", 1)[0]
        aligned = trial.index("bsr sync_beam")
        copper_start = trial.index("move.w #0,$88(a6)", aligned)
        timed_entry = trial.index("jsr $fb0000", copper_start)
        self.assertLess(aligned, copper_start)
        self.assertLess(copper_start, timed_entry)
        clear_irq = trial.index("move.w #$0010,$9c(a6)", timed_entry)
        enter_kernel = trial.index("jsr (a0)", clear_irq)
        self.assertLess(timed_entry, clear_irq)
        self.assertLess(clear_irq, enter_kernel)
        self.assertIn("move.l #$009c8010,(a0)+", trial)
        self.assertIn("lea divirq_sign_operands(pc),a0", trial)
        table = asm.split("divirq_sign_operands:", 1)[1].split("irq_paths_trial:", 1)[0]
        words = [line.strip() for line in table.splitlines()
                 if line.strip().startswith(("dc.l", "dc.w"))]
        self.assertEqual(words, [
            "dc.l 100", "dc.w 3,0", "dc.l 100", "dc.w -3,0",
            "dc.l -100", "dc.w 3,0", "dc.l -100", "dc.w -3,0",
            "dc.l 0", "dc.w -3,0", "dc.l 100000", "dc.w -2,0",
            "dc.l $10000000", "dc.w -1,0", "dc.l $80000000", "dc.w -1,0",
        ])

    def test_custom_delay_interval_and_repeats(self):
        rows = divider.divider_irq_rows(range(2, 5), repeats=2)
        self.assertEqual(len(rows), 10 * 4 * 3 * 2)
        self.assertEqual({row[4] for row in rows}, {2, 3, 4})
        self.assertEqual({row[5] for row in rows}, {0, 1})

    def test_metadata_retains_operand_and_provenance_details(self):
        rows = divider.divider_irq_rows(range(2), repeats=2)
        snapshot = [dict(path="build_divider_irq_rom.py", sha256="a" * 64)]
        metadata = divider.divider_irq_metadata(rows, range(2), 2, snapshot)
        self.assertEqual(metadata["suite"], "divider_irq")
        self.assertEqual(metadata["row_count"], 160)
        self.assertEqual(metadata["repeats"], 2)
        self.assertEqual(metadata["delays"], [0, 1])
        self.assertEqual(metadata["phase_values"], [0, 1, 2, 3])
        self.assertEqual(metadata["descriptor_fields"],
                         ["kind", "target", "variant", "phase", "delay", "repeat"])
        self.assertEqual(metadata["source_sha256"],
                         hashlib.sha256(
                             Path(divider.__file__).read_bytes().replace(
                                 b"\r\n", b"\n")).hexdigest())
        self.assertEqual(metadata["source_snapshot"], snapshot)
        self.assertEqual(len(metadata["operands"]["DIVS"]), 8)
        self.assertEqual(metadata["targets"][0]["target"], 3)
        self.assertIn("DMA disabled", metadata["observer"])

    def test_invalid_matrix_inputs_are_rejected(self):
        for delays, repeats in (([], 1), ([96], 1), ([2, 2], 1), ([0], 0)):
            with self.subTest(delays=delays, repeats=repeats):
                with self.assertRaises(ValueError):
                    divider.divider_irq_rows(delays, repeats)
        with self.assertRaises(ValueError):
            divider.divider_irq_rows(range(96), repeats=2)


if __name__ == "__main__":
    unittest.main()


import unittest

import compare_divider_irq as comparator


def capture(records, source_id="source", sha="capture"):
    return {"metadata": {"source_id": source_id, "sha256": sha}, "records": records}


def row(delay, launch=0x4281, status=0, pc=0x1234, marker=7,
        irq=0x6065, result=0x12345678, final_marker=9):
    return {
        "kind": 20, "target": 3, "variant": 1, "phase": 2,
        "delay": delay, "repeat": 0, "launch_beam": launch, "status": status,
        "saved_pc_offset": pc, "aux": marker, "irq_beam": irq,
        "counter": result >> 16, "icr": result & 0xffff,
        "second_icr_or_level": final_marker,
    }


class DividerIRQCompareTests(unittest.TestCase):
    def test_source_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Source ID mismatch"):
            comparator.compare(capture([row(0)]), capture([row(0)], source_id="other"))
        with self.assertRaisesRegex(ValueError, "Missing or empty source ID"):
            comparator.compare(capture([row(0)], source_id=None),
                               capture([row(0)], source_id=None))

    def test_descriptor_mismatch_is_rejected(self):
        candidate = row(1)
        candidate["variant"] = 2
        with self.assertRaisesRegex(ValueError, "Descriptor mismatch"):
            comparator.compare(capture([row(0)]), capture([candidate]))

    def test_only_matching_launch_and_successful_records_are_compared(self):
        reference_rows = [row(0), row(1), row(2)]
        candidate_rows = [
            row(0, launch=0x4282, pc=0x9999),
            row(1, status=1, pc=0x8888),
            row(2, pc=0x2000, marker=8, irq=0x6066,
                result=0x87654321, final_marker=10),
        ]
        report = comparator.compare(capture(reference_rows), capture(candidate_rows))
        group = report["groups"][0]
        self.assertEqual(group["records"], 3)
        self.assertEqual(group["matched_launch_status0"], 1)
        self.assertEqual(group["launch_beam_mismatches"], 1)
        self.assertEqual(group["unsuccessful"], 1)
        self.assertEqual(report["excluded"], {
            "launch_beam_mismatch": 1, "nonzero_status": 1})
        self.assertEqual(group["mismatches"], {
            "saved_pc_offset": 1, "aux": 1, "irq_beam": 1,
            "final_result": 1, "final_marker": 1})
        self.assertEqual(report["mismatch_records"], 1)
        self.assertEqual(report["matched_launch_status0"], 1)
        self.assertEqual(report["metric_summary"]["saved_pc_offset"],
                         {"records": 1, "mismatches": 1})
        self.assertEqual(group["delays"]["2"]["reference_pc_distribution"],
                         {"0x00001234": 1})
        self.assertEqual(group["delays"]["2"]["candidate_pc_distribution"],
                         {"0x00002000": 1})


if __name__ == "__main__":
    unittest.main()

import unittest

import compare_irq_focus as comparator


def capture(records, source_id="source", sha="capture"):
    return {"metadata": {"source_id": source_id, "sha256": sha}, "records": records}


def base_row(target, delay=0, launch=0x42C1, status=0):
    return {
        "kind": 43, "target": target, "variant": 0, "phase": 1,
        "delay": delay, "repeat": 0, "launch_beam": launch,
        "launch_ref": 0x4210, "end_beam": 0x42C1, "end_ref": 0x4220,
        "counter": 0x0010, "icr": 0, "irq_beam": 0x42D0, "irq_level": 3,
        "saved_pc_offset": 0x123456, "status": status, "aux": 1,
        "second_counter_or_beam": 0x4230, "second_icr_or_level": 0x4321,
    }


class IRQFocusCompareTests(unittest.TestCase):
    def test_source_descriptor_and_empty_kind43_validation(self):
        row = base_row(0)
        with self.assertRaisesRegex(ValueError, "Source ID mismatch"):
            comparator.compare(capture([row]), capture([row], source_id="other"))
        missing_source = capture([row], source_id="")
        with self.assertRaisesRegex(ValueError, "Missing or empty source ID"):
            comparator.compare(missing_source, missing_source)
        different = base_row(1)
        with self.assertRaisesRegex(ValueError, "Descriptor mismatch"):
            comparator.compare(capture([row]), capture([different]))
        other_kind = dict(row, kind=42)
        with self.assertRaisesRegex(ValueError, "No kind43"):
            comparator.compare(capture([other_kind]), capture([other_kind]))

    def test_masked_request_compares_bit_and_each_bracketing_beam(self):
        ref = base_row(0)
        cand = dict(ref, counter=0x1010)
        report = comparator.compare(capture([ref]), capture([cand]))
        self.assertEqual(report["mismatch_records"], 0)
        cand = dict(ref, counter=0x1000, launch_ref=0x4211,
                    second_counter_or_beam=0x4231)
        report = comparator.compare(capture([ref]), capture([cand]))
        self.assertEqual(report["groups"][0]["metrics"], {
            "masked_intreq_bit": {"records": 1, "mismatches": 1},
            "launch_ref": {"records": 1, "mismatches": 1},
            "second_counter_or_beam": {"records": 1, "mismatches": 1},
        })
        self.assertEqual(set(report["failures"][0]["differences"]),
                         {"masked_intreq_bit", "launch_ref", "second_counter_or_beam"})

    def test_cpu_targets_compare_exception_marker_and_optional_final_result(self):
        ref = base_row(2)
        cand = dict(ref, saved_pc_offset=0x123458, irq_beam=0x42D1,
                    aux=2, second_icr_or_level=0x4322, counter=0x20, icr=3)
        basic = comparator.compare(capture([ref]), capture([cand]))
        self.assertEqual(set(basic["metric_summary"]),
                         {"saved_pc_offset", "irq_beam", "aux", "final_marker"})
        self.assertEqual(basic["mismatch_records"], 1)
        full = comparator.compare(capture([ref]), capture([cand]), include_final_result=True)
        self.assertIn("final_result", full["metric_summary"])
        self.assertEqual(full["metric_summary"]["final_result"]["mismatches"], 1)

    def test_launch_mismatch_and_unsuccessful_rows_are_excluded(self):
        refs = [base_row(0, 0), base_row(1, 1)]
        candidates = [dict(refs[0], launch_beam=0x42C2), dict(refs[1], status=1)]
        report = comparator.compare(capture(refs), capture(candidates))
        self.assertEqual(report["matched_launch_status0"], 0)
        self.assertEqual(report["excluded"], {
            "launch_beam_mismatch": 1, "nonzero_status": 1})
        by_target = {group["target"]: group for group in report["groups"]}
        self.assertEqual(by_target[0]["launch_beam_mismatches"], 1)
        self.assertEqual(by_target[1]["unsuccessful"], 1)

    def test_metric_aggregation_is_per_target_and_reports_primary_failures(self):
        refs = [base_row(0, 0), base_row(1, 1), base_row(1, 2)]
        candidates = [dict(refs[0], counter=0), dict(refs[1], aux=3), refs[2]]
        report = comparator.compare(capture(refs), capture(candidates))
        groups = {group["target"]: group for group in report["groups"]}
        self.assertEqual(groups[0]["metrics"]["masked_intreq_bit"],
                         {"records": 1, "mismatches": 1})
        self.assertEqual(groups[1]["metrics"]["aux"],
                         {"records": 2, "mismatches": 1})
        self.assertEqual(report["metric_summary"]["aux"],
                         {"records": 2, "mismatches": 1})
        self.assertEqual(len(report["failures"]), 2)
        self.assertEqual(report["failures"][0]["target"], 0)


if __name__ == "__main__":
    unittest.main()

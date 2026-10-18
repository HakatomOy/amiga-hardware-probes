import copy
import unittest

import compare_copper_busy as comparator


def row():
    return dict(kind=50, target=0, variant=2, phase=0, delay=0, repeat=0,
                launch_beam=0x4240, launch_ref=0x4280, end_beam=0x4300,
                counter=0x02c0, icr=0x02c0, irq_beam=0x02c0, irq_level=0x02c0,
                saved_pc_offset=0x02c002c0, status=0x62c0, aux=0x42c0,
                second_counter_or_beam=0xffff, second_icr_or_level=0xffff)


class CopperBusyTests(unittest.TestCase):
    def test_status_slot_is_sample_and_shifted_sample_is_detected(self):
        reference = row()
        candidate = dict(reference, status=0x02c0)
        key = comparator.key(reference)
        report = comparator.compare({key: reference}, {key: candidate})
        self.assertEqual(report["counts"]["invalid"], 0)
        self.assertEqual(report["counts"]["mismatch"], 1)
        self.assertEqual(report["patterns"][0]["hardware_busy"], "00000011")
        self.assertEqual(report["patterns"][0]["candidate_busy"], "00000001")

    def test_brackets_are_never_silently_aligned(self):
        reference = row()
        key = comparator.key(reference)
        result = comparator.compare({key: reference}, {key: dict(reference, launch_ref=0x4281)})
        self.assertEqual(result["counts"]["different_brackets"], 1)
        self.assertEqual(result["counts"]["comparable"], 0)

    def test_missing_invalid_and_control_are_distinct(self):
        reference = row()
        key = comparator.key(reference)
        self.assertEqual(comparator.compare({key: reference}, {})["counts"]["missing"], 1)
        for change in ({"end_beam": 0xffff}, {"second_counter_or_beam": 0}):
            report = comparator.compare({key: reference}, {key: dict(reference, **change)})
            self.assertEqual(report["counts"]["invalid"], 1)
        control = dict(reference, variant=6, second_counter_or_beam=0xdead, second_icr_or_level=0xdead)
        key = comparator.key(control)
        self.assertEqual(comparator.compare({key: control}, {key: copy.deepcopy(control)})["counts"]["match"], 1)

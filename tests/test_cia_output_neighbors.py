import copy
import unittest
from tools.check_cia_output_neighbors import check_rows


class OutputGateTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(kind=53, target=0, variant=1, phase=1, delay=2, repeat=0,
                        launch_ref=65532, end_ref=65530, second_icr_or_level=65528,
                        icr=64, irq_level=64)

    def test_live_bit_is_reported_without_crediting_repairs(self):
        candidate = copy.deepcopy(self.row)
        candidate['irq_level'] = 0
        report = check_rows([self.row], [self.row], [candidate])
        self.assertEqual(report['unqualified_live_pb6_changes'], 1)
        self.assertEqual(report['qualified']['match'], 1)

    def test_settled_field_and_descriptor_changes_fail(self):
        for field in ('icr', 'delay', 'end_ref'):
            candidate = copy.deepcopy(self.row)
            candidate[field] += 1
            with self.assertRaises(ValueError):
                check_rows([self.row], [self.row], [candidate])

    def test_existing_settled_mismatch_is_not_accepted(self):
        reference = copy.deepcopy(self.row)
        reference['icr'] = 0
        with self.assertRaises(ValueError):
            check_rows([reference], [self.row], [self.row])

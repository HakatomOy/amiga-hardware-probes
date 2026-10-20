import unittest
from tools.check_native_blit_neighbors import check_changes


class NativeRequestGateTests(unittest.TestCase):
    def test_only_matching_hardware_field_repairs_are_accepted(self):
        old = dict(end_ref=0, reference_ticks=100, launch_beam=10, launch_ref=100,
                   end_beam=30, counter=0)
        hw = old | dict(end_ref=64, reference_ticks=36)
        new = hw.copy()
        self.assertEqual(check_changes({0: hw}, {0: old}, {0: new})['historical_native_field_repairs'], 1)
        for field in ('launch_beam', 'end_beam', 'counter'):
            with self.assertRaises(ValueError):
                check_changes({0: hw}, {0: old}, {0: new | {field: new[field]+1}})
        with self.assertRaises(ValueError):
            check_changes({0: hw | dict(end_ref=0)}, {0: old}, {0: new})

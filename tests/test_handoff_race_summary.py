import unittest
from tools.summarize_handoff_race import summarize


class RaceSummaryTests(unittest.TestCase):
    def test_old_new_order_is_independent_of_status_or_beam_difference(self):
        fields = [dict(name='first_D', field='irq_beam', unit='word'),
                  dict(name='beam', field='launch_ref', unit='packed beam')]
        row = dict(case=[77,3,2,0,0,0], status='mismatches',
                   expected=[0x5555,0x4280], actual=[0xaaaa,0x4280])
        result = summarize({'case':row}, fields)
        self.assertEqual(result['counts']['destination_differences'], 1)
        self.assertEqual(result['counts']['beam_differences'], 0)
        self.assertEqual(result['groups'][0]['hardware'], {'5555':1})
        row.update(expected=[0xaaaa,0x4282], actual=[0xaaaa,0x4280])
        result = summarize({'case':row}, fields)
        self.assertEqual(result['counts']['destination_differences'], 0)
        self.assertEqual(result['counts']['beam_differences'], 1)
        row['status'] = 'excluded'
        with self.assertRaises(ValueError):
            summarize({'case':row}, fields)

import unittest
from tools.summarize_handoff_request import summarize


class RequestSummaryTests(unittest.TestCase):
    def test_flags_and_beams_are_not_conflated(self):
        fields = [dict(name='post', field='launch_ref', unit='packed beam'),
                  dict(name='word', field='end_beam', unit='word')]
        row = dict(case=[76, 6, 4, 0, 0, 0], status='mismatches',
                   expected=[0x4300, 0], actual=[0x42e2, 0])
        report = summarize({'case': row}, fields)
        group = report['groups'][0]
        self.assertEqual((group['channel'], group['dma_planes']), ('A', 6))
        self.assertEqual((group['timing_differences'], group['data_differences']), (1, 0))
        self.assertEqual(group['beam_deltas'], [dict(hw_minus_model=[1], cases=1)])
        row.update(expected=[0x4300, 1], actual=[0x4300, 0])
        group = summarize({'case': row}, fields)['groups'][0]
        self.assertEqual((group['timing_differences'], group['data_differences']), (0, 1))
        row['status'] = 'excluded'
        with self.assertRaises(ValueError):
            summarize({'case': row}, fields)

    def test_near_line_length_delta_keeps_raw_witness_and_mismatch(self):
        fields = [dict(name='beam', field='icr', unit='packed beam')]
        row = dict(case=[76,6,4,0,0,0], status='mismatches',
                   expected=[0x4200], actual=[0x42df])
        report = summarize({'case': row}, fields)
        self.assertEqual(report['groups'][0]['timing_differences'], 1)
        witness = report['wrap_sensitive'][0]
        self.assertEqual((witness['hardware'], witness['candidate']), (0x4200,0x42df))
        self.assertEqual(witness['encoded_delta'], -223)
        row['actual'] = []
        with self.assertRaises(ValueError):
            summarize({'case': row}, fields)

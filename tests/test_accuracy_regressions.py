import unittest
from tools.make_accuracy_regressions import policy


class RegressionContractTests(unittest.TestCase):
    def test_probe_specific_measurements_keep_field_meanings(self):
        bus=policy(55)
        marker=next(f for f in bus['measurements'] if f['field']=='status')
        self.assertEqual(marker['mask'],0x14)
        self.assertEqual(len(bus['qualification']),2)
        handoff=policy(60)
        self.assertIn('remaining_polls',{f['name'] for f in handoff['measurements']})
        self.assertNotIn('remaining_polls',{f['name'] for f in policy(59)['measurements']})
        with self.assertRaises(ValueError):policy(999)


if __name__=='__main__':
    unittest.main()

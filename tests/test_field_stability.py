import unittest
from tools.field_stability import summarize

class FieldStabilityTests(unittest.TestCase):
    def test_conflicting_field_does_not_hide_other_observations_or_accept_case(self):
        row=dict(kind=100,target=1,variant=0,phase=0,delay=0,repeat=0,counter=4,icr=7)
        policy=dict(qualification=[],measurements=[dict(name='a',field='counter',unit='CCK'),dict(name='b',field='icr',unit='flags')])
        changed=dict(row,counter=6)
        report=summarize([[row,changed],[row,changed]],[row],policy)
        self.assertEqual(report['fields']['a']['counts'],{'unstable':1})
        self.assertEqual(report['fields']['b']['counts'],{'match':1})
        self.assertTrue(report['diagnostic_only'])
        self.assertFalse(report['acceptance_contract_changed'])
        report=summarize([[row],[row]],[changed],policy)
        self.assertEqual(report['fields']['a']['counts'],{'mismatch':1})
        self.assertEqual(report['fields']['a']['examples'][0]['hardware'],[4])
        self.assertEqual(summarize([[row]],[row],policy)['fields']['a']['counts'],{'insufficient_independent_repeats':1})

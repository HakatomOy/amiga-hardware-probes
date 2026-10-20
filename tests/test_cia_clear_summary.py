import unittest

from tools.summarize_cia_clear import summarize


FIELDS = [dict(name=n) for n in ('TA_before', 'CIA_snapshot', 'Paula_request',
                                'request1', 'request2', 'request3')]


def case(phase, state, requests=(0, 0, 0, 0), status='matches'):
    return dict(case=[85, 4, 0, phase, 0, 0], status=status,
                expected=[0, state, *requests])


class ClearSummaryTests(unittest.TestCase):
    def test_asserted_clear_and_pb_control_are_distinct_evidence(self):
        rows = dict(clear=case(8, 129), not_asserted=case(8, 1),
                    control=case(0, 255, (8, 8, 8, 8)))
        result = summarize(rows, FIELDS)
        self.assertTrue(result['discriminating'])
        self.assertEqual(result['counts']['asserted_then_ack_stays_clear'], 1)
        self.assertEqual(result['counts']['ICR_not_asserted'], 1)
        self.assertEqual(result['counts']['PB_control_request_observed'], 1)

    def test_unasserted_icr_and_unqualified_cases_do_not_prove_cancellation(self):
        rows = dict(clear=case(8, 1), excluded=case(8, 129, status='excluded'),
                    control=case(0, 255, (8, 8, 8, 8)))
        result = summarize(rows, FIELDS)
        self.assertFalse(result['discriminating'])
        self.assertEqual(result['counts'].get('ICR_asserted', 0), 0)
        self.assertEqual(result['counts']['unqualified'], 1)

    def test_reassertion_is_counted_and_other_probe_kinds_are_rejected(self):
        result = summarize(dict(clear=case(9, 129, (0, 8, 0, 0))), FIELDS)
        self.assertEqual(result['counts']['asserted_then_ack_reasserts'], 1)
        wrong = case(9, 129)
        wrong['case'][0] = 84
        with self.assertRaisesRegex(ValueError, 'kind85'):
            summarize(dict(wrong=wrong), FIELDS)

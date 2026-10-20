import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools import evidence as e


def group(delta=2, count=8):
    return dict(count=count, pattern=[['event', ['delta', delta], 'CCK']],
                representatives=['1', '2', '3', '4'], shared_conditions={'target': 0})


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run, self.cache = self.root/'run', self.root/'cache'
        self.spec = dict(id='test', comparison=dict(alignment='exact',
                         measurements=[dict(field='counter', unit='CCK')], qualification=[]))
        self.report = dict(counts={'total': 8, 'mismatches': 8}, groups=[group()],
                           reference_hashes=['hardware'], alignment='exact')
        self.save(self.run, self.report)

    def save(self, run, report, spec=None):
        e.write(run/'experiment.json', spec or self.spec)
        e.write(run/'summary.json', dict(status='review', identity={'rom': 'a'}))
        e.write(run/'comparison.json', report)
        e.write(run/'cases.json', {})

    def test_ids_survive_order_count_and_representative_changes(self):
        before = dict(groups=[group(), group(4)])
        after = dict(groups=[group(4), group(count=3)])
        result = e.family_delta(after, before, self.spec)
        self.assertEqual(len(result['changed']), 1)
        self.assertEqual((result['changed'][0]['before'], result['changed'][0]['after']), (8, 3))
        self.assertEqual(result['unchanged_cases'], 8)
        self.assertEqual(set(e.families(before, self.spec)), set(e.families(after, self.spec)))
        self.assertNotEqual(set(e.families(before, self.spec)), set(e.families(before, {'unit': 'ns'})))

    def test_packet_budget_and_cache_hit(self):
        report = dict(self.report, groups=[group(i) for i in range(30)])
        self.save(self.run, report)
        first = e.packet(self.run, self.cache, limit=2)
        self.assertFalse(first['cache']['reused'])
        self.assertEqual(first['changed_family_count'], 30)
        self.assertEqual(len(first['changed_families']), 2)
        self.assertEqual(len(first['changed_families'][0]['representatives']), 3)
        self.assertTrue(e.packet(self.run, self.cache, limit=2)['cache']['reused'])
        self.assertFalse(e.packet(self.run, self.cache, limit=3)['cache']['reused'])
        self.assertFalse(e.packet(self.run, self.cache, refresh=True)['cache']['reused'])

    def test_corrupt_cache_is_rebuilt_and_changed_inputs_invalidate(self):
        first = e.packet(self.run, self.cache)
        entry = Path(first['cache']['entry'])
        stored = e.read(entry)
        stored['packet']['counts']['total'] = 999
        e.write(entry, stored)
        self.assertEqual(e.packet(self.run, self.cache)['counts']['total'], 8)
        entry.write_text('partial JSON')
        self.assertFalse(e.packet(self.run, self.cache)['cache']['reused'])
        self.save(self.run, dict(self.report, counts={'total': 9}))
        changed = e.packet(self.run, self.cache)
        self.assertNotEqual(first['cache']['key'], changed['cache']['key'])

    def test_explicit_baseline_rejects_changed_contract_or_hardware(self):
        baseline = self.root/'before'
        self.save(baseline, dict(self.report, reference_hashes=['other']))
        with self.assertRaisesRegex(ValueError, 'reference hashes'):
            e.packet(self.run, self.cache, baseline)
        spec = copy.deepcopy(self.spec)
        spec['comparison']['measurements'][0]['unit'] = 'ns'
        self.save(baseline, self.report, spec)
        with self.assertRaisesRegex(ValueError, 'contract differs'):
            e.packet(self.run, self.cache, baseline)

    def test_baseline_unchanged_families_are_counts_only(self):
        baseline = self.root/'before'
        self.save(baseline, dict(self.report, groups=[group(), group(4)]))
        result = e.packet(self.run, self.cache, baseline)
        self.assertEqual(result['unchanged_families'], 1)
        self.assertEqual(result['unchanged_family_cases'], 8)
        self.assertEqual(result['changed_families'][0]['change'], 'resolved')
        self.assertEqual(result['changed_families'][0]['detail_run'], str(baseline.resolve()))

    def test_case_delta_detects_value_removal_and_shift_despite_equal_family_counts(self):
        baseline = self.root/'before'
        self.save(baseline, self.report)
        def case(actual):
            return dict(status='matches' if actual == [10] else 'mismatches',
                        qualification=[], expected=[10], actual=actual)
        e.write(baseline/'cases.json', {'value': case([10]), 'removed': case([10]),
                                       'event': case([10])})
        e.write(self.run/'cases.json', {'value': case([11]), 'event': case([12])})
        result = e.packet(self.run, self.cache, baseline)
        self.assertEqual(result['delta']['regressions'], 2)
        self.assertEqual(result['delta']['missing_results'], 1)
        self.assertEqual(result['unchanged_families'], 1)
        self.assertEqual(result['changed_case_examples']['regressions'], ['event', 'value'])
        self.assertNotIn('unchanged_matches', result['changed_case_examples'])
        # A case-file edit invalidates even when group counts remain identical.
        e.write(self.run/'cases.json', {})
        self.assertNotEqual(result['cache']['key'], e.packet(self.run, self.cache, baseline)['cache']['key'])


if __name__ == '__main__':
    unittest.main()

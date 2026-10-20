import unittest

import rom_results
from tools.qualification_audit import audit


def row(repeat=0, **values):
    return dict(dict.fromkeys(rom_results.FIELDS[:6], 0), repeat=repeat, **values)


class QualificationAuditTests(unittest.TestCase):
    def test_same_descriptor_pairs_are_not_shifted_or_pooled(self):
        fields = [dict(field='beam', name='bracket', unit='packed beam')]
        candidate = [row(0, beam=10), row(1, beam=11)]
        hardware = [row(0, beam=11), row(1, beam=10)]
        report = audit(candidate, [hardware], fields)
        self.assertEqual(report['fields'][0]['matched'], 0)
        self.assertEqual(report['fields'][0]['different'], 2)
        self.assertEqual(report['qualification_cohorts_per_condition'], [{2: 1}, {2: 1}])

    def test_missing_descriptor_and_masked_values(self):
        fields = [dict(field='beam', unit='bits', mask=1)]
        report = audit([row(0, beam=2), row(1, beam=3)], [[row(0, beam=0)]], fields)
        self.assertEqual(report['fields'][0]['matched'], 1)
        self.assertEqual(report['fields'][0]['missing'], 1)

    def test_duplicate_reference_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            audit([row(beam=1)], [[row(beam=1), row(beam=2)]], [])

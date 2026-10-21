from pathlib import Path
import tempfile
import unittest

from tools.screen_capture_variants import checked_names, scenario_spec


class CaptureVariantScreenTests(unittest.TestCase):
    def test_variant_never_weakens_or_mutates_hardware_contract(self):
        base = dict(capture=dict(expected_cases=384),
                    comparison=dict(alignment='exact', min_matches=384, max_excluded=0,
                                    required_field_repairs={'post_access': 20}),
                    references=['references/a/run1', 'references/a/run2'], baseline='captures/base')
        with tempfile.TemporaryDirectory() as folder:
            env = Path(folder) / 'environment.json'
            result = scenario_spec(base, env, Path(folder) / 'record.json')
        self.assertEqual(result['comparison'], base['comparison'])
        self.assertEqual(result['references'], base['references'])
        self.assertNotIn('environment_json', base['capture'])
        self.assertTrue(Path(result['capture']['environment_json']).is_absolute())

    def test_screen_rejects_path_components_and_unknown_baseline(self):
        valid = dict(variants={'0': {}}, scenarios={'fetch': 'test.json'},
                     baseline=dict(variant='0', scenario='fetch', packet='packet.bin'))
        checked_names(valid)
        for changed in (dict(valid, variants={'../escape': {}}),
                        dict(valid, baseline=dict(variant='other', scenario='fetch'))):
            with self.assertRaises(ValueError):
                checked_names(changed)


if __name__ == '__main__':
    unittest.main()

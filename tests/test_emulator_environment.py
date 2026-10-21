import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import run_rom
from tools import experiment


class EmulatorEnvironmentTests(unittest.TestCase):
    def test_only_explicit_emulator_string_settings_are_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'environment.json'
            good = {'COPPERLINE_EXPERIMENT_CPU_FREE': '2'}
            path.write_text(json.dumps(good))
            self.assertEqual(run_rom.load_emulator_environment(path), good)
            for invalid in ({'PATH': 'other'}, {'COPPERLINE_X': 1}, []):
                path.write_text(json.dumps(invalid))
                with self.assertRaisesRegex(ValueError, 'COPPERLINE_'):
                    run_rom.load_emulator_environment(path)

    def test_environment_content_changes_the_replay_identity(self):
        def identity(settings):
            payload = json.dumps(settings, sort_keys=True).encode()
            return dict(binary_sha256='binary', config_sha256='config', rom_sha256='rom',
                        environment_sha256=hashlib.sha256(payload).hexdigest())
        before = experiment.replay_fingerprint(identity({'COPPERLINE_X': '0'}), 60, [])
        after = experiment.replay_fingerprint(identity({'COPPERLINE_X': '1'}), 60, [])
        self.assertNotEqual(before, after)


if __name__ == '__main__':
    unittest.main()

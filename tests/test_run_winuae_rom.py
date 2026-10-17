import hashlib
import tempfile
import unittest
from pathlib import Path

import run_winuae_rom


class WinUAESettingsTests(unittest.TestCase):
    def test_existing_settings_are_copied_with_source_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'accepted.ini'
            source_bytes = b'[WinUAE]\nBetaToken=134356116308172329\nOtherSetting=yes\n'
            source.write_bytes(source_bytes)
            out = root / 'run'
            out.mkdir()

            provenance = run_winuae_rom._prepare_winuae_settings(out, source)

            self.assertEqual((out / 'winuae.ini').read_bytes(), source_bytes)
            self.assertEqual(provenance['settings_source_path'], str(source.resolve()))
            self.assertEqual(provenance['settings_source_sha256'], hashlib.sha256(source_bytes).hexdigest())
            self.assertEqual(provenance['settings_source_kind'], 'copied-existing-settings')

    def test_calls_without_settings_keep_the_fresh_debugger_ini(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / 'run'
            out.mkdir()

            provenance = run_winuae_rom._prepare_winuae_settings(out)

            ini_bytes = (out / 'winuae.ini').read_bytes()
            self.assertEqual((out / 'winuae.ini').read_text(), '[WinUAE]\nDebuggerType=1\n')
            self.assertIsNone(provenance['settings_source_path'])
            self.assertEqual(provenance['settings_source_sha256'], hashlib.sha256(ini_bytes).hexdigest())
            self.assertEqual(provenance['settings_source_kind'], 'generated-default')


if __name__ == '__main__':
    unittest.main()

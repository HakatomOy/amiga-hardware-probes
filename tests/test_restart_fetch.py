from pathlib import Path
import shutil
import tempfile
import unittest

import build_copper_restart_fetch_rom as probe


class RestartFetchTests(unittest.TestCase):
    def test_venues_share_identical_banks_and_repeat_pairs(self):
        rows = probe.trials()
        self.assertEqual(len(rows), 384)
        self.assertEqual(len(set(rows)), 384)
        for row in rows:
            self.assertIn(row[:-1] + (1 - row[-1],), rows)
            self.assertIn(row[:2] + (row[2] ^ 4096,) + row[3:], rows)
            self.assertEqual((row[2] >> 5) & 97,
                             ((row[2] >> 5) & 1) + (((row[2] >> 10) & 1) * 32))

    def test_common_input_precedes_unknown_venue_and_copy_precedes_alignment(self):
        root = Path(probe.__file__).parent
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            (stage / 'src/rom').mkdir(parents=True)
            for name in ('experiment.asm', 'blitter_handoff_kernel.i', 'blitter_handoff_observer.i'):
                shutil.copyfile(root / 'src/rom' / name, stage / 'src/rom' / name)
            probe.transform(stage)
            kernel = (stage / 'src/rom/blitter_handoff_kernel.i').read_text()
            observer = (stage / 'src/rom/blitter_handoff_observer.i').read_text()
            self.assertLess(kernel.index('.copy_restart_banks:'), kernel.index('jsr sync_beam'))
            self.assertIn('jsr $ffbf80', kernel)
            self.assertIn('suba.l #$fcb000,a3', kernel)
            self.assertEqual(observer.count('move.w 6(a6),d2'), 1)
            self.assertIn('move.w 6(a6),d2\n        jmp (a3)', observer)


if __name__ == '__main__':
    unittest.main()

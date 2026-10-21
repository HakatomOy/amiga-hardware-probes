from pathlib import Path
import shutil
import tempfile
import unittest

import build_copper_restart_access_rom as probe


class RestartAccessTests(unittest.TestCase):
    def test_full_matrix_repeats_and_sparse_bank_selection(self):
        rows = probe.trials()
        self.assertEqual(len(rows), 768)
        self.assertEqual(len(set(rows)), len(rows))
        for item in rows:
            self.assertIn(item[:-1] + (1 - item[-1],), rows)
            variant = item[2]
            self.assertEqual((variant >> 5) & 97,
                             ((variant >> 5) & 1) + (((variant >> 10) & 1) * 32) + ((variant >> 11) * 64))
            self.assertTrue(variant & 8)

    def test_critical_access_has_no_intervening_observer_or_blit_start(self):
        root = Path(probe.__file__).parent
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            (stage / 'src/rom').mkdir(parents=True)
            for name in ('experiment.asm', 'blitter_handoff_kernel.i', 'blitter_handoff_observer.i'):
                shutil.copyfile(root / 'src/rom' / name, stage / 'src/rom' / name)
            probe.transform(stage)
            text = (stage / 'src/rom/blitter_handoff_observer.i').read_text()
            self.assertNotIn('move.w d5,(a2)', text)
            self.assertEqual(text.count('move.w (a1),d0'), 4)
            self.assertEqual(text.count('move.w d0,(a1)'), 4)
            self.assertEqual(text.count('move.w #0,$88(a0)\n        move.w #$8080,$96(a0)\n        move.w'), 4)
            self.assertEqual(text.count('move.w #$8080,$96(a0)\n        move.w #0,$88(a0)\n        move.w'), 4)
            self.assertEqual(text.count('dbra d1,.settle_'), 8)
            for block in text.split('restart_access_')[1:]:
                self.assertLess(block.index('move.w 6(a6),d2'), block.index('movea.l '))
            kernel = (stage / 'src/rom/blitter_handoff_kernel.i').read_text()
            self.assertLess(kernel.index('move.l #$dff006,d4'), kernel.index('jsr sync_beam'))


if __name__ == '__main__':
    unittest.main()

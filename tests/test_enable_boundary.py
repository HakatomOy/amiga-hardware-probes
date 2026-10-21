from pathlib import Path
import shutil
import tempfile
import unittest

import build_copper_enable_boundary_rom as probe


class EnableBoundaryTests(unittest.TestCase):
    def test_matrix_pairs_venues_initial_states_and_repeats(self):
        rows = probe.trials()
        self.assertEqual(len(set(rows)), 192)
        for row in rows:
            self.assertIn(row[:-1] + (row[-1] ^ 1,), rows)
            for bit in (4096, 8192):
                self.assertIn(row[:2] + (row[2] ^ bit,) + row[3:], rows)

    def test_measured_restart_removed_and_initial_state_prepared_before_alignment(self):
        root = Path(probe.__file__).parent
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            (stage / 'src/rom').mkdir(parents=True)
            for name in ('experiment.asm', 'blitter_handoff_kernel.i', 'blitter_handoff_observer.i'):
                shutil.copyfile(root / 'src/rom' / name, stage / 'src/rom' / name)
            probe.transform(stage)
            kernel = (stage / 'src/rom/blitter_handoff_kernel.i').read_text()
            observer = (stage / 'src/rom/blitter_handoff_observer.i').read_text()
            self.assertLess(kernel.index('.enable_seed_ready:'), kernel.index('jsr sync_beam'))
            self.assertNotIn('$88(a0)', observer)
            self.assertEqual(observer.count('move.w #0,$1fe(a6)'), 8)
            self.assertEqual(observer.count('move.w d6,22(a4)'), 8)
            self.assertIn('move.w 6(a6),d2\n        jmp (a3)', observer)


if __name__ == '__main__':
    unittest.main()

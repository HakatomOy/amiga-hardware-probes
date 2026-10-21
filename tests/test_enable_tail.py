from pathlib import Path
import shutil
import tempfile
import unittest

import build_copper_enable_boundary_rom as boundary
import build_copper_enable_tail_rom as probe


class EnableTailTests(unittest.TestCase):
    def test_matrix_pairs_tails_venues_and_repeats(self):
        rows = probe.trials()
        self.assertEqual(len(set(rows)), 192)
        for row in rows:
            self.assertIn(row[:-1] + (row[-1] ^ 1,), rows)
            for bit in (4096, 8192):
                self.assertIn(row[:2] + (row[2] ^ bit,) + row[3:], rows)

    def test_first_move_and_cpu_observers_do_not_depend_on_tail(self):
        root = Path(probe.__file__).parent
        with tempfile.TemporaryDirectory() as folder:
            observers = []
            for name, transform in (('boundary', boundary.transform), ('tail', probe.transform)):
                stage = Path(folder) / name
                (stage / 'src/rom').mkdir(parents=True)
                for source in ('experiment.asm', 'blitter_handoff_kernel.i', 'blitter_handoff_observer.i'):
                    shutil.copyfile(root / 'src/rom' / source, stage / 'src/rom' / source)
                transform(stage)
                observers.append((stage / 'src/rom/blitter_handoff_observer.i').read_text())
            self.assertEqual(*observers)
            kernel = (stage / 'src/rom/blitter_handoff_kernel.i').read_text()
            self.assertIn('move.w #$009c,$6000\n        move.w #$8010,$6002', kernel)
            self.assertEqual(kernel.count('move.w #0,$88(a6)      ; COPEN is disabled'), 1)
            self.assertIn('move.w #$ffff,$6010', kernel)
            self.assertLess(kernel.index('.enable_tail_ready:'), kernel.index('jsr sync_beam'))


if __name__ == '__main__':
    unittest.main()

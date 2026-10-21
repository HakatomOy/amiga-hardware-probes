from pathlib import Path
import shutil
import tempfile
import unittest

import build_copper_marker_copy_rom as probe


class MarkerCopyTests(unittest.TestCase):
    def test_small_matrix_keeps_both_forms_and_independent_repeats(self):
        rows = probe.trials()
        self.assertEqual(len(rows), 96)
        self.assertEqual(len(set(rows)), 96)
        for row in rows:
            self.assertIn(row[:-1] + (1 - row[-1],), rows)
            self.assertEqual(row[2] & 32, 0)
            self.assertTrue(row[2] & 1024)

    def test_marker_values_are_preserved_separately(self):
        root = Path(probe.__file__).parent
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            (stage / 'src/rom').mkdir(parents=True)
            for name in ('experiment.asm', 'blitter_handoff_kernel.i', 'blitter_handoff_observer.i'):
                shutil.copyfile(root / 'src/rom' / name, stage / 'src/rom' / name)
            probe.transform(stage)
            text = (stage / 'src/rom/blitter_handoff_observer.i').read_text()
            self.assertEqual(text.count('move.w 6(a6),18(a4)\n        move.w 6(a6),d3'), 4)
            self.assertEqual(text.count('move.w 6(a6),d6\n        nop\n        nop\n        move.w 6(a6),d3'), 4)
            self.assertEqual(text.count('move.w d3,22(a4)'), 8)
            self.assertEqual(text.count('move.w d6,18(a4)'), 4)


if __name__ == '__main__':
    unittest.main()

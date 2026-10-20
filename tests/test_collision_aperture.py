from pathlib import Path
import shutil
import tempfile
import unittest

import build_collision_aperture_rom as probe


class CollisionApertureTests(unittest.TestCase):
    def test_matrix_covers_pointer_halves_controls_and_five_phase_repeats(self):
        rows = probe.trials()
        self.assertEqual(len(rows), 1440)
        self.assertEqual(len(set(rows)), len(rows))
        self.assertEqual({r[1] for r in rows}, {1, 2, 3})
        self.assertEqual({r[2] for r in rows}, {4, 5, 6, 7})
        self.assertEqual({r[4] for r in rows}, {0, 1, 2, 3})
        self.assertEqual({r[5] for r in rows}, set(range(5)))

    def test_read_pairs_precede_stores_and_retain_settled_controls(self):
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            shutil.copytree(probe.base.ROOT / 'src', stage / 'src')
            probe.transform(stage)
            kernel = (stage / 'src/rom/blitter_handoff_kernel.i').read_text()
            self.assertIn('cmpi.w #$4310,d0', kernel)
            self.assertIn('jsr (a3)', kernel)
            self.assertIn('blitter_handoff_trial:\n        move.l a3,-(sp)', kernel)
            self.assertIn('movea.l (sp)+,a3\n        rts', kernel)
            self.assertIn('.settled_line:', kernel)
            edge = (stage / 'src/rom/edge_kernel.asm').read_text()
            tail = edge[edge.index('        dcb.b $ffea00-*,0'):]
            pair = 'move.w $0e(a6),d0\n        move.w $0e(a6),d1'
            self.assertEqual(tail.count(pair), 4)
            self.assertEqual(tail.count('move.w d2,38(a4)'), 4)
            self.assertEqual(tail.count('exg d2,d2'), 2)
            self.assertEqual(tail.count('        nop\n'), 4)

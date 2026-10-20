import tempfile
from pathlib import Path
import shutil
import unittest

import build_handoff_copper_race_rom as probe
import build_handoff_copper_access_rom as access
from tools.verify_copper_overlap import analyze


class CopperRaceTests(unittest.TestCase):
    def test_access_controls_use_identical_opcode_and_enabled_copper(self):
        rows = access.trials()
        self.assertEqual(len(rows), 1024)
        self.assertEqual(len(set(rows)), 1024)
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            shutil.copytree(access.base.ROOT/'src', stage/'src')
            access.transform(stage)
            text = (stage/'src/rom/blitter_handoff_observer.i').read_text()
            self.assertEqual(text.count('move.w (a1),d0'), 8)
            self.assertEqual(text.count('move.w #$8080,$96(a6)'), 8)

    def test_activity_after_completion_is_not_overlap(self):
        import rom_results
        row = dict(zip(rom_results.FIELDS[:6], (78,3,6,0,0,0)))
        lines = ['BLTP 0 66 100 START size=0041',
                 'BLTP 0 66 101 OWNER Copper',
                 'COPPROBE MOVE v=042 h=65 reg=1fe val=0000',
                 'BLTP 0 66 110 END source=bus_slot']
        self.assertEqual(analyze(lines, [row])['counts']['with_overlap_moves'], 1)
        with self.assertRaisesRegex(ValueError, 'no verified Copper overlap'):
            analyze([lines[0], lines[1], lines[3], lines[2]], [row])
        with self.assertRaisesRegex(ValueError, 'incomplete trace'):
            analyze(lines[:-1], [row])

    def test_matrix_and_finite_activity_witness(self):
        rows = probe.trials()
        self.assertEqual(len(rows), 1536)
        self.assertEqual(len(set(rows)), len(rows))
        self.assertEqual({(r[2] >> 1) & 3 for r in rows}, {2, 3})
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            shutil.copytree(probe.base.ROOT/'src', stage/'src')
            probe.transform(stage)
            observer = (stage/'src/rom/blitter_handoff_observer.i').read_text()
            self.assertEqual(observer.count('move.w #$8080,$96(a6)'), 8)
            self.assertEqual(observer.count('move.w #0,$88(a6)'), 8)
            self.assertEqual(observer.count('move.w d0,(a1)'), 8)
            kernel = (stage/'src/rom/blitter_handoff_kernel.i').read_text()
            self.assertIn('move.w #$8010,(a1)+', kernel)
            self.assertIn('rept 32', kernel)


if __name__ == '__main__':
    unittest.main()

from pathlib import Path
import tempfile
import unittest

import build_controlled_collision_rom as probe


class ControlledCollisionTests(unittest.TestCase):
    def test_rom_ram_pairs_preserve_descriptors_and_controls(self):
        for pointer, expected in ((True, 960), (False, 1600)):
            rows = probe.trials(pointer)
            self.assertEqual(len(rows), expected)
            self.assertEqual(len(set(rows)), expected)
            half = expected // 2
            self.assertEqual(rows[:half], [(k,t,v & ~8,p,d,r) for k,t,v,p,d,r in rows[half:]])

    def test_common_input_precedes_enable_and_preserves_trial_table_pointer(self):
        for pointer in (True, False):
            with tempfile.TemporaryDirectory() as folder:
                stage = Path(folder)
                source = stage/'src/rom'
                source.mkdir(parents=True)
                (source/'experiment.asm').write_text((probe.base.ROOT/'src/rom/experiment.asm').read_text())
                probe.transform(stage, pointer)
                kernel = (source/'blitter_handoff_kernel.i').read_text()
                observer = (source/'blitter_handoff_observer.i').read_text()
            self.assertNotIn('a3', kernel.lower())
            self.assertNotIn('a3', observer.lower())
            self.assertNotIn('move.w d6,$96(a6)', kernel)
            self.assertEqual(observer.count('move.w d6,$96(a6)'), 1)
            self.assertIn('move.w 6(a6),d3\n        jmp (a0)', observer)
            self.assertLess(kernel.index('jsr $ffbf80'), kernel.index('move.w d3,38(a4)'))
            self.assertIn('#$4411', kernel)
            self.assertIn('#$4520', observer)


if __name__ == '__main__':
    unittest.main()

from pathlib import Path
import tempfile
import unittest
import build_handoff_race_rom as probe


class HandoffRaceTests(unittest.TestCase):
    def test_race_has_matching_neighbor_and_no_start_controls(self):
        rows = set(probe.trials())
        self.assertEqual(len(rows), 2304)
        for k,t,v,p,d,r in rows:
            self.assertIn((k,t,v ^ 16,p,d,r), rows)
            self.assertIn((k,t,v ^ 8,p,d,r), rows)
            self.assertEqual(t % 3, 0)

    def test_overwrite_is_preloaded_and_preseed_does_not_enter_timed_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            rom = stage / 'src/rom'
            rom.mkdir(parents=True)
            original = Path(probe.__file__).parent / 'src/rom'
            for name in ('experiment.asm','blitter_handoff_kernel.i','blitter_handoff_observer.i'):
                (rom / name).write_bytes((original / name).read_bytes())
            probe.transform(stage)
            kernel = (rom / 'blitter_handoff_kernel.i').read_text()
            self.assertLess(kernel.index('move.w #$5555,$12000'), kernel.index('jsr sync_beam'))
            self.assertIn('move.l #$12002,d4', kernel)
            observer = (rom / 'blitter_handoff_observer.i').read_text()
            self.assertEqual(observer.count('move.w #$5555,d0\n        move.w 6(a6),12(a4)'), 8)
            self.assertEqual(observer.count('move.w d0,(a1)'), 8)
            self.assertEqual(observer.count('move.w (a1),34(a4)'), 8)

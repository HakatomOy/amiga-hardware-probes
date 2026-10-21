from pathlib import Path
import shutil
import tempfile
import unittest

import build_init_resource_race_rom as probe
from tools.summarize_init_resource import summarize


def row(mode, source=0xaaaa, launch=0x42c0):
    return dict(kind=90, target=3, variant=6 | (mode << 8), phase=0, delay=4,
                repeat=0, status=0, launch_beam=launch, irq_level=source,
                end_ref=0, counter=0x4307, icr=0, irq_beam=0x4313)


class InitResourceTests(unittest.TestCase):
    def test_launch_sweep_retains_controls_and_all_launches(self):
        rows = probe.trials(launch_sweep=True)
        self.assertEqual(len(rows), 606)
        self.assertEqual(len(set(rows)), len(rows))
        races = [r for r in rows if r[1] == 3 and not r[2] & 16]
        self.assertEqual({(r[3], r[4]) for r in races},
                         {(phase, pad) for phase in range(2) for pad in range(8)})
        for item in rows:
            self.assertIn(item[:-1] + (1 - item[-1],), rows)
        for mode in range(3):
            for inert in (0, 8):
                self.assertEqual(sum(r[2] >> 8 == mode and r[2] & 8 == inert
                                     for r in races), 96)
            self.assertEqual(sum(r[1] == 3 and r[2] & 16 and r[2] >> 8 == mode
                                 for r in rows), 2)

    def test_controls_repeat_pairs_and_modes(self):
        rows = probe.trials()
        self.assertEqual(len(rows), 600)
        self.assertEqual(len(set(rows)), 600)
        for item in rows:
            self.assertIn(item[:-1] + (1 - item[-1],), rows)
        self.assertEqual([sum(r[2] >> 8 == mode for r in rows) for mode in range(3)], [200] * 3)

    def test_transform_selects_observer_before_alignment_and_bounds_wait(self):
        root = Path(probe.__file__).parent
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            (stage / 'src/rom').mkdir(parents=True)
            for name in ('experiment.asm', 'blitter_handoff_kernel.i', 'blitter_handoff_observer.i'):
                shutil.copyfile(root / 'src/rom' / name, stage / 'src/rom' / name)
            probe.transform(stage)
            kernel = (stage / 'src/rom/blitter_handoff_kernel.i').read_text()
            observer = (stage / 'src/rom/blitter_handoff_observer.i').read_text()
            self.assertIn('lsr.w #5,d0\n        andi.w #3,d0', kernel)
            self.assertLess(kernel.index('movea.l 0(a1,d0.w),a3'), kernel.index('jsr sync_beam'))
            self.assertIn('dbra d1,.wait_entry', kernel)
            self.assertEqual(observer.count('move.w d0,(a1)'), 4)
            self.assertEqual(observer.count('move.w $02(a6),d1'), 4)
            self.assertNotIn('dbra', observer)

    def test_summary_never_aligns_different_launches(self):
        result = summarize([row(0), row(1), row(2, source=0x5555)])
        self.assertEqual(result['counts']['source_changes'], 1)
        result = summarize([row(0), row(1), row(2, launch=0x42c2)])
        self.assertEqual(result['counts']['unmatched_launch_cohorts'], 1)
        self.assertEqual(result['counts']['race_cohorts'], 0)

    def test_summary_rejects_missing_and_duplicate_modes(self):
        for rows in ([row(0), row(1)], [row(0), row(0), row(1), row(2)]):
            with self.assertRaises(ValueError):
                summarize(rows)


if __name__ == '__main__':
    unittest.main()

import tempfile
import unittest
from pathlib import Path
import shutil

import build_handoff_busy_onset_rom as onset
import build_handoff_focus_rom as focus
from tools.summarize_busy_onset import summarize


class BusyOnsetTests(unittest.TestCase):
    def test_summary_distinguishes_rising_busy_from_clear_only(self):
        def row(variant, states, repeat):
            return dict(zip(('kind', 'target', 'variant', 'phase', 'delay', 'repeat'),
                            (89, 5, variant, 0, 4, repeat)), status=0,
                        launch_ref=states[0], end_ref=states[1], irq_beam=states[2],
                        icr=0, irq_level=0 if variant & 8 else 0xaaaa)
        result = summarize([row(6, (0, 0x4000, 0), 0), row(6, (0, 0, 0), 1),
                            row(14, (0, 0, 0), 0)])
        self.assertEqual(result['counts']['real_clear_to_busy'], 1)
        self.assertEqual(result['counts']['real16_clear_to_busy'], 1)
        self.assertEqual(result['counts']['real_first_clear_last_D_still_zero'], 2)
        self.assertEqual(result['counts']['inert'], 1)

    def test_controls_and_repeat_pairs(self):
        rows = onset.trials()
        self.assertEqual(len(rows), 384)
        self.assertEqual(len(set(rows)), 384)
        self.assertEqual({r[1] for r in rows}, {3, 5})
        self.assertEqual({r[2] & 24 for r in rows}, {0, 8, 16, 24})
        for row in rows:
            self.assertIn(row[:-1] + (1 - row[-1],), rows)

    def test_launch_prefix_and_first_status_opcode_are_unchanged(self):
        root = Path(onset.__file__).parent
        with tempfile.TemporaryDirectory() as directory:
            before, after = Path(directory) / 'before', Path(directory) / 'after'
            for stage in (before, after):
                (stage / 'src/rom').mkdir(parents=True)
                for name in ('experiment.asm', 'blitter_handoff_kernel.i',
                             'blitter_handoff_observer.i'):
                    shutil.copyfile(root / 'src/rom' / name, stage / 'src/rom' / name)
            focus.transform(before, read_control=True)
            onset.transform(after)
            old = (before / 'src/rom/blitter_handoff_observer.i').read_text()
            new = (after / 'src/rom/blitter_handoff_observer.i').read_text()
            self.assertEqual(old.split('.wait_busy:')[0], new.split('        move.w $02(a6),d0')[0])
            self.assertNotIn('dbra', new.lower())
            self.assertNotIn('move.w #0,$40(a6)', new)
            self.assertIn('move.w (a0),26(a4)', new)
            kernel = (after / 'src/rom/blitter_handoff_kernel.i').read_text()
            self.assertIn('#$009c,$607c', kernel)
            self.assertIn('#$8010,$607e', kernel)


if __name__ == '__main__':
    unittest.main()

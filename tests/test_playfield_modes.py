from pathlib import Path
import tempfile
import unittest
import build_playfield_modes_rom as probe


class PlayfieldModeProbeTests(unittest.TestCase):
    def test_every_case_has_identical_single_dual_partner(self):
        rows=probe.trials()
        self.assertEqual(len(rows),512)
        self.assertEqual(len(set(rows)),512)
        cases=set(rows)
        for k,t,v,p,d,r in rows:
            self.assertIn((k,t,v^1,p,d,r),cases)
        self.assertEqual({t for _,t,_,_,_,_ in rows},set(range(16)))
        self.assertEqual({p for _,_,_,p,_,_ in rows},set(range(4)))

    def test_mode_selection_is_before_common_observer_with_no_critical_branch(self):
        self.assertIn('move.w #$2200,d4',probe.KERNEL)
        self.assertIn('move.w d4,$100(a6)',probe.KERNEL)
        self.assertNotRegex(probe.OBSERVER,r'(?<!\d)4\(a4\)')
        self.assertNotIn('a3',probe.KERNEL.lower())
        self.assertNotIn('d7',probe.KERNEL.lower())
        self.assertIn('move.w #$8300,$96(a6)',probe.OBSERVER)
        self.assertIn('cmpi.w #$4420,d0',probe.OBSERVER)
        self.assertIn('cmpi.w #$44d0,d0',probe.OBSERVER)
        with tempfile.TemporaryDirectory() as temporary:
            stage=Path(temporary);source=stage/'src/rom';source.mkdir(parents=True)
            (source/'experiment.asm').write_text((probe.base.ROOT/'src/rom/experiment.asm').read_text())
            probe.transform(stage)
            self.assertIn('cmpi.w #101,(a4)',(source/'experiment.asm').read_text())

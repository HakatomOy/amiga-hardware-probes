from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build_handoff_stride_rom as probe


class HandoffStrideTests(unittest.TestCase):
    def test_cadence_is_independent_of_launch_phase_and_outer_stream_survives(self):
        rows=probe.trials()
        self.assertEqual(len(rows),1280)
        self.assertEqual(len(set(rows)),1280)
        self.assertEqual({r[2]>>5 for r in rows},{0,1,2,3})
        self.assertEqual({r[3] for r in rows},{0,1})
        with tempfile.TemporaryDirectory() as directory:
            stage=Path(directory);rom=stage/'src/rom';rom.mkdir(parents=True)
            (rom/'experiment.asm').write_text('cmpi.w #60,(a4)')
            (rom/'blitter_handoff_kernel.i').write_text('        ; Align in ROM, then apply phase and the 0..7 NOP launch padding.\n        jsr $ffb000')
            (rom/'blitter_handoff_observer.i').write_text('blitter_handoff_observer:\n.wait_busy:\n        move.w $02(a6),d0\n        rts')
            with patch.object(probe.focus,'transform'):probe.transform(stage)
            kernel=(rom/'blitter_handoff_kernel.i').read_text()
            self.assertLess(kernel.index('move.l a3,-(sp)'),kernel.index('; Align in ROM'))
            self.assertIn('movea.l (sp)+,a3',kernel)
            observer=(rom/'blitter_handoff_observer.i').read_text()
            self.assertEqual(observer.count('blitter_stride_'),4)
            self.assertIn('.wait_busy:\n        nop\n        nop\n        nop\n',observer)


if __name__=='__main__':unittest.main()

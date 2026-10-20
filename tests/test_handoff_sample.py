from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build_handoff_sample_rom as probe


class SingleSampleTests(unittest.TestCase):
    def test_fixed_samples_do_not_branch_on_status_and_fit_observer_region(self):
        rows = probe.trials()
        self.assertEqual(len(rows), 1024)
        self.assertEqual(len(set(rows)), 1024)
        self.assertEqual({r[2] >> 5 for r in rows}, set(range(8)))
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            rom = stage/'src/rom'
            rom.mkdir(parents=True)
            (rom/'experiment.asm').write_text('cmpi.w #67,(a4)')
            (rom/'blitter_handoff_kernel.i').write_text('.observers: dc.l $ffb000,$ffb400,$ffb800,$ffbc00')
            with patch.object(probe.stride, 'transform'):
                probe.transform(stage)
            text = (rom/'blitter_handoff_observer.i').read_text()
            self.assertEqual(text.count('move.w $02(a6),d0'), 8)
            self.assertNotIn('btst', text)
            self.assertNotIn('dbra', text)
            self.assertNotIn('$40(a6)', text)
            self.assertIn('dcb.b $ffbe00-*,0', text)
            self.assertNotIn('dcb.b $ffc000', text)
            self.assertIn('$ffbe00', (rom/'blitter_handoff_kernel.i').read_text())

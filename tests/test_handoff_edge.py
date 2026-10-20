from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build_handoff_edge_rom as probe


class HandoffEdgeTests(unittest.TestCase):
    def test_width_controls_and_status_precedes_beam(self):
        rows = probe.trials()
        self.assertEqual(len(rows), 1536)
        self.assertEqual(len(set(rows)), 1536)
        self.assertEqual({r[1] for r in rows}, {3, 4, 5})
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            rom = stage/'src/rom'
            rom.mkdir(parents=True)
            (rom/'experiment.asm').write_text('cmpi.w #70,(a4)')
            old = '''        move.w 6(a6),d3
        move.w $02(a6),d0
        move.w 6(a6),d4
        move.w $1e(a6),d1
        move.w 6(a6),d2
        move.w d4,18(a4)
        move.w d1,20(a4)
        move.w d2,22(a4)
        clr.w 34(a4)
'''
            (rom/'blitter_handoff_observer.i').write_text(old * 8)
            with patch.object(probe.sample, 'transform'):
                probe.transform(stage)
            text = (rom/'blitter_handoff_observer.i').read_text()
            self.assertTrue(text.startswith('        move.w $02(a6),d0\n'))
            self.assertEqual(text.count('move.w d4,34(a4)'), 8)
            self.assertNotIn('dbra', text)

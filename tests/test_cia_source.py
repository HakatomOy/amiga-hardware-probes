from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build_cia_source_rom as probe


class SourceTests(unittest.TestCase):
    def test_discriminating_controls_and_counter_pin_request_order(self):
        rows=probe.trials()
        self.assertEqual(len(rows),640)
        self.assertEqual(len(set(rows)),640)
        self.assertEqual({r[3] for r in rows},{0,2,4,6})
        with tempfile.TemporaryDirectory() as directory:
            stage=Path(directory);rom=stage/'src/rom';rom.mkdir(parents=True)
            (rom/'experiment.asm').write_text('cmpi.w #57,(a4)')
            (rom/'edge_kernel.asm').write_text('header\n        dcb.b $ffda00-*,0\nold')
            with patch.object(probe.phase,'transform'):
                probe.transform(stage)
            s=(rom/'edge_kernel.asm').read_text()
            self.assertLess(s.index('move.b $bfe401,d0'),s.index('move.b $bfe101,d1'))
            self.assertLess(s.index('move.b $bfe101,d1'),s.index('move.w $1e(a6),d5'))
            self.assertLess(s.index('move.w $1e(a6),d5'),s.index('move.b $bfe401,d7'))
            self.assertIn('ori.w #6,d7',s)
            self.assertIn('move.b $bfd400,d0',s)
        with patch.object(probe.base,'build',side_effect=lambda *a,**k:k):
            arguments=probe.build(None,False,None)
        self.assertIsNone(arguments['profile']['masked_fields'])


if __name__=='__main__':
    unittest.main()

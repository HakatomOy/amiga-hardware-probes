import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import build_cia_request_rom as probe


class RequestProbeTests(unittest.TestCase):
    def test_four_samples_keep_timer_launch_and_calibration(self):
        rows = probe.trials()
        self.assertEqual(len(rows), 640)
        self.assertEqual(len(set(rows)), 640)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src/rom').mkdir(parents=True)
            (root / 'src/rom/experiment.asm').write_text('cmpi.w #66,(a4)')
            blocks = []
            for cia in (0xbfe001, 0xbfd000):
                blocks.append(f'''        move.w $1e(a6),d5
        moveq #0,d7
        move.b ${cia+0x400:06x},d7
        move.w 6(a6),d6
        moveq #0,d4
        move.b ${cia+0xd00:06x},d4
        move.w d7,28(a4)
        move.w d4,30(a4)''')
            edge = root / 'src/rom/edge_kernel.asm'
            edge.write_text('\n'.join(blocks))
            with patch.object(probe.source, 'transform'):
                probe.transform(root)
            text = edge.read_text()
            self.assertEqual(text.count('move.w $1e(a6),'), 8)
            self.assertEqual(text.count('        nop\n'), 6)
            self.assertNotIn('move.b $bf', text)
            self.assertIn('move.w d7,38(a4)', text)


if __name__ == '__main__':
    unittest.main()

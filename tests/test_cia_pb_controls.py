import tempfile
from pathlib import Path
from unittest.mock import patch
import unittest
import build_cia_pb_control_rom as probe


class PbControlsTests(unittest.TestCase):
    def test_matrix_and_independent_control_bits(self):
        rows = probe.trials()
        self.assertEqual(len(rows), 576)
        self.assertEqual(len(set(rows)), 576)
        self.assertEqual({bool(r[3] & 8) for r in rows}, {False, True})
        self.assertEqual({bool(r[3] & 16) for r in rows}, {False, True})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rom = root / 'src/rom'
            rom.mkdir(parents=True)
            (rom/'experiment.asm').write_text('cmpi.w #66,(a4)')
            (rom/'edge_kernel.asm').write_text('\n'.join(f'''        moveq #$19,d7
        btst #2,7(a4)
        beq.s .plain{address:x}
        ori.w #6,d7
.plain{address:x}:''' for address in (0xffda00, 0xffdc00)))
            with patch.object(probe.source, 'transform'):
                probe.transform(root)
            text = (rom/'edge_kernel.asm').read_text()
            self.assertEqual(text.count('andi.w #$fff7,d7'), 2)
            self.assertEqual(text.count('btst #4,7(a4)'), 2)
            self.assertNotIn('ori.w #6,d7', text)

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


class ApertureProbeTests(unittest.TestCase):
    def test_banks_preserve_samples_and_only_change_post_pb_aperture(self):
        import shutil
        import build_cia_request_aperture_rom as aperture
        rows = aperture.trials()
        self.assertEqual(len(rows), 1280)
        self.assertEqual(len(set(rows)), 1280)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(aperture.base.ROOT / 'src', root / 'src')
            experiment = root / 'src/rom/experiment.asm'
            experiment.write_text(experiment.read_text().replace('        cmpi.w #10,(a4)', '        cmpi.w #56,(a4)\n        cmpi.w #10,(a4)', 1))
            aperture.transform(root)
            text = (root / 'src/rom/edge_kernel.asm').read_text()
            tail = text[text.index('        dcb.b $ffda00-*,0'):]
            self.assertEqual(tail.count('        exg d2,d2'), 2)
            self.assertEqual(tail.count('move.w $1e(a6),'), 16)
            self.assertNotIn('move.b $bfed01', tail)
            self.assertNotIn('move.b $bfdd00', tail)
            for address in ('ffda00', 'ffdc00', 'ffde00', 'ffe000'):
                self.assertIn('dcb.b $' + address + '-*,0', tail)


class RequestClearProbeTests(unittest.TestCase):
    def test_clear_and_pb_controls_have_identical_ack_and_aperture(self):
        import shutil
        import build_cia_request_clear_rom as clear
        self.assertEqual(len(clear.trials()), 640)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(clear.base.ROOT / 'src', root / 'src')
            experiment = root / 'src/rom/experiment.asm'
            experiment.write_text(experiment.read_text().replace('        cmpi.w #10,(a4)',
                                  '        cmpi.w #56,(a4)\n        cmpi.w #10,(a4)', 1))
            clear.transform(root)
            text = (root / 'src/rom/edge_kernel.asm').read_text()
            tail = text[text.index('        dcb.b $ffda00-*,0'):]
            self.assertEqual(tail.count('move.w #$2008,$9c(a6)'), 8)
            self.assertEqual(tail.count('move.w $1e(a6),'), 32)
            self.assertEqual(tail.count('move.b $bfed01,d1'), 2)
            self.assertEqual(tail.count('move.b $bfdd00,d1'), 2)
            self.assertEqual(tail.count('exg d2,d2'), 4)
            self.assertIn('addi.w #24,d0', (root / 'src/rom/irq_stage_kernel.i').read_text())


if __name__ == '__main__':
    unittest.main()

from pathlib import Path
import tempfile
import unittest
import build_copper_dma_collision_rom as collision
import build_pointer_collision_rom as pointer


class CollisionProbeTests(unittest.TestCase):
    def test_descriptors_cover_writer_plane_half_and_controls(self):
        for probe, total in ((collision, 800), (pointer, 480)):
            rows = probe.trials()
            self.assertEqual(len(rows), total)
            self.assertEqual(len(set(rows)), total)
            self.assertEqual({r[2] for r in rows}, set(range(8)))
        self.assertEqual({r[1] for r in pointer.trials()}, {1, 2, 3})

    def test_settled_observer_and_pointer_selection_are_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            rom = stage/'src/rom'
            rom.mkdir(parents=True)
            (rom/'experiment.asm').write_text('cmpi.w #49,(a4)')
            pointer.transform(stage)
            text = (rom/'blitter_handoff_kernel.i').read_text()
            self.assertIn('cmpi.w #73,(a4)', (rom/'experiment.asm').read_text())
            self.assertIn('clr.w $102(a6)', text)
            self.assertIn('move.w #$00e4,d4', text)
            self.assertIn('move.w #$00e2,d4', text)
            self.assertIn('lea $5a000,a0', text)
            self.assertNotIn('lea $2a000,a0', text)
            self.assertIn('move.w #5,d5', text)
            self.assertLess(text.index('cmpi.w #$4420,d0'), text.index('move.w $0e(a6),16(a4)'))
            self.assertLess(text.index('move.w $0e(a6),16(a4)'), text.index('move.w #$7fff,$96(a6)', text.index('.settled_line:')))
            self.assertIn('move.l #$19000,$e0(a6)\n        move.l #$19000,$e4(a6)', text)

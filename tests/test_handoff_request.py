from pathlib import Path
import tempfile
import unittest
import build_handoff_request_rom as probe


class HandoffRequestTests(unittest.TestCase):
    def test_matrix_has_paired_sources_and_inert_controls(self):
        rows = probe.trials()
        self.assertEqual(len(rows), 2304)
        self.assertEqual(len(set(rows)), len(rows))
        descriptors = set(rows)
        for kind, target, variant, phase, pad, repeat in rows:
            self.assertEqual(target % 3, 0)
            self.assertIn((kind, target, variant ^ 16, phase, pad, repeat), descriptors)
            self.assertIn((kind, target, variant ^ 8, phase, pad, repeat), descriptors)
            self.assertIn((variant >> 1) & 3, (0, 1, 2))

    def test_staged_observers_change_masks_without_changing_read_opcode(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            rom = stage / 'src/rom'
            rom.mkdir(parents=True)
            original = Path(probe.__file__).parent / 'src/rom'
            for name in ('experiment.asm', 'blitter_handoff_kernel.i', 'blitter_handoff_observer.i'):
                (rom / name).write_bytes((original / name).read_bytes())
            probe.transform(stage)
            kernel = (rom / 'blitter_handoff_kernel.i').read_text()
            for mask in ('01ff', '09f0', '08f0'):
                self.assertIn('move.w #$' + mask + ',d4', kernel)
            self.assertNotIn('move.w #$0fff,d4', kernel)
            self.assertIn('move.l #$dff002,d4', kernel)
            self.assertNotIn('move.l #$f80000,d4', kernel)
            self.assertEqual((rom / 'blitter_handoff_observer.i').read_text().count('move.w (a1),d0'), 8)

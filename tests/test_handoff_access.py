from pathlib import Path
import tempfile
import unittest
import build_handoff_access_rom as probe


class HandoffAccessTests(unittest.TestCase):
    def test_source_controls_keep_identical_first_read_and_one_word_blits(self):
        rows=probe.trials()
        self.assertEqual(len(rows),1536)
        self.assertEqual(len(set(rows)),1536)
        self.assertEqual({r[1] for r in rows},{3,6,9,12})
        self.assertEqual({r[1]%3 for r in rows},{0})
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp);rom=stage/'src/rom';rom.mkdir(parents=True)
            original=Path(probe.__file__).parent/'src/rom'
            for name in ('experiment.asm','blitter_handoff_kernel.i','blitter_handoff_observer.i'):
                (rom/name).write_bytes((original/name).read_bytes())
            probe.transform(stage)
            observer=(rom/'blitter_handoff_observer.i').read_text()
            self.assertEqual(observer.count('move.w (a1),d0'),8)
            self.assertNotIn('move.w $02(a6),d0',observer)
            kernel=(rom/'blitter_handoff_kernel.i').read_text()
            self.assertIn('cmpi.w #15,d0',kernel)
            for address in ('$dff002','$10000','$c70000','$f80000'):
                self.assertIn('move.l #'+address+',d4',kernel)
            self.assertIn('move.w #$a55a,$c70000',kernel)

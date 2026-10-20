from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build_cpu_operand_rom as probe


class OperandTests(unittest.TestCase):
    def test_matrix_is_bounded_and_selects_source_memory_dma_independently(self):
        rows=probe.trials()
        self.assertEqual(len(rows),960)
        self.assertEqual(len(set(rows)),960)
        self.assertEqual({r[2]&7 for r in rows},{4})
        self.assertEqual({r[2]>>5 for r in rows},{0,1,2})
        self.assertEqual({(r[2]>>3)&3 for r in rows},{0,1,2,3})
        with tempfile.TemporaryDirectory() as directory:
            stage=Path(directory);rom=stage/'src/rom';rom.mkdir(parents=True)
            (rom/'experiment.asm').write_text('cmpi.w #61,(a4)')
            (rom/'irq_stage_kernel.i').write_text('        lsr.w #3,d0\n        lea $18100,a1')
            (rom/'irq_stage_observer.i').write_text('.loop:\n        nop\n        move.b d0,-(a1)\n.tst_loop:\n        tst.w (a1)')
            with patch.object(probe.dma,'transform'):
                probe.transform(stage)
            observer=(rom/'irq_stage_observer.i').read_text()
            self.assertNotIn('-(a1)',observer)
            self.assertIn('move.w (a1),d0',observer)
            self.assertIn('cmp.w (a1),d0',observer)
            self.assertIn('andi.w #3,d0',(rom/'irq_stage_kernel.i').read_text())


if __name__=='__main__':
    unittest.main()

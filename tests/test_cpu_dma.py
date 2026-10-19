import tempfile
from pathlib import Path
import shutil
import unittest
import build_cpu_dma_rom as b
import compare_irq_stage as c
from test_irq_stage import row


class CPUDMATests(unittest.TestCase):
    def test_matrix_and_source_decode(self):
        rows=b.trials()
        self.assertEqual(len(rows),1920)
        self.assertEqual(len(set(rows)),1920)
        for dma in range(4):
            for source,level in enumerate((2,6,2,6,3,3)):
                r=dict(row(),kind=61,variant=source+8*dma,irq_level=level)
                c.validate(r)
                self.assertEqual(c.source_mask(r),(8,0x2000,8,0x2000,16,16)[source])
                self.assertTrue(c.source_name(r).endswith(f"_DMA{dma}"))
                self.assertEqual(c.compare([r],[dict(r)])["counts"]["matches"],1)
        with self.assertRaises(ValueError):c.validate(dict(row(),kind=61,variant=31))

    def test_read_timing_difference_is_reported_without_relaxing_visibility(self):
        r=dict(row(),kind=61,target=4,variant=8,irq_level=0x4250,
               second_counter_or_beam=8,second_icr_or_level=8)
        c.validate(r)
        changed=dict(r,irq_level=r['irq_level']+2)
        self.assertEqual(c.compare([r],[changed])['counts']['no_identical_bracket'],1)
        report=c.access_bracket_summary([r],[changed])
        self.assertEqual(report['counts']['read_bracket_mismatches'],1)
        self.assertEqual(report['groups'][0]['first_divergent_read'],0)

    def test_dma_staging_preserves_software_source_and_stop_guard(self):
        root=Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as folder:
            stage=Path(folder);rom=stage/'src/rom';rom.mkdir(parents=True)
            (rom/'experiment.asm').write_text('cmpi.w #56,(a4)')
            for name in ('irq_stage_kernel.i','irq_stage_observer.i'):
                shutil.copyfile(root/'src/rom'/name,rom/name)
            b.transform(stage)
            observer=(rom/'irq_stage_observer.i').read_text()
            kernel=(rom/'irq_stage_kernel.i').read_text()
            self.assertIn('move.l #$ffcd1a,6(sp)',observer)
            self.assertEqual(observer.count('move.w d6,$96(a6)'),5)
            self.assertIn('andi.w #7,d0',kernel)
            self.assertIn('move.w #$6200,$100(a6)',kernel)
            self.assertIn('move.w #$01fe,(a0)+',kernel)

    def test_built_stop_continuation_is_instruction_boundary(self):
        image=Path(__file__).parents[1]/'build/cpu-dma-v2/a500-timing-rom.bin'
        if not image.exists():self.skipTest('local assembled image not available')
        data=image.read_bytes()
        self.assertEqual(data[0x7cd16:0x7cd1a],bytes.fromhex('4e722000'))
        self.assertEqual(data[0x7cd1a:0x7cd1c],bytes.fromhex('6000'))

import tempfile
from pathlib import Path
import shutil
import unittest
import build_cpu_irq_rom as b
import compare_irq_stage as c
from test_irq_stage import row


class CPUControlTests(unittest.TestCase):
    def test_matrix_and_levels(self):
        self.assertEqual(len(b.trials()), 1152)
        self.assertEqual(len(b.trials((1,3))), 768)
        for variant, level in enumerate((2,6,2,6,3,3)):
            r=dict(row(), kind=58, variant=variant, irq_level=level)
            c.validate(r)
            self.assertEqual(c.compare([r],[dict(r)])["counts"]["matches"],1)
            changed=dict(r,irq_beam=r["irq_beam"]+2)
            self.assertEqual(c.compare([r],[changed])["counts"]["mismatches"],1)

    def test_staging_records_pc_before_stop_return_guard(self):
        root=Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as folder:
            stage=Path(folder); rom=stage / "src/rom";rom.mkdir(parents=True)
            for name in ("irq_stage_kernel.i","irq_stage_observer.i"):
                shutil.copyfile(root / "src/rom" / name,rom / name)
            (rom / "experiment.asm").write_text("cmpi.w #56,(a4)")
            b.transform(stage)
            text=(rom / "irq_stage_observer.i").read_text()
            self.assertEqual(text.count("jsr cpu_irq_stop_guard"),4)
            self.assertIn("move.l #$ffcd10,6(sp)",text)
            self.assertLess(text.index("move.l 2(sp),ISPC(a5)"),text.index("jsr cpu_irq_stop_guard"))
            self.assertIn("move.l #$ffe080,$68",(rom / "irq_stage_kernel.i").read_text())

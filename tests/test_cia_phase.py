from pathlib import Path
import shutil
import tempfile
import unittest
import build_cia_phase_rom as b
import compare_irq_stage as c
from test_irq_stage import row


class CIAPhaseTests(unittest.TestCase):
    def test_matrix_is_bounded_and_keeps_generation_paths_separate(self):
        rows = b.trials()
        self.assertEqual(len(rows), 1920)
        self.assertEqual(len(set(rows)), 1920)
        self.assertEqual({r[2] for r in rows}, {0, 2, 5, 6})

    def test_calibration_is_a_matching_condition_not_a_shift(self):
        r = dict(row(), kind=57, variant=0, irq_level=2)
        for field in ('end_beam', 'second_counter_or_beam'):
            bad = dict(r); bad[field] += 1
            result = c.compare([r], [bad])['counts']
            self.assertEqual(result['no_identical_bracket'], 1)
            self.assertEqual(result['matches'], 0)
        self.assertEqual(c.measures(r), c.measures(dict(r, second_icr_or_level=0xff)))

    def test_phase_coverage_does_not_select_by_irq_outcome(self):
        r = dict(row(), kind=57, variant=0, irq_level=2)
        hardware = [dict(r, repeat=i, end_beam=0x4252,
                         second_counter_or_beam=0x4265+i) for i in range(5)]
        candidate = dict(hardware[3], repeat=0)
        self.assertEqual(c.compare(hardware, [candidate])["counts"]["matches"], 1)
        candidate["irq_beam"] += 2
        result = c.compare(hardware, [candidate])["counts"]
        self.assertEqual(result["mismatches"], 1)
        self.assertEqual(result["no_identical_bracket"], 0)
        candidate["launch_ref"] += 1
        self.assertEqual(c.compare(hardware, [candidate])["counts"]["no_identical_bracket"], 1)
        self.assertEqual(sum(v["cases"] for v in c.calibration_summary(hardware)), 5)

    def test_masked_stream_uses_its_declared_settled_field(self):
        r = dict(row(), kind=57, target=4, variant=5, end_ref=8,
                 second_counter_or_beam=0x4210, second_icr_or_level=0xff)
        c.validate(r)
        self.assertEqual(c.measures(r)['settled'], 8)
        with self.assertRaises(ValueError):
            c.validate(dict(r, end_ref=0))

    def test_staging_preserves_calibration_and_uses_mask_enable_controls(self):
        root = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            rom = stage / 'src/rom'
            rom.mkdir(parents=True)
            for name in ('irq_stage_kernel.i', 'irq_stage_observer.i'):
                shutil.copyfile(root / 'src/rom' / name, rom / name)
            (rom / 'experiment.asm').write_text('cmpi.w #56,(a4)')
            (rom / 'edge_kernel.asm').write_text('')
            b.transform(stage)
            trial = (rom / 'irq_stage_kernel.i').read_text()
            observer = (rom / 'irq_stage_observer.i').read_text()
            edge = (rom / 'edge_kernel.asm').read_text()
            self.assertIn('move.w #$009a,d0', trial)
            self.assertNotIn('move.w a1,38(a4)', trial)
            self.assertNotIn('move.w 6(a6),16(a4)', trial)
            self.assertIn('move.w d4,16(a4)', observer)
            self.assertIn('move.b #$81,$bfed01', edge)
            self.assertIn('move.b #$81,$bfdd00', edge)
            self.assertIn('cmpi.w #57,(a4)', (rom / 'experiment.asm').read_text())
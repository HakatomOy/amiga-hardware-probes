import unittest
from pathlib import Path
import tempfile
import shutil
import build_handoff_focus_rom as b
import compare_handoff_focus as c
from test_irq_stage import row


def sample():
    return dict(row(),kind=59,target=3,variant=2,status=0,launch_beam=0x4250,
                counter=0x4270,icr=0x4280,irq_beam=0xaaaa,irq_level=0xaaaa)


class HandoffFocusTests(unittest.TestCase):
    def test_matrix(self):
        self.assertEqual(len(b.trials()),128)
        self.assertEqual(len(b.trials(True)),256)
        self.assertEqual({r[2] for r in b.trials()},{2,3,10,11})

    def test_value_missing_shift_and_invalid_detection(self):
        r=sample()
        self.assertEqual(c.compare([r],[dict(r)])["counts"]["matches"],1)
        self.assertEqual(c.compare([r],[])["counts"]["missing_results"],1)
        self.assertEqual(c.compare([r],[dict(r,counter=r['counter']+2)])["counts"]["mismatches"],1)
        self.assertEqual(c.compare([r],[dict(r,launch_beam=r['launch_beam']+2)])["counts"]["no_identical_bracket"],1)
        with self.assertRaises(ValueError):c.validate(dict(r,status=1))

    def test_pattern_groups_delta_without_shifting_actual_measurements(self):
        a=sample();b=dict(a,delay=1,counter=a['counter']+8)
        result=c.compare([a,b],[dict(a,counter=a['counter']+2),dict(b,counter=b['counter']+2)])
        self.assertEqual(len(result['groups']),1)
        self.assertEqual(result['groups'][0]['count'],2)
        self.assertEqual(result['groups'][0]['representatives'][0]['differences'][0][1:],(0x4270,0x4272))

    def test_cross_line_patterns_sort_without_packed_beam_subtraction(self):
        a=sample();b=dict(a,delay=1,counter=0x42e0)
        report=c.compare([a,b],[dict(a,counter=0x4272),dict(b,counter=0x4301)])
        self.assertEqual(report["counts"]["mismatches"],2)
        self.assertEqual(len(report["groups"]),2)

    def test_candidate_delta_keeps_new_field_regressions_visible(self):
        r=sample();before=dict(r,counter=r['counter']-2)
        after=dict(r,irq_beam=0)
        result=c.candidate_delta([r],[before],[after])
        self.assertEqual(result['repaired_fields'],{'handoff_beam':1})
        self.assertEqual(result['regressed_fields'],{'final_first_d':1})
        self.assertEqual(result['counts']['complete_repairs'],0)
        self.assertEqual(result['counts']['cases_with_field_regressions'],1)

    def test_conflicting_reference_excluded(self):
        r=sample()
        self.assertEqual(c.compare([r,dict(r,repeat=1,counter=1)],[r])["counts"]["unstable_reference"],1)

    def test_alignment_clobber_is_restored_before_indirect_write(self):
        root=Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as folder:
            stage=Path(folder);rom=stage/'src/rom';rom.mkdir(parents=True)
            (rom/'experiment.asm').write_text('cmpi.w #49,(a4)')
            for name in ('blitter_handoff_kernel.i','blitter_handoff_observer.i'):
                shutil.copyfile(root/'src/rom'/name,rom/name)
            b.transform(stage)
            text=(rom/'blitter_handoff_kernel.i').read_text()
            self.assertIn('jsr $fb0000\n        movea.l d2,a2',text)
            self.assertIn('move.l #$dff1fe,d2',text)
            self.assertIn('move.w d5,(a2)',(rom/'blitter_handoff_observer.i').read_text())

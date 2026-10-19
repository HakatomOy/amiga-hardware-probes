from pathlib import Path
import tempfile
import unittest
import build_serial_phase_rom as probe
from tools.screen_serial_delay import screen


class SerialPhaseTests(unittest.TestCase):
    def test_matrix_and_independent_phase_brackets(self):
        rows=probe.trials()
        self.assertEqual(len(rows),384)
        self.assertEqual(len(set(rows)),384)
        self.assertEqual(len(probe.trials(True)),1536)
        self.assertEqual({r[4]>>5 for r in rows if r[2]==0},{14,15,16})
        self.assertEqual({r[4]>>5 for r in rows if r[2]==1},{30,31,32})
        with tempfile.TemporaryDirectory() as directory:
            stage=Path(directory);rom=stage/'src/rom';rom.mkdir(parents=True)
            (rom/'experiment.asm').write_text('cmpi.w #56,(a4)\njsr irq_stage_trial')
            (rom/'cia_serial_buffer_kernel.i').write_text((Path(probe.__file__).parent/'src/rom/cia_serial_buffer_kernel.i').read_text())
            probe.transform(stage)
            text=(rom/'cia_serial_buffer_kernel.i').read_text()
            self.assertLess(text.index('move.b $400(a0),d5'),text.index('move.b $d00(a0),d3'))
            self.assertLess(text.index('move.b $d00(a0),d3'),text.index('move.b $400(a0),d6'))
            self.assertIn('move.w d5,16(a4)',text)
            self.assertIn('move.w d6,18(a4)',text)
            self.assertIn('lsr.w #5,d1',text)

    def test_delay_screen_is_not_acceptance_and_excludes_ambiguous_brackets(self):
        rows=[dict(kind=64,variant=0,phase=1,status=0,aux=15,end_ref=28-t,
                   end_beam=(34-t)%32,icr=8 if t>=4 else 0) for t in range(9)]
        report=screen(rows)
        self.assertEqual([d for d,n in report['errors_by_delay_E'].items() if n==0],[4])
        rows[4]['icr']=0
        self.assertEqual(screen(rows)['errors_by_delay_E'][4],1)
        rows[0]['end_ref']=1
        self.assertEqual(screen(rows)['excluded']['possible_reload_before_final_TB_read'],1)


if __name__=='__main__':
    unittest.main()

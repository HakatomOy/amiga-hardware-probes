import tempfile
from pathlib import Path
import shutil
import unittest

import build_handoff_copper_race_rom as probe
import build_handoff_copper_access_rom as access
import build_handoff_copper_witness_rom as witness
import build_copper_cpu_order_rom as order
import build_copper_cpu_opcode_rom as opcode
import build_copper_cpu_quiet_rom as quiet
from tools.verify_copper_overlap import analyze
from tools.summarize_copper_cpu_order import index_trace, screen_phases, early_flags


class CopperRaceTests(unittest.TestCase):
    def test_quiet_trace_keeps_fetch_before_cpu_witness_and_write_after_completion(self):
        import rom_results
        row = dict(zip(rom_results.FIELDS[:6], (83, 0, 6, 0, 0, 0)))
        lines = ['COPPROBE MOVE v=043 h=05 reg=09c val=8002',
                 'CPUBUS kind=custom addr=00dff1fe v=043 h=07',
                 'COPPROBE MOVE v=043 h=08 reg=09c val=8010',
                 'CPUBUS kind=write addr=00006002 v=043 h=0d ev=043 eh=0f']
        result = index_trace(lines, [row], {'83,0,6,0,0,0'})
        self.assertEqual(result['83,0,6,0,0,0']['fetch_minus_cpu_grant_cck'], -8)
        with self.assertRaisesRegex(ValueError, 'coverage'):
            index_trace(lines[:2] + lines[3:], [row], {'83,0,6,0,0,0'})

    def test_quiet_probe_keeps_copper_but_disables_display_planes(self):
        self.assertEqual(len(quiet.trials()),512)
        with tempfile.TemporaryDirectory() as folder:
            stage=Path(folder)
            shutil.copytree(quiet.base.ROOT/'src',stage/'src')
            quiet.transform(stage)
            kernel=(stage/'src/rom/blitter_handoff_kernel.i').read_text()
            self.assertNotIn('move.w #$6200,$100(a6)',kernel)
            observer=(stage/'src/rom/blitter_handoff_observer.i').read_text()
            self.assertEqual(observer.count('move.w #$8080,$96(a6)'),8)

    def test_opcode_probe_overwrites_first_word_and_keeps_constant_safe_data(self):
        self.assertEqual(len(opcode.trials()),512)
        with tempfile.TemporaryDirectory() as folder:
            stage=Path(folder)
            shutil.copytree(opcode.base.ROOT/'src',stage/'src')
            opcode.transform(stage)
            kernel=(stage/'src/rom/blitter_handoff_kernel.i').read_text()
            observer=(stage/'src/rom/blitter_handoff_observer.i').read_text()
            self.assertIn('addi.l #$6000,d4',kernel)
            self.assertIn('move.w #$01fe,(a1)',kernel)
            self.assertIn('move.w #$8004,2(a1)',kernel)
            self.assertEqual(observer.count('move.w #$009c,d0'),8)

    def test_early_flags_require_matching_read_brackets(self):
        model = dict(launch_ref=1,end_ref=2,icr=3,counter=0)
        hw = dict(model,counter=4)
        case = dict(status='matches',candidate=model,hardware=[hw,hw],expected=[4],actual=[4])
        result = early_flags({'case':case},0)
        self.assertEqual(result['counts']['early_differences_with_matching_final_order'],1)
        model['icr'] = 4
        self.assertEqual(early_flags({'case':case},0)['counts']['clock_mismatch'],1)

    def test_write_phase_screen_checks_both_repairs_and_regressions(self):
        indexed = {'a':dict(fetch_minus_cpu_grant_cck=1),'b':dict(fetch_minus_cpu_grant_cck=1)}
        cases = {'a':dict(expected=[4],actual=[2]),'b':dict(expected=[2],actual=[2])}
        results = screen_phases(indexed,cases,0)['results']
        self.assertEqual(results[1]['repairs'],1)
        self.assertEqual(results[1]['regressions'],1)
        cases['a']['actual'] = [4]
        with self.assertRaisesRegex(ValueError,'does not reproduce'):
            screen_phases(indexed,cases,0)

    def test_copper_order_trace_binds_fetch_to_write_grant_not_log_order(self):
        import rom_results
        row = dict(zip(rom_results.FIELDS[:6], (81,6,46,0,0,0)))
        lines = ['CPUBUS kind=custom addr=00dff1fe v=043 h=07',
                 'COPPROBE MOVE   v=043 h=0e reg=09c val=8002',
                 'CPUBUS kind=write addr=00006022 v=043 h=0d ev=043 eh=0f',
                 'COPPROBE MOVE   v=043 h=a4 reg=09c val=8010']
        result = index_trace(lines,[row],{'81,6,46,0,0,0'})
        self.assertEqual(result['81,6,46,0,0,0']['fetch_minus_cpu_grant_cck'],1)
        with self.assertRaisesRegex(ValueError,'write/fetch'):
            index_trace([lines[0],lines[1],lines[3]],[row],{'81,6,46,0,0,0'})

    def test_direct_copper_ordering_has_no_blitter_and_prepared_old_new_words(self):
        rows = order.trials()
        self.assertEqual(len(rows), 512)
        self.assertTrue(all(r[2]&8 for r in rows))
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            shutil.copytree(order.base.ROOT/'src', stage/'src')
            order.transform(stage)
            kernel = (stage/'src/rom/blitter_handoff_kernel.i').read_text()
            observer = (stage/'src/rom/blitter_handoff_observer.i').read_text()
            self.assertIn('move.w #$8002,(a1)', kernel)
            self.assertIn('move.w #$009c,-2(a1)', kernel)
            self.assertIn('addi.l #$6002,d4', kernel)
            self.assertNotIn('bne.w .no_copper_list', kernel)
            self.assertEqual(observer.count('move.w #$8004,d0'), 8)

    def test_register_witness_has_same_post_start_nops_and_delayed_writeback(self):
        self.assertEqual(len(witness.trials()), 768)
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            shutil.copytree(witness.base.ROOT/'src', stage/'src')
            witness.transform(stage)
            text = (stage/'src/rom/blitter_handoff_observer.i').read_text()
            self.assertEqual(text.count('move.w 6(a6),12(a4)'), 4)
            self.assertEqual(text.count('move.w 6(a6),d2'), 4)
            self.assertEqual(text.count('move.w 6(a6),d3\n        move.w d2,12(a4)'), 4)
            for n in range(4,8):
                body = text.split(f'sample_{n}:',1)[1].split('        rts',1)[0]
                self.assertIn(f'        rept {n-4}\n',body)

    def test_access_controls_use_identical_opcode_and_enabled_copper(self):
        rows = access.trials()
        self.assertEqual(len(rows), 1024)
        self.assertEqual(len(set(rows)), 1024)
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            shutil.copytree(access.base.ROOT/'src', stage/'src')
            access.transform(stage)
            text = (stage/'src/rom/blitter_handoff_observer.i').read_text()
            self.assertEqual(text.count('move.w (a1),d0'), 8)
            self.assertEqual(text.count('move.w #$8080,$96(a6)'), 8)

    def test_activity_after_completion_is_not_overlap(self):
        import rom_results
        row = dict(zip(rom_results.FIELDS[:6], (78,3,6,0,0,0)))
        lines = ['BLTP 0 66 100 START size=0041',
                 'BLTP 0 66 101 OWNER Copper',
                 'COPPROBE MOVE v=042 h=65 reg=1fe val=0000',
                 'BLTP 0 66 110 END source=bus_slot']
        self.assertEqual(analyze(lines, [row])['counts']['with_overlap_moves'], 1)
        with self.assertRaisesRegex(ValueError, 'no verified Copper overlap'):
            analyze([lines[0], lines[1], lines[3], lines[2]], [row])
        with self.assertRaisesRegex(ValueError, 'incomplete trace'):
            analyze(lines[:-1], [row])

    def test_matrix_and_finite_activity_witness(self):
        rows = probe.trials()
        self.assertEqual(len(rows), 1536)
        self.assertEqual(len(set(rows)), len(rows))
        self.assertEqual({(r[2] >> 1) & 3 for r in rows}, {2, 3})
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            shutil.copytree(probe.base.ROOT/'src', stage/'src')
            probe.transform(stage)
            observer = (stage/'src/rom/blitter_handoff_observer.i').read_text()
            self.assertEqual(observer.count('move.w #$8080,$96(a6)'), 8)
            self.assertEqual(observer.count('move.w #0,$88(a6)'), 8)
            self.assertEqual(observer.count('move.w d0,(a1)'), 8)
            kernel = (stage/'src/rom/blitter_handoff_kernel.i').read_text()
            self.assertIn('move.w #$8010,(a1)+', kernel)
            self.assertIn('rept 32', kernel)


if __name__ == '__main__':
    unittest.main()

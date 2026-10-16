import unittest
from pathlib import Path

import build_rom
import build_line_c_bus_data_rom as suite
import compare_timing_sweeps

ROOT = Path(__file__).resolve().parents[1]


class LineCBusDataRomTests(unittest.TestCase):
    def test_exact_kind46_matrix_and_literals(self):
        rows = suite.line_c_bus_data_rows()
        patterns = build_rom.line_c_bus_data_patterns()
        regions = build_rom.line_c_bus_data_regions()
        self.assertEqual(len(rows), 1536)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual({row[0] for row in rows}, {46})
        self.assertEqual({row[1] for row in rows}, set(range(16)))
        self.assertEqual({row[2] for row in rows}, set(range(6)))
        self.assertEqual({row[3] for row in rows}, {0, 1})
        self.assertEqual({row[4] for row in rows}, {0})
        self.assertEqual({row[5] for row in rows}, set(range(8)))
        self.assertEqual([item['data'] for item in patterns],
                         [0x0000, 0xffff, 0x2000, 0x0800, 0x2800, 0xd7ff])
        self.assertEqual([item['address'] for item in regions], [0x18000, 0xc01000])

    def test_kernel_write_is_between_launch_and_eight_adjacent_reads(self):
        asm = (ROOT / 'src/rom/edge_kernel.asm').read_text()
        kernel = asm.split('line_c_bus_data_observer:', 1)[1].split('\n; Kind', 1)[0]
        instructions = [line.strip() for line in kernel.splitlines()
                        if line.strip() and not line.lstrip().startswith(';')]
        launch = instructions.index('move.w d5,(a1)')
        self.assertEqual(instructions[launch + 1], 'move.w d3,(a3)')
        self.assertEqual(instructions[launch + 2:launch + 10],
                         [f'move.w $02(a6),d{i}' for i in range(8)])
        busy_clear = instructions.index('bne.s *-6')
        self.assertEqual(instructions[busy_clear + 2:busy_clear + 4],
                         ['move.w $10000,14(a4)', 'move.w $11050,18(a4)'])

    def test_controller_loads_pattern_and_region_before_observer(self):
        asm = (ROOT / 'src/rom/experiment.asm').read_text()
        routine = asm.split('line_c_bus_data_trial:', 1)[1].split(
            'include "line_c_bus_data_patterns.i"', 1)[0]
        pattern_load = routine.index('move.w (a2),d3')
        region_load = routine.index('movea.l (a3),a3')
        observer = routine.index('movea.l #$ff7800,a2')
        self.assertLess(pattern_load, region_load)
        self.assertLess(region_load, observer)
        self.assertIn('move.w #$8000,$74(a6)', routine)
        self.assertIn('ori.w #$0bca,d0', routine)
        self.assertIn('move.w #$0001,$42(a6)', routine)
        self.assertIn('move.w #$0082,d5', routine)
        self.assertIn('move.l a3,-(sp)', routine)
        self.assertIn('move.w 6(a4),-(sp)', routine)
        self.assertIn('clr.w 6(a4)', routine)
        self.assertIn('move.w #$ffff,$44(a6)', routine)
        self.assertIn('move.w #$ffff,$46(a6)', routine)
        self.assertIn('move.w d0,$11050', routine)
        self.assertIn('lsl.w #8,d0', routine)
        self.assertIn('lsl.w #4,d0', routine)
        self.assertNotIn('lsl.w #12,d0', routine)
        self.assertNotIn('move.w d0,$18000', routine)
        observer = routine.index('movea.l #$ff7800,a2')
        restore_phase = routine.index('move.w (sp)+,6(a4)')
        self.assertLess(observer, restore_phase)
        self.assertIn('move.l (sp)+,a3', routine)

    def test_runner_checks_sources_and_both_scratch_destinations(self):
        runner = (ROOT / 'run_rom.py').read_text()
        self.assertIn("'line_c_bus_data_observer' in manifest", runner)
        self.assertIn("'source-memory-check.json'", runner)
        self.assertIn("'Kind46 source/scratch-memory verification failed", runner)
        self.assertIn("'C_second_word'", runner)
        self.assertIn('postbusy_d_readbacks=result_checks', runner)

    def test_strict_comparator_covers_matrix_and_marks_sample_differences(self):
        def row(samples):
            return dict(counter=samples[0], icr=samples[1], irq_beam=samples[2],
                        irq_level=samples[3], saved_pc_offset=(samples[4] << 16) | samples[5],
                        status=samples[6], aux=samples[7], launch_beam=0x6050,
                        launch_ref=0,end_ref=0,
                        end_beam=0x6080, second_counter_or_beam=0x6070,
                        second_icr_or_level=0x6090)
        pairs=[]
        for key in suite.line_c_bus_data_rows():
            samples=[0x2000,0,0,0,0,0,0x2000,0]
            pairs.append((key,row(samples),row(samples)))
        report=compare_timing_sweeps._compare_line_c_bus_data(pairs)
        self.assertEqual(report['kind'],46)
        self.assertEqual(len(report['groups']),1536)
        changed=list(pairs)
        key,hw,emu=changed[0]
        diff=row([0,0,0,0,0,0,0,0])
        changed[0]=(key,hw,diff)
        report=compare_timing_sweeps._compare_line_c_bus_data(changed)
        self.assertTrue(report['groups'][0]['raw_mismatch'])
        with self.assertRaisesRegex(ValueError,'Incomplete kind46'):
            compare_timing_sweeps._compare_line_c_bus_data(pairs[:-1])


if __name__ == '__main__':
    unittest.main()

from pathlib import Path
import tempfile
import unittest

import build_collision_cpu_clear_rom as clear
import build_collision_cpu_poll_rom as poll
import build_dma_enable_phase_rom as phase
import build_dma_restart_boundary_rom as restart
import build_dma_nop_boundary_rom as nop
import build_dma_write_gap_rom as gap
import build_dma_gap_readback_rom as readback
import build_dma_steady_read_rom as steady
import build_copper_cold_fetch_race_rom as race
import build_copper_wait_mask_race_rom as mask_race
import build_bitplane_enable_source_race_rom as bpl_race
import build_custom_read_return_rom as custom_return
import build_custom_return_forms_rom as return_forms


def generated(builder):
    with tempfile.TemporaryDirectory() as directory:
        stage = Path(directory)
        source = stage / 'src/rom'
        source.mkdir(parents=True)
        (source / 'experiment.asm').write_text(
            (clear.base.ROOT / 'src/rom/experiment.asm').read_text())
        builder.transform(stage)
        return ((source / 'blitter_handoff_kernel.i').read_text(),
                (source / 'blitter_handoff_observer.i').read_text())


class CollisionCpuProbeTests(unittest.TestCase):
    def test_matrix_decouples_data_phase_width_and_dma(self):
        rows = phase.trials()
        self.assertEqual(len(set(rows)), 1024)
        # Every timing/control condition has every independent data pattern.
        for _, target, variant, launch, delay, repeat in rows:
            for pixels in range(4):
                self.assertIn((110, target, (variant & 15) | (pixels << 4),
                               launch, delay, repeat), rows)
            self.assertIn((110, target, variant ^ 2, launch, delay, repeat), rows)
            self.assertIn((110, target, variant ^ 8, launch, delay, repeat), rows)
        kernel, _ = generated(phase)
        self.assertIn('move.w #$4200,d4', kernel)
        self.assertIn('move.w #4095,d0', kernel)
        self.assertIn('btst #4,5(a4)', kernel)
        self.assertIn('btst #5,5(a4)', kernel)

    def test_critical_polling_sequence_and_outer_registers_are_preserved(self):
        kernel, observer = generated(poll)
        self.assertIn('movem.l d7/a3,-(sp)', kernel)
        self.assertIn('movem.l (sp)+,d7/a3', kernel)
        self.assertIn('move.w #$8300,$96(a6)\n.poll:', observer)
        self.assertIn('move.w #$8200,$96(a6)\n.poll:', observer)
        self.assertLess(observer.index('tst.w $0e(a6)'), observer.index('move.w d0,18(a4)'))
        self.assertNotIn('jmp (a2)', observer)

    def test_restart_controls_differ_only_in_register_and_enable_value(self):
        self.assertEqual(len(set(restart.trials())), 64)
        kernel, observer = generated(restart)
        self.assertIn('move.l a3,-(sp)', kernel)
        self.assertIn('movea.l (sp)+,a3', kernel)
        for variant in range(4):
            text = restart.observer(variant)
            self.assertLess(text.index('move.w 6(a6),d4'), text.index('16(a4)'))
            self.assertIn('move.w #0,$88(a6)' if variant & 2 else
                          'move.w #0,$180(a6)', text)
        self.assertEqual(observer.count('move.w $1e(a6),16(a4)'), 4)

    def test_nop_control_keeps_master_and_post_sample_before_ram_stores(self):
        self.assertEqual(len(set(nop.trials())), 64)
        kernel, observer = generated(nop)
        self.assertIn('move.w #$8200,d1', kernel)
        self.assertIn('move.w #$8280,d1', kernel)
        self.assertNotIn('move.w #0,$88(a6)', observer)
        self.assertEqual(observer.count('rept 4'), 2)
        self.assertEqual(observer.count('move.w #0,$180(a6)'), 2)
        for text in observer.split('restart_boundary_')[1:]:
            self.assertLess(text.index('move.w 6(a6),d4'), text.index('16(a4)'))

    def test_gap_control_crosses_all_actors_and_preserves_post_sample(self):
        self.assertEqual(len(set(gap.trials())), 256)
        kernel, observer = generated(gap)
        self.assertIn('lsl.l #7,d0', kernel)
        for delay in range(4):
            for actor in nop.VARIANTS:
                variant = actor | delay << 3
                text = observer.split(f'restart_boundary_{variant}:')[1].split('dcb.b')[0]
                self.assertIn('        nop\n' * delay + '        move.w 6(a6),d4', text)
                self.assertLess(text.index('move.w 6(a6),d4'), text.index('16(a4)'))
                self.assertIn(f'${0xffb000 + variant * 0x80:x}-*', observer)
        self.assertNotIn('move.w #0,$88(a6)', observer)

    def test_gap_triplets_keep_actor_prefix_and_store_after_third_read(self):
        self.assertEqual(len(set(readback.trials())), 256)
        _, old = generated(gap)
        _, new = generated(readback)
        for delay in range(4):
            for actor in nop.VARIANTS:
                label = f'restart_boundary_{actor | delay << 3}:'
                prior = old.split(label)[1].split('dcb.b')[0]
                text = new.split(label)[1].split('dcb.b')[0]
                self.assertEqual(prior.split('move.w 6(a6),d4')[0],
                                 text.split('move.w 6(a6),d4')[0])
                self.assertLess(text.index('move.w 6(a6),d6'), text.index('16(a4)'))
                self.assertIn('move.w d5,14(a4)', text)
                self.assertIn('move.w d6,18(a4)', text)

    def test_steady_probe_removes_copper_and_separates_activity_from_reads(self):
        self.assertEqual(len(set(steady.trials())), 128)
        kernel, observer = generated(steady)
        self.assertIn('move.w #$2600,$100(a6)', kernel)
        self.assertIn('move.w #$2081,$8e(a6)', kernel)
        self.assertIn('move.w #$8200,d1', kernel)
        self.assertIn('move.w #$8300,d1', kernel)
        self.assertNotIn('#$8280,d1', kernel)
        self.assertIn('.plane2_ready:\n        moveq #-1,d1\n        moveq #-1,d2', kernel)
        for variant in range(8):
            text = steady.observer(variant)
            self.assertLess(text.index('move.w 6(a6),d6'), text.index('move.w $0e(a6),d0'))
            self.assertLess(text.index('move.w 6(a6),d6'), text.index('16(a4)'))
            self.assertEqual(text.count('$96(a6)'), 1)
            self.assertNotIn('$88(a6)', text)

    def test_cold_fetch_race_preserves_registers_and_independent_witness(self):
        self.assertEqual(len(set(race.trials())), 256)
        kernel, observer = generated(race)
        self.assertIn('lea $2000,a1', kernel)
        self.assertIn('lea $2010,a1', kernel)
        self.assertIn('move.w #$8004,(a0)+', kernel)
        self.assertIn('move.w #$8008,(a0)+', kernel)
        self.assertIn('move.w #$0180,$2000', kernel)
        self.assertNotIn('move.w #$8280,d1', kernel)
        for variant in range(32):
            text = race.observer(variant)
            # ROM alignment may EXG D0/D1: load critical gate value afterward.
            self.assertLess(text.index('move.w #$'), text.index('move.w 6(a6),d3'))
            self.assertIn('move.w #$8380,d1' if variant & 1 else 'move.w #$8280,d1', text)
            self.assertLess(text.index('move.w d2,(a1)'), text.index('move.w $1e(a6),d0'))
            self.assertIn('move.w (a1),20(a4)', text)

    def test_wait_mask_race_separates_early_passage_and_settled_completion(self):
        self.assertEqual(len(set(mask_race.trials())), 256)
        kernel, observer = generated(mask_race)
        self.assertIn('move.w #$4341,(a0)+\n        move.w #$fffe,(a0)+', kernel)
        self.assertIn('move.w #$80fe,$2002', kernel)
        self.assertIn('move.w #$80fe,d2', kernel)
        self.assertIn('lea $2002,a1', kernel)
        for variant in range(32):
            text = mask_race.observer(variant)
            self.assertLess(text.index('cmpi.w #$42a0'), text.index('move.w d5,14(a4)'))
            self.assertLess(text.index('move.w d5,14(a4)'), text.index('cmpi.w #$4460'))
            self.assertLess(text.index('cmpi.w #$4460'), text.index('move.w d0,16(a4)'))

    def test_bitplane_race_isolates_first_source_words_and_preserves_controls(self):
        self.assertEqual(len(set(bpl_race.trials())), 256)
        kernel, _ = generated(bpl_race)
        self.assertIn('.plane2_ready:\n        moveq #0,d1\n        moveq #0,d2', kernel)
        self.assertIn('move.w #$ffff,$18000', kernel)
        self.assertIn('move.w #$ffff,$19000', kernel)
        self.assertIn('clr.w $19000', kernel)
        self.assertIn('lea $19000,a1', kernel)
        self.assertIn('lea $19010,a1', kernel)
        self.assertIn('move.w #$2600,$100(a6)', kernel)
        self.assertIn('tst.w $0e(a6)\n        jsr sync_beam', kernel)
        for variant in range(32):
            text = bpl_race.observer(variant)
            self.assertIn('move.w #$8380,d1' if variant & 1 else 'move.w #$8300,d1', text)
            self.assertLess(text.index('move.w d2,(a1)'), text.index('move.w $0e(a6),d0'))
            self.assertIn('move.w (a1),20(a4)', text)

    def test_custom_return_records_preserve_the_actual_common_return_mapping(self):
        self.assertEqual(len(set(custom_return.trials())), 160)
        kernel, observer = generated(custom_return)
        self.assertIn('dc.l $dff000,$dfeffc,$dff018,$dff008,$dff17a', kernel)
        # Common return overwrites24 with D4; D5's true following beam survives36.
        self.assertIn('move.w d4,24(a4)', kernel)
        self.assertIn('move.w d5,36(a4)', kernel)
        self.assertIn('move.w d6,18(a4)', observer)
        for variant in sorted({r[2] for r in custom_return.trials()}):
            text = custom_return.observer(variant)
            self.assertLess(text.index('move.w 6(a6),d6'), text.index('34(a4)'))
            self.assertIn('move.w d2,6(a0)' if (variant >> 1) & 7 == 4 else
                          'move.w 6(a0),d4', text)

    def test_return_forms_pair_exact_gate_instructions_and_fit_reserved_rom(self):
        rows = return_forms.trials()
        self.assertEqual(len(set(rows)), 320)
        for row in rows:
            self.assertIn((123, row[1], row[2] ^ 32, *row[3:]), rows)
        self.assertLessEqual(len(return_forms.VARIANTS) * return_forms.STRIDE, 0x1000)
        kernel, _ = generated(return_forms)
        self.assertIn('lea custom_return_observers(pc),a3', kernel)
        for variant in return_forms.VARIANTS:
            text = return_forms.observer(variant)
            gate = (f'move.w #${0x8380 if variant & 1 else 0x8300:x},$96(a6)'
                    if variant & 32 else 'move.w d1,$96(a6)')
            self.assertIn('move.w 6(a6),d3\n        ' + gate, text)


if __name__ == '__main__':
    unittest.main()

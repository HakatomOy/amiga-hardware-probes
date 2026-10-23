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


if __name__ == '__main__':
    unittest.main()

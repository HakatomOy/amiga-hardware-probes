"""Kind72: digital collision witness for late Copper/CPU DMA register writes."""
import argparse
from pathlib import Path
import shutil
import build_irq_stage_rom as base


def trials():
    return [(72, target, control + 4 * writer, h, 0, repeat)
            for target in (0, 1) for writer in (0, 1) for control in range(4)
            for h in range(25) for repeat in range(2)]


KERNEL = '''; Late-write fetch boundary; CLXDAT bit0 witnesses matching PF1/PF2 pixels.
blitter_handoff_trial:
        move.w #$2700,sr
        move.w #$7fff,$96(a6)
        move.w #$7fff,$9a(a6)
        move.w #$7fff,$9c(a6)
        move.w #$2c81,$8e(a6)
        move.w #$f4c1,$90(a6)
        move.w #$0038,$92(a6)
        move.w #$00d0,$94(a6)
        clr.w $108(a6)
        clr.w $10a(a6)
        move.w #$2600,$100(a6)
        move.w #$00c3,$98(a6)
        clr.w $110(a6)
        clr.w $112(a6)
        move.w 4(a4),d0
        andi.w #3,d0
        cmpi.w #1,d0
        bne.s .planes_on
        move.w #$0200,$100(a6)
.planes_on:
        moveq #-1,d1
        cmpi.w #2,d0
        bne.s .pattern_ready
        moveq #0,d1
.pattern_ready:
        lea $18000,a0
        lea $19000,a1
        lea $1a000,a2
        move.w #511,d0
.fill:
        move.w d1,(a0)+
        move.w d1,(a1)+
        clr.w (a2)+
        dbra d0,.fill
        move.l #$18000,$e0(a6)
        move.l #$19000,$e4(a6)
        move.w #$0096,d4
        move.w #$8100,d5
        move.w #$8280,d6
        tst.w 2(a4)
        beq.s .register_ready
        move.l #$1a000,$e4(a6)
        move.w #$00e6,d4
        move.w #$9000,d5
        move.w #$8380,d6
.register_ready:
        move.w 4(a4),d0
        andi.w #3,d0
        cmpi.w #3,d0
        bne.s .not_positive
        move.w #$01fe,d4
        move.w #$8380,d6
        move.l #$19000,$e4(a6)
.not_positive:
        move.w 6(a4),d2
        add.w d2,d2
        addi.w #$4211,d2
        tst.w 2(a4)
        beq.s .wait_word_ready
        addi.w #$a0,d2
.wait_word_ready:
        lea $6000,a0
        move.w d2,(a0)+
        move.w #$fffe,(a0)+
        move.w d4,d0
        btst #2,5(a4)
        beq.s .copper_writer
        move.w #$01fe,d0
.copper_writer:
        move.w d0,(a0)+
        move.w d5,(a0)+
        move.l #$fffffffe,(a0)+
        move.l #$6000,$80(a6)
        jsr sync_beam
        move.l #$dff000,a2
        adda.w d4,a2
        move.w d6,$96(a6)
        move.w #0,$88(a6)
.test_line:
        move.w 6(a6),d0
        cmpi.w #$4200,d0
        bcs.s .test_line
        tst.w $0e(a6)
        move.w 6(a6),12(a4)
        btst #2,5(a4)
        beq.s .wait_end
.wait_cpu:
        move.w 6(a6),d0
        cmp.w d2,d0
        bcs.s .wait_cpu
        move.w 6(a6),14(a4)
        move.w d5,(a2)
        move.w 6(a6),18(a4)
.wait_end:
        move.w 6(a6),d0
        cmpi.w #$4320,d0
        bcs.s .wait_end
        move.w 6(a6),26(a4)
        move.w $0e(a6),d0
        move.w 6(a6),34(a4)
        move.w d0,20(a4)
        move.w $0e(a6),22(a4)
        move.w #$7fff,$96(a6)
        clr.w 32(a4)
        rts
'''


def transform(stage):
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage/'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #49,(a4)', 'cmpi.w #72,(a4)'))
    (stage/'src/rom/blitter_handoff_kernel.i').write_text(KERNEL)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=72, targets=['BPLEN enable', 'BPL2PTL zero-to-ones'],
                            variants='bit2 CPU writer; low2 main/planes-off/zero-data/always-on controls',
                            phases='Copper WAIT BPLEN10..40 or pointerB0..E0 in two-CCK steps; CPU writes have measured pre/post beams',
                            measurement_fields='counter/ICR CLXDAT; irq_level/aux before/after collision read beams',
                            limitations='Collision is a digital pixel witness, not a framebuffer photo; source landing must be checked before attributing any difference to render delay.'))

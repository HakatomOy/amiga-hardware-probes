"""Kind109: isolate bitplane/Copper enable from the following COPJMP write."""
import argparse
from pathlib import Path
import shutil

import build_irq_stage_rom as base
import build_playfield_modes_rom as modes


def trials():
    return [(109, 8, variant, phase, 0, repeat)
            for variant in range(4) for phase in range(4) for repeat in range(4)]


def observer(variant):
    return f'''        dcb.b ${0xffb000 + variant * 0x100:x}-*,0
restart_boundary_{variant}:
        move.w 6(a6),d3
        move.w #${0x8380 if variant & 1 else 0x8300:x},$96(a6)
        move.w #0,${0x88 if variant & 2 else 0x180:x}(a6)
        move.w 6(a6),d4
.wait:
        move.w 6(a6),d0
        cmpi.w #$4460,d0
        bcs.s .wait
        move.w $1e(a6),16(a4)
        move.w d3,12(a4)
        move.w d4,24(a4)
        move.w #$7fff,$96(a6)
        clr.w 32(a4)
        rts
'''


def transform(stage):
    shutil.copyfile(__file__, stage / Path(__file__).name)
    shutil.copyfile(modes.__file__, stage / Path(modes.__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #49,(a4)', 'cmpi.w #109,(a4)'))
    setup = '''        lea $2000,a0
        move.w #$4341,(a0)+
        move.w #$fffe,(a0)+
        move.w #$009c,(a0)+
        move.w #$8004,(a0)+
        move.w #$ffff,(a0)+
        move.w #$fffe,(a0)+
        move.l #$2000,$80(a6)
        move.w #0,$88(a6)
        moveq #0,d0
        move.w 4(a4),d0
        lsl.l #8,d0
        addi.l #$ffb000,d0
        movea.l d0,a3
'''
    kernel = modes.KERNEL.replace('        jsr sync_beam', setup + '        jsr sync_beam')
    kernel = kernel.replace('blitter_handoff_trial:\n',
                            'blitter_handoff_trial:\n        move.l a3,-(sp)\n')
    kernel = kernel.replace('        rts', '        movea.l (sp)+,a3\n        rts')
    kernel = kernel.replace('        jsr $ffb000', '        nop\n        jsr (a3)')
    kernel = kernel.replace('        move.w d4,$100(a6)', '        move.w #$2200,$100(a6)')
    (stage / 'src/rom/blitter_handoff_kernel.i').write_text(kernel)
    (stage / 'src/rom/blitter_handoff_observer.i').write_text(
        ''.join(observer(v) for v in range(4)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=109, variants='bit0 COPEN; bit1 COPJMP instead of inert COLOR00 write',
                            fields={'12': 'pre-enable beam', '24': 'post-write beam',
                                    '16': 'INTREQR Copper completion bit2'},
                            limitations='64 ROM-only cases; identical immediate-write forms, '
                            'two-plane DMA in all cases; pre-enable input qualification only. '
                            'No RAM writes until post-write sample; four repeats per launch.'))

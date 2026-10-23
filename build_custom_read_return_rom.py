"""Kind122: compare custom-register read paths with an equal-length write."""
import argparse
from pathlib import Path
import shutil

import build_dma_restart_boundary_rom as cold

TARGETS = ('VHPOSR', 'DMACONR', 'INTREQR', 'CLXDAT', 'COLOR00_WRITE')


def trials():
    return [(122, 15, copper | target << 1 | gap << 4, phase, 0, repeat)
            for gap in range(2) for target in range(5) for copper in range(2)
            for phase in range(4) for repeat in range(2)]


def observer(variant):
    operation = 'move.w d2,6(a0)' if (variant >> 1) & 7 == 4 else 'move.w 6(a0),d4'
    return f'''        dcb.b ${0xffb000 + variant * 0x80:x}-*,0
custom_return_{variant}:
        move.w #${0x8380 if variant & 1 else 0x8300:x},d1
        moveq #0,d4
        move.w 6(a6),d3
        move.w d1,$96(a6)
''' + '        nop\n' * (variant >> 4) + f'''        {operation}
        move.w 6(a6),d5
        move.w 6(a6),d6
.wait:
        move.w 6(a6),d0
        cmpi.w #$4460,d0
        bcs.s .wait
        move.w $0e(a6),d0
        andi.w #1,d0
        move.w d0,34(a4)
        move.w $1e(a6),d0
        andi.w #8,d0
        move.w d0,16(a4)
        move.w d3,12(a4)
        move.w d4,20(a4)
        move.w d5,24(a4)
        move.w d6,18(a4)
        move.w #$7fff,$96(a6)
        clr.w 32(a4)
        rts
'''


def transform(stage):
    cold.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #109,(a4)', 'cmpi.w #122,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    text = p.read_text().replace('lsl.l #8,d0', 'lsl.l #7,d0')
    text = text.replace('#$2c81,$8e(a6)', '#$2081,$8e(a6)')
    text = text.replace('move.w #$2200,$100(a6)', 'move.w #$2600,$100(a6)')
    text = text.replace('.plane2_ready:\n', '.plane2_ready:\n        moveq #-1,d1\n        moveq #-1,d2\n')
    text = text.replace('move.w #$8004,(a0)+', 'move.w #$8008,(a0)+')
    text = text.replace('        jsr sync_beam', '''        move.w 4(a4),d0
        lsr.w #1,d0
        andi.w #7,d0
        lsl.w #2,d0
        lea custom_read_targets(pc),a0
        movea.l 0(a0,d0.w),a0
        moveq #0,d2
        tst.w $0e(a6)
        jsr sync_beam
        move.w #$8200,$96(a6)''')
    text += '''
        even
custom_read_targets:
        dc.l $dff000,$dfeffc,$dff018,$dff008,$dff17a
'''
    p.write_text(text)
    variants = sorted({row[2] for row in trials()})
    (stage / 'src/rom/blitter_handoff_observer.i').write_text(''.join(observer(v) for v in variants))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    cold.base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
                    profile=dict(kind=122, targets=TARGETS,
                                 variants='bit0 cold Copper; bits1:3 operand target; bit4 one NOP gap',
                                 fields={'12': 'input beam', '20': 'raw operand value',
                                         '24': 'first following beam', '18': 'second following beam',
                                         '34': 'PF1/PF2 activity bit0', '16': 'Copper completion bit3'},
                                 limitations='160 ROM-only cases. MOVE.W d16(An),Dn versus Dn,d16(An), '
                                 'both12 uncontended CPU clocks. Target pointer selected before alignment. '
                                 'Two following beam reads before RAM stores. Midline BPLEN, optional cold Copper; '
                                 'independent plane and Copper witnesses.'))

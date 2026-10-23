"""Kind121: CPU overwrite versus the first midline bitplane fetch."""
import argparse
from pathlib import Path
import shutil

import build_dma_restart_boundary_rom as cold


def trials():
    return [(121, 15, control | gap << 3, phase, 0, repeat)
            for gap in range(4) for control in range(8)
            for phase in range(4) for repeat in range(2)]


def observer(variant):
    return f'''        dcb.b ${0xffb000 + variant * 0x80:x}-*,0
bitplane_source_race_{variant}:
        move.w #${0x8380 if variant & 1 else 0x8300:x},d1
        move.w 6(a6),d3
        move.w d1,$96(a6)
''' + '        nop\n' * (variant >> 3) + '''        move.w d2,(a1)
        move.w 6(a6),d4
.wait:
        move.w 6(a6),d0
        cmpi.w #$4460,d0
        bcs.s .wait
        move.w $0e(a6),d0
        andi.w #1,d0
        move.w d0,14(a4)
        move.w $1e(a6),d0
        andi.w #8,d0
        move.w d0,16(a4)
        move.w (a1),20(a4)
        move.w d3,12(a4)
        move.w d4,24(a4)
        move.w #$7fff,$96(a6)
        clr.w 32(a4)
        rts
'''


def transform(stage):
    cold.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #109,(a4)', 'cmpi.w #121,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    text = p.read_text().replace('lsl.l #8,d0', 'lsl.l #7,d0')
    text = text.replace('#$2c81,$8e(a6)', '#$2081,$8e(a6)')
    text = text.replace('move.w #$2200,$100(a6)', 'move.w #$2600,$100(a6)')
    text = text.replace('.plane2_ready:\n', '.plane2_ready:\n        moveq #0,d1\n        moveq #0,d2\n')
    text = text.replace('        move.l #$18000,$e0(a6)', '''        move.w #$ffff,$18000
        move.w #$ffff,$19000
        btst #2,5(a4)
        beq.s .source_ready
        clr.w $19000
.source_ready:
        move.l #$18000,$e0(a6)''')
    text = text.replace('move.w #$8004,(a0)+', 'move.w #$8008,(a0)+')
    text = text.replace('        jsr sync_beam', '''        lea $19000,a1
        btst #1,5(a4)
        beq.s .store_target_ready
        lea $19010,a1
.store_target_ready:
        moveq #0,d2
        tst.w $0e(a6)
        jsr sync_beam
        move.w #$8200,$96(a6)''')
    p.write_text(text)
    (stage / 'src/rom/blitter_handoff_observer.i').write_text(''.join(observer(v) for v in range(32)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    cold.base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
                    profile=dict(kind=121,
                                 variants='bit0 cold Copper; bit1 neighbor overwrite; bit2 preseed zero; bits3:4 NOP gap',
                                 fields={'12': 'input beam', '14': 'PF1/PF2 source collision bit0',
                                         '16': 'finite Copper completion bit3',
                                         '20': 'CPU-written word', '24': 'diagnostic post-store beam'},
                                 limitations='256 ROM-only cases. Only first word of each plane isffff, '
                                 'all other source words zero. CPU clears first plane2 word or neighbor. '
                                 'PF1/PF2 collision witnesses old-word fetch; preseed-zero and neighbor controls. '
                                 'Master pre-enabled, BPLEN midline, optional cold finite Copper.'))

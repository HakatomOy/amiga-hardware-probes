"""Kind95: identical restart controls executed from ROM or copied chip RAM."""
import argparse
from pathlib import Path
import shutil

import build_copper_restart_access_rom as restart
import build_irq_stage_rom as base


def trials():
    return [(95, 3, 14 | (access << 5) | (mode << 8) | (gate << 10) | (ram << 12),
             phase, pad, repeat)
            for ram in range(2) for gate in range(2) for mode in range(3)
            for access in range(2) for phase in range(2) for pad in range(4)
            for repeat in range(2)]


def transform(stage):
    restart.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    path = stage / 'src/rom/experiment.asm'
    text = path.read_text()
    assert text.count('cmpi.w #93,(a4)') == 1
    path.write_text(text.replace('cmpi.w #93,(a4)', 'cmpi.w #95,(a4)'))
    path = stage / 'src/rom/blitter_handoff_kernel.i'
    text = path.read_text()
    anchor = '        ; Align in ROM, then apply phase and the 0..7 NOP launch padding.'
    assert text.count(anchor) == 1
    assert text.count('        jsr (a3)') == 1
    text = text.replace('        jsr (a3)', '        jsr $ffbf80')
    text = text.replace(anchor, '''        ; Copy for BOTH venues, outside the measured window. A1/A2 are
        ; restored by the existing aligned entry; do not clobber A3/D4.
        lea $ffb000,a1
        lea $30000,a2
        move.w #1023,d0
.copy_restart_banks:
        move.l (a1)+,(a2)+
        dbra d0,.copy_restart_banks
        move.w 4(a4),d0
        btst #12,d0
        beq.s .restart_venue_ready
        suba.l #$fcb000,a3
.restart_venue_ready:
''' + anchor)
    path.write_text(text)
    path = stage / 'src/rom/blitter_handoff_observer.i'
    text = path.read_text()
    anchor = '        move.w 6(a6),d2         ; input anchor precedes the unverified prefix\n'
    assert text.count(anchor) == 8
    text = text.replace(anchor, '')
    # Keep the input in common ROM, before the unknown venue's first fetch.
    text += '''
        dcb.b $ffbf80-*,0
restart_common_input:
        move.w 6(a6),d2
        jmp (a3)
'''
    path.write_text(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm', required=True)
    parser.add_argument('--wsl', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    base.build(args.vasm, args.wsl, args.out, rows=trials(), transform=transform,
               profile=dict(kind=95, variants='bit12 execute from30000 shadow instead offfb000 ROM;bit10 gate order;bit5 RGAread/write;bits9:8 off/WAIT/active',
                            fields={'12': 'input beam', '18': 'prefix-complete beam',
                                    '20': 'post-access beam', '16': 'access result',
                                    '28': 'settled IRQ', '30': 'settled beam'},
                            scratch='30000..30fff; outside code starting20000 and results40000',
                            limitations='All banks copied for both venues before alignment. Same instructions; address/prefetch arbitration differs. No blitter, exact raw qualification, no alignment.'))

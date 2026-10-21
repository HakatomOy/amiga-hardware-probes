"""Kind96: observe initial COPEN execution without a second measured restart."""
import argparse
from pathlib import Path
import shutil

import build_copper_restart_fetch_rom as fetch
import build_irq_stage_rom as base


def trials():
    return [(96, 3, 14 | (mode << 8) | 1024 | (ram << 12) | (seed << 13),
             phase, pad, repeat)
            for ram in range(2) for seed in range(2) for mode in range(3)
            for phase in range(2) for pad in range(4) for repeat in range(2)]


def transform(stage):
    fetch.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    path = stage / 'src/rom/experiment.asm'
    text = path.read_text()
    assert text.count('cmpi.w #95,(a4)') == 1
    path.write_text(text.replace('cmpi.w #95,(a4)', 'cmpi.w #96,(a4)'))
    path = stage / 'src/rom/blitter_handoff_kernel.i'
    text = path.read_text()
    anchor = '        ; Copy for BOTH venues, outside the measured window.'
    assert text.count(anchor) == 1
    text = text.replace(anchor, '''        ; Active first instruction raises COPER, then parks. Prepare before
        ; alignment; the optional disabled strobe controls the starting state.
        move.w #$009c,$6000
        move.w #$8010,$6002
        move.w #$ffff,$6004
        move.w #$fffe,$6006
        move.w 4(a4),d0
        andi.w #$0300,d0
        cmpi.w #$0200,d0
        bne.s .enable_seed_ready
        btst #5,4(a4)           ; variant bit13, high byte bit5
        beq.s .enable_seed_ready
        move.w #0,$88(a6)      ; COPEN is disabled; retain pending restart
.enable_seed_ready:
''' + anchor)
    path.write_text(text)
    path = stage / 'src/rom/blitter_handoff_observer.i'
    text = path.read_text()
    assert text.count('move.w #0,$88(a0)') == 8
    text = text.replace('move.w #0,$88(a0)', 'move.w #0,$1fe(a6)')
    assert text.count('        move.w 6(a6),d5') == 8
    text = text.replace('        move.w 6(a6),d5',
                        '        move.w $1e(a6),d6\n        move.w 6(a6),d5')
    text = text.replace('        move.w d5,20(a4)',
                        '        move.w d5,20(a4)\n        move.w d6,22(a4)')
    path.write_text(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm', required=True)
    parser.add_argument('--wsl', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    base.build(args.vasm, args.wsl, args.out, rows=trials(), transform=transform,
               profile=dict(kind=96,
                            variants='bits9:8 off/WAIT/active; bit12 RAM venue; bit13 disabled restart seed',
                            fields={'12': 'common ROM input', '18': 'prefix-complete beam',
                                    '16': 'VHPOSR result', '20': 'post-early-IRQ beam',
                                    '22': 'early INTREQ', '28': 'settled INTREQ', '30': 'settled beam'},
                            limitations='No measured COPJMP. Short active stream raises COPER then parks. Pending-restart and inherited-state controls; no blitter. Exact observations, no trace alignment.'))

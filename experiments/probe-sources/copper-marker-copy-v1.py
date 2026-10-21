"""Kind94: locate VHPOSR memory-destination marker timing with a small control."""
import argparse
from pathlib import Path
import shutil

import build_copper_restart_access_rom as restart
import build_irq_stage_rom as base


def trials():
    return [(94, 3, 14 | (mode << 8) | 1024 | (copy_control << 11), phase, pad, repeat)
            for copy_control in range(2) for mode in range(3)
            for phase in range(2) for pad in range(4) for repeat in range(2)]


def transform(stage):
    restart.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    path = stage / 'src/rom/experiment.asm'
    text = path.read_text()
    assert text.count('cmpi.w #93,(a4)') == 1
    path.write_text(text.replace('cmpi.w #93,(a4)', 'cmpi.w #94,(a4)'))
    path = stage / 'src/rom/blitter_handoff_observer.i'
    text = path.read_text()
    # All selected cases read VHPOSR. Both forms have the identical immediate
    # address prefix; only the marker destination and its nominal padding vary.
    text = text.replace('movea.l d4,a1\n        nop\n        nop', 'movea.l #$dff006,a1')
    blocks = text.split('restart_access_')
    for index in range(1, len(blocks)):
        bank = int(blocks[index].split(':', 1)[0])
        marker = ('move.w 6(a6),18(a4)\n        move.w 6(a6),d3'
                  if bank < 4 else
                  'move.w 6(a6),d6\n        nop\n        nop\n        move.w 6(a6),d3')
        blocks[index] = blocks[index].replace('move.w 6(a6),d3         ; measure prefix, rather than qualify it away', marker)
        blocks[index] = blocks[index].replace('move.w d3,18(a4)', 'move.w d3,22(a4)')
        if bank >= 4:
            blocks[index] = blocks[index].replace('move.w d5,20(a4)', 'move.w d5,20(a4)\n        move.w d6,18(a4)')
    path.write_text('restart_access_'.join(blocks))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm', required=True)
    parser.add_argument('--wsl', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    base.build(args.vasm, args.wsl, args.out, rows=trials(), transform=transform,
               profile=dict(kind=94, variants='bit11 register-marker+twoNOP control instead of memory marker;gate-first,RGAread only;off/WAIT/active;phase0/1,pad0..3',
                            fields={'12': 'input before prefix', '18': 'first marker sample',
                                    '22': 'following register marker', '20': 'post-access beam',
                                    '16': 'access result', '28': 'settled IRQ', '30': 'settled beam'},
                            limitations='No blitter; unknown marker instruction lies inside measured window. Exact raw input qualification; no alignment.'))

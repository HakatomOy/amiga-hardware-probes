"""Kind110: independent launch phase, plane data and two/four-plane pressure."""
import argparse
from pathlib import Path
import shutil

import build_irq_stage_rom as base
import build_collision_cpu_poll_rom as poll

DELAYS = (0, 1, 3, 5, 7, 9, 13, 15)


def trials():
    return [(110, 8, (four << 1) | (off << 3) | (pixels << 4), phase, delay, repeat)
            for four in range(2) for off in range(2) for pixels in range(4)
            for phase in range(4) for delay in DELAYS for repeat in range(2)]


def transform(stage):
    poll.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #108,(a4)', 'cmpi.w #110,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    text = p.read_text().replace('btst #0,7(a4)', 'btst #4,5(a4)')
    text = text.replace('btst #1,7(a4)', 'btst #5,5(a4)')
    text = text.replace('        move.w d4,$100(a6)', '''        move.w #$2200,d4
        btst #1,5(a4)
        beq.s .planes_ready
        move.w #$4200,d4
.planes_ready:
        move.w d4,$100(a6)''')
    text = text.replace('        jsr sync_beam', '''        move.l #$1a000,$e8(a6)
        move.l #$1b000,$ec(a6)
        lea $1a000,a0
        move.w #4095,d0
.zero_extra_planes:
        clr.w (a0)+
        dbra d0,.zero_extra_planes
        jsr sync_beam''')
    p.write_text(text)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=110, variants='bit1 four planes; bit3 DMA off; bits4/5 BPL1/2 data',
                            thresholds=list(poll.THRESHOLDS), selected_delays=list(DELAYS),
                            fields={'12': 'pre-enable beam', '14': 'pre-clear beam',
                                    '18': 'last polling value', '24': 'BPLCON0'},
                            limitations='1024 cases decouple launch phase from data. BPL3/4 zero; '
                            'two/four-plane pressure distinguishes fetch phases equivalent with two planes. '
                            'Only pre-enable input qualifies; all later beams are outputs.'))

"""Kind111: a nonuniform eight-CCK slot pattern distinguishes enable phases."""
import argparse
from pathlib import Path
import shutil

import build_irq_stage_rom as base
import build_dma_enable_phase_rom as phase


def trials():
    return [(111, t, v, p, d, r) for _, t, v, p, d, r in phase.trials()
            if v & 2 and v >> 4 in (0, 3)]


def transform(stage):
    phase.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #110,(a4)', 'cmpi.w #111,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    p.write_text(p.read_text().replace('move.w #$4200,d4', 'move.w #$3200,d4'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=111, variants='bit1 always set: three planes; bit3 DMA off; bits4/5 BPL1/2 data',
                            thresholds=list(phase.poll.THRESHOLDS), selected_delays=list(phase.DELAYS),
                            fields={'12': 'pre-enable beam', '14': 'pre-clear beam',
                                    '18': 'last polling value', '24': 'BPLCON0'},
                            limitations='256 three-plane cases; BPL3 zero. Nonuniform slots3/5/7 '
                            'distinguish counter phases that alias with two or four planes. '
                            'No Copper or blitter; qualify only pre-enable input.'))

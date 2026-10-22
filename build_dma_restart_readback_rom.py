"""Kind114: distinguish a first-read sample error from persistent CPU timing drift."""
import argparse
from pathlib import Path
import shutil

import build_irq_stage_rom as base
import build_dma_master_boundary_rom as master


def trials():
    return [(114, *row[1:]) for row in master.trials()]


def transform(stage):
    master.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #113,(a4)', 'cmpi.w #114,(a4)'))
    observers = []
    for variant in (1, 3):
        text = master.warm.cold.observer(variant)
        text = text.replace('        move.w 6(a6),d4', '''        move.w 6(a6),d4
        move.w 6(a6),d5
        move.w 6(a6),d6''')
        text = text.replace('        move.w d4,24(a4)', '''        move.w d4,24(a4)
        move.w d5,14(a4)
        move.w d6,18(a4)''')
        observers.append(text)
    (stage / 'src/rom/blitter_handoff_observer.i').write_text(''.join(observers))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=114, variants='1 inert write;3 COPJMP; master DMA pre-enabled',
                            fields={'12': 'pre-enable beam', '24': 'first post-write read',
                                    '14': 'second read', '18': 'third read',
                                    '16': 'INTREQR completion'},
                            limitations='32 ROM-only cases; three consecutive VHPOSR reads before '
                            'any RAM stores. First-read prefix unchanged from kind113. '
                            'Raw beams, no alignment or packed-value subtraction.'))

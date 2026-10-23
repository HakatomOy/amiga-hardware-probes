"""Kind115: equal-duration ROM NOPs versus a custom write, with cold/warm Copper."""
import argparse
from pathlib import Path
import shutil

import build_irq_stage_rom as base
import build_dma_warm_restart_rom as warm

VARIANTS = (1, 3, 5, 7)


def trials():
    return [(115, 8, variant, phase, 0, repeat)
            for variant in VARIANTS for phase in range(4) for repeat in range(4)]


def transform(stage):
    warm.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #112,(a4)', 'cmpi.w #115,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    p.write_text(p.read_text().replace('moveq #0,d1\n        btst #2,5(a4)',
                                     'move.w #$8200,d1\n        btst #2,5(a4)'))
    observers = []
    for variant in VARIANTS:
        text = warm.cold.observer(variant)
        if variant & 2:
            text = text.replace('        move.w #0,$88(a6)',
                                '        rept 4\n        nop\n        endr')
        observers.append(text)
    (stage / 'src/rom/blitter_handoff_observer.i').write_text(''.join(observers))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=115, variants='bit1 four NOPs instead of COLOR00 write; bit2 warm sleeping Copper',
                            fields={'12': 'pre-enable beam', '24': 'post-actor beam',
                                    '16': 'INTREQR completion bit2'},
                            limitations='64 ROM-only cases; master DMA already high. Four NOPs '
                            'and MOVE.W immediate,d16(An) each take16 uncontended68000 clocks. '
                            'No stores before post-actor sample; no output alignment.'))

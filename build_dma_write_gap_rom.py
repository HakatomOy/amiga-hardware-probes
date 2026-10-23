"""Kind116: separate persistent write delay from immediate write/read handoff."""
import argparse
from pathlib import Path
import shutil

import build_dma_nop_boundary_rom as nop


def trials():
    return [(116, 8, variant | gap << 3, phase, 0, repeat)
            for gap in range(4) for variant in nop.VARIANTS
            for phase in range(4) for repeat in range(4)]


def transform(stage):
    nop.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #115,(a4)', 'cmpi.w #116,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    p.write_text(p.read_text().replace('lsl.l #8,d0', 'lsl.l #7,d0'))
    observers = []
    for gap in range(4):
        for actor in nop.VARIANTS:
            variant = actor | gap << 3
            text = nop.warm.cold.observer(variant)
            text = text.replace(f'${0xffb000 + variant * 0x100:x}',
                                f'${0xffb000 + variant * 0x80:x}')
            if actor & 2:
                text = text.replace('        move.w #0,$88(a6)',
                                    '        rept 4\n        nop\n        endr')
            text = text.replace('        move.w 6(a6),d4',
                                '        nop\n' * gap + '        move.w 6(a6),d4')
            observers.append(text)
    (stage / 'src/rom/blitter_handoff_observer.i').write_text(''.join(observers))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    nop.base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
                   profile=dict(kind=116,
                                variants='bit1 four-NOP actor; bit2 warm Copper; bits3:4 trailing NOP count',
                                fields={'12': 'pre-enable beam', '24': 'post-gap beam',
                                        '16': 'INTREQR completion bit2'},
                                limitations='256 ROM-only cases; master DMA pre-enabled. '
                                '0..3 NOPs after actor, each4 CPU clocks. '
                                'No RAM stores before post-gap sample; exact input cohorts.'))

"""Kind113: master DMA already enabled, Copper still cold at the measured write."""
import argparse
from pathlib import Path
import shutil

import build_irq_stage_rom as base
import build_dma_warm_restart_rom as warm


def trials():
    return [(113, 8, variant, phase, 0, repeat)
            for variant in (1, 3) for phase in range(4) for repeat in range(4)]


def transform(stage):
    warm.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #112,(a4)', 'cmpi.w #113,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    text = p.read_text()
    start = text.index('        moveq #0,d1\n        btst #2,5(a4)')
    end = text.index('        jsr sync_beam', start)
    text = text[:start] + '        move.w #$8200,d1\n' + text[end:]
    p.write_text(text)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=113, variants='1 inert write;3 COPJMP; master DMA already enabled at line40',
                            fields={'12': 'pre-enable beam', '24': 'post-write beam',
                                    '16': 'INTREQR completion bit2'},
                            limitations='32 ROM-only cases distinguish DMAEN rise from COPEN rise. '
                            'Only the pre-enable marker qualifies; no output alignment.'))

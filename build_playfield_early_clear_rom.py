"""Kind101 matrix with clear safely before DDF, retaining the original late-clear probe."""
import argparse
from pathlib import Path
import shutil

import build_irq_stage_rom as base
import build_playfield_modes_rom as modes


def transform(stage):
    modes.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/blitter_handoff_observer.i'
    text = p.read_text()
    assert text.count('cmpi.w #$4420,d0') == 1
    p.write_text(text.replace('cmpi.w #$4420,d0', 'cmpi.w #$4400,d0'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=modes.trials(), transform=transform,
               profile=dict(kind=101, variants='Paired DPF and sprite0, mask/pixel matrix as original kind101',
                            fields={'12': 'input', '14': 'pre-clear beam', '20': 'CLXDAT bits0/1/5',
                                    '22': 'second CLXDAT', '24': 'BPLCON0', '36': 'CLXCON'},
                            limitations='Clear threshold4400 before DDF/trigger rather than original4420. '
                            'Original strict late-clear contract remains separate and unchanged. '
                            'No Copper/blitter/sprite DMA; no alignment.'))

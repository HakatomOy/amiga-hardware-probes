"""PR810: expose adjacent zero-latch underflows through PB pulse width."""
import argparse
from pathlib import Path
import shutil
import build_cia_zero_autostart_rom as zero
import build_irq_stage_rom as base


def trials():
    return [(128,) + row[1:] for row in zero.trials()]


def transform(stage):
    shutil.copyfile(__file__, stage / Path(__file__).name)
    shutil.copyfile(zero.__file__, stage / Path(zero.__file__).name)
    kernel = zero.kernel()
    kernel = kernel.replace('.selected:\n', '.selected:\n        lea $100(a0),a3\n        move.w 4(a4),d4\n', 1)
    kernel = kernel.replace('move.b #8,(a1)', 'move.b #10,(a1)')
    old = '        move.b (a1),d0\n        move.w d0,20(a4)'
    new = '        move.b (a3),d0\n        lsr.w d4,d0\n        andi.w #64,d0\n        move.w d0,20(a4)'
    assert kernel.count(old) == 8
    kernel = kernel.replace(old, new)
    p = stage / 'src/rom/experiment.asm'
    text = p.read_text().replace('cmpi.w #56,(a4)', 'cmpi.w #128,(a4)')
    text = text.replace('jsr irq_stage_trial', 'jsr cia_zero_review_trial')
    p.write_text(text + '\n' + kernel)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=128, targets=['CIA-A', 'CIA-B'], sources=None,
                            masks=None, masked_fields=None,
                            variants='0=TA PB6;1=TB PB7;phase=latch;delay=NOP count',
                            fields={'20': 'sampled PB6/PB7 shifted to bit6',
                                    '22': 'next CRA/CRB', '34': 'settled CRA/CRB',
                                    '12': 'pre-write beam', '14': 'post-PB-read beam'},
                            limitations='PBON pulse mode, high-byte auto-start. Adjacent underflows merge into pulse width; first PB sample precedes bit normalization.'))

"""Kind123: paired immediate/register enable with matched read/write operands."""
import argparse
from pathlib import Path
import shutil

import build_custom_read_return_rom as base


def trials():
    return [(123, row[1], row[2] | form << 5, *row[3:])
            for form in range(2) for row in base.trials()]


VARIANTS = sorted({row[2] for row in trials()})
STRIDE = 0x64


def observer(variant):
    original = variant & 31
    slot = VARIANTS.index(variant)
    text = base.observer(original)
    text = text.replace(f'${0xffb000 + original * 0x80:x}-*',
                        f'${0xffb000 + slot * STRIDE:x}-*')
    text = text.replace(f'custom_return_{original}:', f'custom_return_forms_{variant}:')
    if variant & 32:
        text = text.replace('move.w d1,$96(a6)',
                            f'move.w #${0x8380 if variant & 1 else 0x8300:x},$96(a6)')
    return text


def transform(stage):
    base.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #122,(a4)', 'cmpi.w #123,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    text = p.read_text()
    anchor = '        lsl.l #7,d0\n        addi.l #$ffb000,d0\n        movea.l d0,a3'
    assert text.count(anchor) == 1
    text = text.replace(anchor, '''        lsl.w #2,d0
        lea custom_return_observers(pc),a3
        movea.l 0(a3,d0.w),a3''')
    addresses = {v: 0xffb000 + slot * STRIDE for slot, v in enumerate(VARIANTS)}
    text += '\ncustom_return_observers:\n'
    text += ''.join(f'        dc.l ${addresses.get(v, 0):x}\n' for v in range(max(VARIANTS) + 1))
    p.write_text(text)
    (stage / 'src/rom/blitter_handoff_observer.i').write_text(''.join(observer(v) for v in VARIANTS))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.cold.base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
                         profile=dict(kind=123, targets=base.TARGETS,
                                      variants='bit0 cold Copper; bits1:3 operand target; bit4 NOP gap; bit5 immediate DMACON',
                                      fields={'12': 'input beam', '20': 'raw operand', '24': 'operand echo by common return',
                                              '36': 'first following beam by common return', '18': 'second following beam',
                                              '34': 'plane activity bit0', '16': 'Copper completion bit3'},
                                      limitations='320 ROM-only cases. Both gate forms within same ROM. '
                                      'Read/write operands are matched12-clock MOVE.W forms. '
                                      'Compare outputs36/18, not overwritten operand echo24. '
                                      'Raw DMACONR BZERO flag is separate from timing inference.'))

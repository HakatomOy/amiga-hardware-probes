"""Keep original cases, then distinguish custom-register and RAM write ports."""
import argparse
from pathlib import Path
import shutil

import build_dma_master_boundary_rom as master

TARGETS = (('COLOR00', '$180(a6)', 0), ('INTREQ', '$9c(a6)', 0),
           ('DMACON', '$96(a6)', 0), ('COPCON', '$2e(a6)', 0),
           ('NOOP', '$1fe(a6)', 0), ('RAM_ZERO', '0(a1)', 0),
           ('RAM_PATTERN', '0(a1)', 0x5555))
CONTROLS = tuple(16 + (target << 2) + copper for target in range(len(TARGETS)) for copper in range(2))


def trials():
    return master.trials() + [(113, 8, variant, phase, 0, repeat)
                              for variant in CONTROLS for phase in range(4) for repeat in range(4)]


def observer(variant):
    target = (variant - 16) >> 2
    _, operand, value = TARGETS[target]
    original = variant & 1
    text = master.warm.cold.observer(original)
    text = text.replace(f'${0xffb000 + original * 0x100:x}-*',
                        f'${0xffb800 + CONTROLS.index(variant) * 0x80:x}-*')
    text = text.replace(f'restart_boundary_{original}:', f'write_target_{variant}:')
    text = text.replace('move.w #0,$180(a6)', f'move.w #${value:x},{operand}', 1)
    if target >= 5:
        text = text.replace('        move.w d3,12(a4)',
                            '        move.w (a1),20(a4)\n        move.w d3,12(a4)', 1)
    return text


def transform(stage):
    master.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    text = p.read_text()
    anchor = '        lsl.l #8,d0\n        addi.l #$ffb000,d0\n        movea.l d0,a3'
    assert text.count(anchor) == 1
    text = text.replace(anchor, '''        lsl.w #2,d0
        lea write_target_observers(pc),a3
        movea.l 0(a3,d0.w),a3''')
    text = text.replace('        jsr sync_beam', '        lea $1a000,a1\n        jsr sync_beam', 1)
    addresses = {1: 0xffb100, 3: 0xffb300}
    addresses.update({v: 0xffb800 + slot * 0x80 for slot, v in enumerate(CONTROLS)})
    text += '\nwrite_target_observers:\n'
    text += ''.join(f'        dc.l ${addresses.get(v, 0):x}\n' for v in range(max(CONTROLS) + 1))
    p.write_text(text)
    p = stage / 'src/rom/blitter_handoff_observer.i'
    p.write_text(p.read_text() + ''.join(observer(v) for v in CONTROLS))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    master.base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
                      profile=dict(kind=113, targets=[t[0] for t in TARGETS],
                                   variants='Original1/3 first; controls16+(target<<2)+COPEN',
                                   fields={'12': 'input beam', '24': 'post-write beam',
                                           '16': 'Copper completion bit2', '20': 'RAM write readback for RAM targets'},
                                   limitations='256 cases; original first32 descriptors/order/result slots retained. '
                                   'Five no-change custom-register writes and two RAM patterns, all immediate '
                                   'd16(An)16-clock forms. Scratch1a000 outside source/results/code. '
                                   'Control bit1 held0; original ROM observers/alignment unchanged.'))

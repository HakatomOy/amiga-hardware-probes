"""Keep original32 cases first, then pair equal-duration COLOR00 actor forms."""
import argparse
from pathlib import Path
import shutil

import build_dma_master_boundary_rom as master

CONTROLS = tuple(16 + (actor << 2) + copper for actor in range(4) for copper in range(2))


def trials():
    return master.trials() + [(113, 8, variant, phase, 0, repeat)
                              for variant in CONTROLS for phase in range(4) for repeat in range(4)]


def observer(variant):
    actor = (variant - 16) >> 2
    slot = CONTROLS.index(variant)
    original = variant & 1
    text = master.warm.cold.observer(original)
    text = text.replace(f'${0xffb000 + original * 0x100:x}-*', f'${0xffb800 + slot * 0x80:x}-*')
    text = text.replace(f'restart_boundary_{original}:', f'actor_form_{variant}:')
    operations = ('move.w #0,$180(a6)', 'move.w d2,$180(a6)\n        nop',
                  'nop\n        move.w d2,$180(a6)', 'nop\n        nop\n        nop\n        nop')
    return text.replace('move.w #0,$180(a6)', operations[actor], 1)


def transform(stage):
    master.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    text = p.read_text()
    anchor = '        lsl.l #8,d0\n        addi.l #$ffb000,d0\n        movea.l d0,a3'
    assert text.count(anchor) == 1
    text = text.replace(anchor, '''        lsl.w #2,d0
        lea actor_form_observers(pc),a3
        movea.l 0(a3,d0.w),a3''')
    text = text.replace('        jsr sync_beam', '        moveq #0,d2\n        jsr sync_beam', 1)
    addresses = {1: 0xffb100, 3: 0xffb300}
    addresses.update({v: 0xffb800 + slot * 0x80 for slot, v in enumerate(CONTROLS)})
    text += '\nactor_form_observers:\n'
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
                      profile=dict(kind=113,
                                   variants='Original1/3 first; controls16+(actor<<2)+COPEN. Actor0 immediate,1 register+NOP,2 NOP+register,3 fourNOPs',
                                   fields={'12': 'input beam', '24': 'post-actor beam', '16': 'Copper completion bit2'},
                                   limitations='160 cases; original first32 descriptors/order/record slots retained. '
                                   'Original fixed-ROM observers and alignment unchanged; prealignment dispatch changes. '
                                   'All control actors16 CPU clocks; bit1 held clear in controls to decouple manual sprite setup.'))

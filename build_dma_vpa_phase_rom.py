"""Kind124: VPA/E-clock synchronization versus ROM delay before original observer."""
import argparse
from pathlib import Path
import shutil

import build_dma_master_boundary_rom as master


def trials():
    return [(124, 8, variant, phase, 0, repeat)
            for variant in range(16) for phase in range(4) for repeat in range(2)]


def observer(variant):
    text = master.warm.cold.observer(variant)
    text = text.replace(f'${0xffb000 + variant * 0x100:x}-*',
                        f'${0xffb000 + variant * 0x80:x}-*')
    text = text.replace('restart_boundary_', 'vpa_phase_')
    # All paths retain the original immediate-enable/inert-or-COPJMP sequence.
    text = text.replace('move.w #$8300,$96(a6)', 'move.w #$8380,$96(a6)')
    prefix = ('        move.b $bfe001,d0\n' if variant & 1 else '        nop\n' * 6)
    prefix += '        nop\n' * (variant >> 2)
    return text.replace('        move.w 6(a6),d3', prefix + '        move.w 6(a6),d3', 1)


def transform(stage):
    master.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #113,(a4)', 'cmpi.w #124,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    p.write_text(p.read_text().replace('lsl.l #8,d0', 'lsl.l #7,d0'))
    (stage / 'src/rom/blitter_handoff_observer.i').write_text(''.join(observer(v) for v in range(16)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    master.base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
                      profile=dict(kind=124,
                                   variants='bit0 CIA-A PRA byte read versus6 NOPs; bit1 COPJMP versus inert; bits2:3 extra NOPs',
                                   fields={'12': 'input after prefix', '24': 'original post-write beam',
                                           '16': 'finite Copper completion bit2'},
                                   limitations='128 ROM-only cases. Original post-input immediate enable/actor '
                                   'sequence unchanged. CIA read attempts VPA/E synchronization; ROM-delay '
                                   'control is24 CPU clocks plus same0..3 extra NOPs. '
                                   'This tests phase control, not an assumed Amiga phase guarantee.'))

"""Kind97: pair identical initial COPER writes with short/padded Copper tails."""
import argparse
from pathlib import Path
import shutil

import build_copper_enable_boundary_rom as boundary
import build_irq_stage_rom as base


def trials():
    return [(97,) + row[1:] for row in boundary.trials()]


def transform(stage):
    boundary.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    path = stage / 'src/rom/experiment.asm'
    text = path.read_text()
    assert text.count('cmpi.w #96,(a4)') == 1
    path.write_text(text.replace('cmpi.w #96,(a4)', 'cmpi.w #97,(a4)'))
    path = stage / 'src/rom/blitter_handoff_kernel.i'
    text = path.read_text()
    anchor = '        move.w #$fffe,$6006\n'
    assert text.count(anchor) == 1
    text = text.replace(anchor, anchor + '''        btst #5,4(a4)           ; variant bit13: three NOOPs before WAIT
        beq.s .enable_tail_ready
        move.w #$01fe,$6004
        clr.w $6006
        move.w #$01fe,$6008
        clr.w $600a
        move.w #$01fe,$600c
        clr.w $600e
        move.w #$ffff,$6010
        move.w #$fffe,$6012
.enable_tail_ready:
''')
    anchor = '''        btst #5,4(a4)           ; variant bit13, high byte bit5
        beq.s .enable_seed_ready
'''
    assert text.count(anchor) == 1
    # Both active tails start from the same explicitly pending restart.
    text = text.replace(anchor, '')
    path.write_text(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm', required=True)
    parser.add_argument('--wsl', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    base.build(args.vasm, args.wsl, args.out, rows=trials(), transform=transform,
               profile=dict(kind=97,
                            hypothesis='Finite-stream WAIT tail releases CPU/RGA early, separately from initial fetch timing.',
                            competitor='Initial COPEN/first-word timing causes the same mismatch irrespective of tail length.',
                            variants='bits9:8 off/WAIT/active; bit12 RAM venue; bit13 three NOOPs before final WAIT',
                            fields={'12': 'common ROM input', '18': 'prefix-complete beam',
                                    '16': 'VHPOSR result', '20': 'post-early-IRQ beam',
                                    '22': 'early INTREQ', '28': 'settled INTREQ', '30': 'settled beam'},
                            limitations='Same observer opcodes and first COPER MOVE for both tails. Active mode always seeds a disabled restart before alignment. No blitter or measured COPJMP; exact observations without alignment.'))

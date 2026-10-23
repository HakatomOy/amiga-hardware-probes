"""Kind120: CPU overwrite versus the second word of an initial Copper WAIT."""
import argparse
from pathlib import Path
import shutil

import build_copper_cold_fetch_race_rom as first


def trials():
    return [(120, *row[1:]) for row in first.trials()]


def observer(variant):
    text = first.observer(variant)
    text = text.replace('cold_fetch_race_', 'wait_mask_race_')
    text = text.replace('cmpi.w #$4460,d0', 'cmpi.w #$42a0,d0', 1)
    return text.replace('        move.w $1e(a6),d0', '''        move.w $1e(a6),d5
        andi.w #4,d5
        move.w d5,14(a4)
.completion:
        move.w 6(a6),d0
        cmpi.w #$4460,d0
        bcs.s .completion
        move.w $1e(a6),d0''', 1)


def transform(stage):
    first.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #119,(a4)', 'cmpi.w #120,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    text = p.read_text()
    anchor = '        lea $2000,a0\n'
    text = text.replace(anchor, anchor + '        move.w #$4341,(a0)+\n        move.w #$fffe,(a0)+\n', 1)
    text = text.replace('move.w #$0180,$2000', 'move.w #$80fe,$2002')
    text = text.replace('lea $2000,a1', 'lea $2002,a1')
    text = text.replace('move.w #$0180,d2', 'move.w #$80fe,d2')
    p.write_text(text)
    (stage / 'src/rom/blitter_handoff_observer.i').write_text(''.join(observer(v) for v in range(32)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    first.cold.base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
                          profile=dict(kind=120,
                                       variants='bit0 simultaneous BPLEN; bit1 unused-neighbor write; bit2 preseed new mask; bits3:4 NOP gap',
                                       fields={'12': 'input beam', '14': 'early marker bit2 at42:a0',
                                               '16': 'settled completion bits2/3 at44:60',
                                               '20': 'CPU-written word', '24': 'diagnostic post-store beam'},
                                       limitations='256 ROM-only cases. Initial WAIT4341/fffe; '
                                       'CPU changes second word to80fe, ignoring vertical comparison. '
                                       'Early marker distinguishes mask ownership; independent later completion. '
                                       'No beam-output comparison or alignment.'))

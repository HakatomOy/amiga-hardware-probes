"""Kind71: observe status before the first beam read, with longer-blit controls."""
import argparse
from pathlib import Path
import shutil
import build_handoff_sample_rom as sample
import build_irq_stage_rom as base


def trials():
    return [(71, target, v | (n << 5), p, pad, r)
            for target in (3, 4, 5) for n in range(8)
            for v in (0, 1, 2, 3, 8, 9, 10, 11)
            for p in range(2) for pad in (0, 2) for r in range(2)]


def transform(stage):
    sample.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #70,(a4)', 'cmpi.w #71,(a4)'))
    p = stage / 'src/rom/blitter_handoff_observer.i'
    s = p.read_text()
    old = '''        move.w 6(a6),d3
        move.w $02(a6),d0
        move.w 6(a6),d4
        move.w $1e(a6),d1
        move.w 6(a6),d2'''
    new = '''        move.w $02(a6),d0
        move.w 6(a6),d3
        move.w $02(a6),d4
        move.w 6(a6),d1
        move.w $1e(a6),d2
        move.w 6(a6),d6'''
    assert s.count(old) == 8
    s = s.replace(old, new)
    s = s.replace('move.w d4,18(a4)', 'move.w d1,18(a4)')
    s = s.replace('move.w d1,20(a4)', 'move.w d2,20(a4)')
    s = s.replace('move.w d2,22(a4)', 'move.w d6,22(a4)')
    s = s.replace('clr.w 34(a4)', 'move.w d4,34(a4)')
    p.write_text(s)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=71, widths_words=[1, 2, 16],
                            measurement_fields='kind70 except launch_ref/end_ref/icr are beams after status0/status1/request; aux status1',
                            limitations='Status-first observer; post-read beams qualify scheduling but are not electrical edge measurements.'))

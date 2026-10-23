"""Kind117: three consecutive beam reads after the write/NOP gap controls."""
import argparse
from pathlib import Path
import shutil

import build_dma_write_gap_rom as gap


def trials():
    return [(117, *row[1:]) for row in gap.trials()]


def transform(stage):
    gap.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #116,(a4)', 'cmpi.w #117,(a4)'))
    p = stage / 'src/rom/blitter_handoff_observer.i'
    text = p.read_text().replace('        move.w 6(a6),d4',
                               '        move.w 6(a6),d4\n'
                               '        move.w 6(a6),d5\n'
                               '        move.w 6(a6),d6')
    text = text.replace('        move.w d4,24(a4)',
                        '        move.w d4,24(a4)\n'
                        '        move.w d5,14(a4)\n'
                        '        move.w d6,18(a4)')
    p.write_text(text)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    gap.nop.base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
                       profile=dict(kind=117,
                                    variants='bit1 four-NOP actor; bit2 warm Copper; bits3:4 trailing NOP count',
                                    fields={'12': 'pre-enable beam', '24': 'first post-gap read',
                                            '14': 'second read', '18': 'third read',
                                            '16': 'INTREQR completion bit2'},
                                    limitations='256 ROM-only cases; kind116 prefix unchanged. '
                                    'Three consecutive beam reads before RAM stores; exact input cohorts.'))

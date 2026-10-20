"""Kind80: distinguish launch-witness RAM writeback from Copper/blitter ordering."""
import argparse
from pathlib import Path
import shutil

import build_handoff_copper_race_rom as copper
import build_irq_stage_rom as base


def trials():
    return [(80, t, v | address | (n << 5) | witness, 0, 0, r)
            for t in (0, 3, 6) for n in range(4)
            for v in (4, 5, 6, 7, 12, 13, 14, 15)
            for address in (0, 16) for witness in (0, 128) for r in range(2)]


def transform(stage):
    copper.transform(stage)
    shutil.copyfile(__file__, stage/Path(__file__).name)
    path = stage/'src/rom/experiment.asm'
    text = path.read_text()
    assert text.count('cmpi.w #78,(a4)') == 1
    path.write_text(text.replace('cmpi.w #78,(a4)', 'cmpi.w #80,(a4)'))
    path = stage/'src/rom/blitter_handoff_observer.i'
    text = path.read_text()
    # Existing bits7:5 dispatch eight fixed observer banks. The upper four
    # now implement the same NOP0..3 with a register-only launch witness.
    for n in range(4, 8):
        head, body = text.split(f'sample_{n}:', 1)
        if n < 7:
            body, tail = body.split(f'        dcb.b ${0xffb000+(n+1)*0x200:06x}-*,0', 1)
            tail = f'        dcb.b ${0xffb000+(n+1)*0x200:06x}-*,0'+tail
        else:
            tail = ''
        body = body.replace(f'        rept {n}\n', f'        rept {n-4}\n')
        body = body.replace('move.w 6(a6),12(a4)', 'move.w 6(a6),d2')
        body = body.replace('        move.w 6(a6),d3\n',
                            '        move.w 6(a6),d3\n        move.w d2,12(a4)\n')
        text = head+f'sample_{n}:'+body+tail
    path.write_text(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm', required=True)
    parser.add_argument('--wsl', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    base.build(args.vasm, args.wsl, args.out, rows=trials(), transform=transform,
        profile=dict(kind=80, targets=['D-only', 'AD old aaaa', 'AD preseeded5555'],
                     sources=['CPU BLTSIZE or inert write'], masks=None, masked_fields=None,
                     variants='kind78;bits6:5 NOP0..3;bit7 launch beam held in D2 until after first post-overwrite beam instead of immediate RAM writeback',
                     measurement_fields='kind78; bit7 changes witness storage timing deliberately; do not compare different observer modes as equivalent cohorts',
                     limitations='Phase0,pad0 smaller reproducer; launch beam is a software sample,not a BLTSIZE pin edge. No alignment.'))

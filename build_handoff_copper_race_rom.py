"""Kind78: source-write race under a witnessed, finite Copper burst."""
import argparse
from pathlib import Path
import shutil

import build_handoff_race_rom as race
import build_irq_stage_rom as base


def trials():
    return [(78, t, v | address | (n << 5), p, pad, r)
            for t in (0, 3, 6) for n in range(4)
            for v in (4, 5, 6, 7, 12, 13, 14, 15) for address in (0, 16)
            for p in range(2) for pad in (0, 1) for r in range(2)]


def transform(stage):
    race.transform(stage)
    shutil.copyfile(__file__, stage/Path(__file__).name)
    path = stage/'src/rom/experiment.asm'
    text = path.read_text()
    assert text.count('cmpi.w #77,(a4)') == 1
    path.write_text(text.replace('cmpi.w #77,(a4)', 'cmpi.w #78,(a4)'))
    path = stage/'src/rom/blitter_handoff_kernel.i'
    text = path.read_text()
    anchor = '        move.w #$ffff,(a1)+\n        move.w #$fffe,(a1)+'
    assert text.count(anchor) == 1
    text = text.replace(anchor, '''        move.w #$009c,(a1)+           ; completed finite burst witness
        move.w #$8010,(a1)+           ; COPER, CPU interrupts remain masked
'''+anchor)
    path.write_text(text)
    path = stage/'src/rom/blitter_handoff_observer.i'
    text = path.read_text()
    anchor = '        move.w #$5555,d0\n        move.w 6(a6),12(a4)'
    assert text.count(anchor) == 8
    text = text.replace(anchor, '''        move.w 4(a4),d0
        andi.w #6,d0
        cmpi.w #6,d0
        bne.s .no_copper
        move.w #0,$88(a6)
        move.w #$8080,$96(a6)         ; explicitly enable prepared Copper burst
.no_copper:
'''+anchor)
    path.write_text(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm', required=True)
    parser.add_argument('--wsl', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    base.build(args.vasm, args.wsl, args.out, rows=trials(), transform=transform,
        profile=dict(kind=78, targets=['D-only', 'AD old aaaa', 'AD preseeded5555'],
                     variants='kind77 plus DMA mode3=six planes + finite Copper burst',
                     copper='32 NOOPs then INTREQ COPER then terminator; COPEN and COPJMP before launch beam; settled bit4 witnesses completion',
                     measurement_fields='kind77; settled INTREQ additionally observes COPER',
                     limitations='Software ordering witnesses, not electrical edges; exact launch cohorts; no alignment.'))

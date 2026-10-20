"""Kind79: identical CPU read opcode across four spaces under witnessed Copper."""
import argparse
from pathlib import Path
import shutil

import build_handoff_access_rom as access
import build_irq_stage_rom as base


def trials():
    return [(79, t, v | (n << 5), p, pad, r)
            for t in (3, 6, 9, 12) for n in range(4)
            for v in (4, 5, 6, 7, 12, 13, 14, 15)
            for p in range(2) for pad in (0, 2) for r in range(2)]


def transform(stage):
    access.transform(stage)
    shutil.copyfile(__file__, stage/Path(__file__).name)
    path = stage/'src/rom/experiment.asm'
    text = path.read_text()
    assert text.count('cmpi.w #74,(a4)') == 1
    path.write_text(text.replace('cmpi.w #74,(a4)', 'cmpi.w #79,(a4)'))
    path = stage/'src/rom/blitter_handoff_kernel.i'
    text = path.read_text()
    anchor = '        move.w #$ffff,(a1)+\n        move.w #$fffe,(a1)+'
    assert text.count(anchor) == 1
    path.write_text(text.replace(anchor, '''        move.w #$009c,(a1)+
        move.w #$8010,(a1)+           ; finite burst completion witness
'''+anchor))
    path = stage/'src/rom/blitter_handoff_observer.i'
    text = path.read_text()
    anchor = '        move.w 6(a6),12(a4)'
    assert text.count(anchor) == 8
    path.write_text(text.replace(anchor, '''        move.w 4(a4),d0
        andi.w #6,d0
        cmpi.w #6,d0
        bne.s .no_copper
        move.w #0,$88(a6)
        move.w #$8080,$96(a6)
.no_copper:
'''+anchor))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm', required=True)
    parser.add_argument('--wsl', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    base.build(args.vasm, args.wsl, args.out, rows=trials(), transform=transform,
        profile=dict(kind=79, targets=['3 custom', '6 chip', '9 slow', '12 ROM'],
                     sources=['CPU AD BLTSIZE or inert write'], masks=None, masked_fields=None,
                     variants='six planes vs six planes plus32-NOOP finite Copper; bit0 nasty; bit3 no-start; bits6:5 post-start NOP0..3',
                     measurement_fields='kind74; settled INTREQ COPER witnesses finite Copper completion',
                     limitations='Exact launch cohorts; software observation clocks, not pin timestamps; no alignment.'))

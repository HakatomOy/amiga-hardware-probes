"""Kind73: distinguish lost pointer writes from early collision visibility."""
import argparse
from pathlib import Path
import shutil
import build_copper_dma_collision_rom as collision
import build_irq_stage_rom as base


def trials():
    return [(73, target, control+4*writer, h, 0, repeat)
            for target in (1, 2, 3) for writer in (0, 1) for control in range(4)
            for h in (range(17) if control in (0, 3) else (0, 8, 16))
            for repeat in range(2)]


def transform(stage):
    collision.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage/'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #72,(a4)', 'cmpi.w #73,(a4)'))
    p = stage/'src/rom/blitter_handoff_kernel.i'
    s = p.read_text().replace('        clr.w $108(a6)', '        clr.w $102(a6)\n        clr.w $108(a6)')
    s = s.replace('        dbra d0,.fill\n', '''        dbra d0,.fill
        lea $5a000,a0
        move.w #511,d0
.fill_high:
        move.w d1,(a0)+
        dbra d0,.fill_high
''')
    s = s.replace('.register_ready:\n', '''.register_ready:
        cmpi.w #2,2(a4)
        bne.s .not_high
        move.w #$00e4,d4
        move.w #5,d5
.not_high:
        cmpi.w #3,2(a4)
        bne.s .selected_plane
        move.l #$1a000,$e0(a6)
        move.l #$18000,$e4(a6)
        move.w #$00e2,d4
        move.w #$9000,d5
.selected_plane:
''')
    s = s.replace('        move.w #$8380,d6\n        move.l #$19000,$e4(a6)',
                  '        move.w #$8380,d6\n        move.l #$19000,$e0(a6)\n        move.l #$19000,$e4(a6)')
    anchor = '        move.w $0e(a6),22(a4)\n'
    assert anchor in s
    s = s.replace(anchor, anchor + '''.settled_line:
        move.w 6(a6),d0
        cmpi.w #$4420,d0
        bcs.s .settled_line
        move.w 6(a6),28(a4)
        move.w $0e(a6),16(a4)
        move.w 6(a6),30(a4)
''')
    p.write_text(s)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=73, targets=['BPL2PTL', 'BPL2PTH', 'BPL1PTL'],
                            measurement_fields='kind72 plus end_beam settled CLXDAT after the following full line; saved_pc_offset brackets that read',
                            limitations='Settled pixel witness distinguishes accepted/lost retargeting; exact transfer-slot attribution still needs validated scheduling.'))

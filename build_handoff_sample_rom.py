"""Kind70: single bracketed BBUSY read, independent of polling outcomes."""
import argparse
from pathlib import Path
import shutil
import build_handoff_stride_rom as stride
import build_irq_stage_rom as base


def trials():
    return [(70, 3, v | (n << 5), p, pad, r) for n in range(8)
            for v in (0, 1, 2, 3, 8, 9, 10, 11)
            for p in range(2) for pad in range(4) for r in range(2)]


def transform(stage):
    stride.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #67,(a4)', 'cmpi.w #70,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    s = p.read_text()
    s = s.replace('.observers: dc.l $ffb000,$ffb400,$ffb800,$ffbc00',
                  '.observers: dc.l ' + ','.join(f'${0xffb000+0x200*n:06x}' for n in range(8)))
    p.write_text(s)
    blocks = []
    for n in range(8):
        blocks.append(f'''        dcb.b ${0xffb000+0x200*n:06x}-*,0
sample_{n}:
        move.w 6(a6),12(a4)
        move.w d5,(a2)
        rept {n}
        nop
        endr
        move.w 6(a6),d3
        move.w $02(a6),d0
        move.w 6(a6),d4
        move.w $1e(a6),d1
        move.w 6(a6),d2
        move.w d3,14(a4)
        move.w d0,16(a4)
        move.w d4,18(a4)
        move.w d1,20(a4)
        move.w d2,22(a4)
        rept 128
        nop
        endr
        move.w $10000,24(a4)
        move.w (a0),26(a4)
        move.w $1e(a6),28(a4)
        move.w 6(a6),30(a4)
        clr.w 32(a4)
        clr.w 34(a4)
        rts
''')
    (stage/'src/rom/blitter_handoff_observer.i').write_text('\n'.join(blocks))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=70, variants='low bits priority/DMA/no-start; bits7:5 zero to seven ROM NOPs after start',
                            measurement_fields='launch_beam launch; launch_ref pre-status beam; end_beam DMACONR; end_ref post-status beam; counter INTREQ; icr post-request beam; irq_beam/irq_level final D; saved_pc_offset settled INTREQ:beam',
                            limitations='Single software read, not an electrical edge. Compare launch-only timing and separately exact read-bracket register values.'))

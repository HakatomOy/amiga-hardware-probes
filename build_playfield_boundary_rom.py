"""Kind103: bracket destructive PF-PF reads while moving DDF and DIW independently."""
import argparse
from pathlib import Path
import shutil

import build_irq_stage_rom as base
import build_playfield_modes_rom as modes


def trials():
    return [(103, target, variant, pixel, delay, repeat)
            for target in (4, 15) for pixel in (0, 3)
            for variant in (0, 1, 2, 4) for delay in range(24)
            for repeat in range(2)]


def observer():
    text = '''        dcb.b $ffb000-*,0
playfield_boundary:
        move.w 6(a6),d3
        move.w #$8300,$96(a6)
        move.w 8(a4),d0
        add.w d0,d0
        lea .table(pc),a0
        move.w (a0,d0.w),d0
        jmp (a0,d0.w)
.table:
'''
    text += ''.join(f'        dc.w .sample{i}-.table\n' for i in range(24))
    for i in range(24):
        text += f'''.sample{i}:
.wait{i}:
        move.w 6(a6),d0
        cmpi.w #${0x4400 + i * 2:04x},d0
        bcs.s .wait{i}
        move.w 6(a6),14(a4)
        tst.w $0e(a6)
        move.w 6(a6),16(a4)
        move.w 6(a6),26(a4)
        move.w $0e(a6),d0
        move.w 6(a6),34(a4)
        move.w d0,20(a4)
        move.w $0e(a6),22(a4)
        move.w #$7fff,$96(a6)
        clr.w 32(a4)
        rts
'''
    return text


def transform(stage):
    modes.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #101,(a4)', 'cmpi.w #103,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    text = p.read_text().replace('        move.w d4,24(a4)\n', '')
    text = text.replace('        move.w d5,36(a4)\n', '')
    anchor = '        clr.w $102(a6)\n'
    text = text.replace(anchor, '''        btst #1,5(a4)
        beq.s .ddf_ready
        move.w #$0040,$92(a6)
.ddf_ready:
        btst #2,5(a4)
        beq.s .diw_ready
        move.w #$2c91,$8e(a6)
.diw_ready:
''' + anchor)
    p.write_text(text)
    (stage / 'src/rom/blitter_handoff_observer.i').write_text(observer())


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=103, variants='0 base;1 DPF;2 DDF+8CCK;4 DIW+16 lores pixels',
                            fields={'12': 'input', '14': 'pre-clear beam',
                                    '16': 'post-clear beam', '26': 'pre-read beam',
                                    '34': 'post-read beam', '20': 'CLXDAT', '22': 'second CLXDAT'},
                            limitations='Raw VHPOSR brackets, not electrical timestamps; no alignment. '
                            'CLXCON0040/C3, plane pixel0/3, no sprites/Copper/blitter. '
                            'Sweep thresholds4400..442e; two repeats.'))

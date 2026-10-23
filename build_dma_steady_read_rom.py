"""Kind118: steady two-plane DMA, no Copper, consecutive CPU beam reads."""
import argparse
from pathlib import Path
import shutil

import build_dma_warm_restart_rom as warm


def trials():
    return [(118, 15, variant, phase, 0, repeat)
            for variant in range(8) for phase in range(4) for repeat in range(4)]


def observer(variant):
    return f'''        dcb.b ${0xffb000 + variant * 0x80:x}-*,0
steady_read_{variant}:
        move.w 6(a6),d3
''' + '        nop\n' * (variant >> 1) + '''        move.w 6(a6),d4
        move.w 6(a6),d5
        move.w 6(a6),d6
.wait:
        move.w 6(a6),d0
        cmpi.w #$4460,d0
        bcs.s .wait
        move.w $0e(a6),d0
        andi.w #1,d0
        move.w d0,16(a4)
        move.w d3,12(a4)
        move.w d4,24(a4)
        move.w d5,14(a4)
        move.w d6,18(a4)
        move.w #$7fff,$96(a6)
        clr.w 32(a4)
        rts
'''


def transform(stage):
    warm.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #112,(a4)', 'cmpi.w #118,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    text = p.read_text().replace('lsl.l #8,d0', 'lsl.l #7,d0')
    text = text.replace('#$2c81,$8e(a6)', '#$2081,$8e(a6)')
    text = text.replace('move.w #$2200,$100(a6)', 'move.w #$2600,$100(a6)')
    text = text.replace('.plane2_ready:\n', '.plane2_ready:\n        moveq #-1,d1\n        moveq #-1,d2\n')
    text = text.replace('moveq #0,d1\n        btst #2,5(a4)',
                        'move.w #$8200,d1\n        btst #0,5(a4)')
    text = text.replace('move.w #$8280,d1', 'move.w #$8300,d1')
    text = text.replace('        jsr sync_beam', '        tst.w $0e(a6)\n        jsr sync_beam')
    p.write_text(text)
    (stage / 'src/rom/blitter_handoff_observer.i').write_text(''.join(observer(v) for v in range(8)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    warm.base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
                    profile=dict(kind=118,
                                 variants='bit0 steady bitplane DMA; bits1:2 ROM NOP gap',
                                 fields={'12': 'input beam', '24': 'first read', '14': 'second read',
                                         '18': 'third read', '16': 'PF1/PF2 activity bit0'},
                                 limitations='128 ROM-only cases; DMA enabled atline40, Copper always disabled. '
                                 'Two all-one planes, dual playfield, both enabled bits match one; '
                                 'CLXDAT bit0 witnesses fetch activity after critical reads. '
                                 'Three beam reads before RAM stores; no output alignment.'))

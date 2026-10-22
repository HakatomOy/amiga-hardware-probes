"""Kind104: finite Copper gates isolate collision windows from CPU read timing."""
import argparse
from pathlib import Path
import shutil

import build_irq_stage_rom as base
import build_playfield_boundary_rom as boundary


def trials():
    return [(104, target | (closing << 4), variant, pixel, delay, repeat)
            for target in (4, 15) for closing in range(2) for pixel in (0, 3)
            for variant in (0, 1, 2, 4) for delay in range(16)
            for repeat in range(2)]


OBSERVER = '''        dcb.b $ffb000-*,0
playfield_gate:
        move.w 6(a6),d3
        tst.w $0e(a6)
        move.w #$8380,$96(a6)
.wait:
        move.w 6(a6),d0
        cmpi.w #$4480,d0
        bcs.s .wait
        move.w 6(a6),26(a4)
        move.w $0e(a6),d0
        move.w 6(a6),34(a4)
        move.w d0,20(a4)
        move.w $1e(a6),16(a4)
        move.w $0e(a6),22(a4)
        move.w #$7fff,$96(a6)
        clr.w 32(a4)
        rts
'''


def transform(stage):
    boundary.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #103,(a4)', 'cmpi.w #104,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    text = p.read_text().replace('        move.w 2(a4),d5\n',
                               '        move.w 2(a4),d5\n        andi.w #15,d5\n')
    text = text.replace('        move.w 2(a4),d0\n',
                        '        move.w 2(a4),d0\n        andi.w #15,d0\n', 1)
    # Plane6 must be one outside the gate; this two-plane stream cannot
    # satisfy that condition. No CLXDAT read occurs during the gated interval.
    text = text.replace('        move.w d5,$98(a6)\n', '        move.w #$0820,$98(a6)\n')
    text = text.replace('        jsr sync_beam\n', '''        lea $2000,a0
        move.w 8(a4),d0
        add.w d0,d0
        addi.w #$4431,d0
        move.w #$4421,d1
        move.w #$4471,d2
        btst #4,3(a4)
        beq.s .opening_gate
        move.w d0,d2
        bra.s .gate_ready
.opening_gate:
        move.w d0,d1
.gate_ready:
        move.w d1,(a0)+
        move.w #$fffe,(a0)+
        move.w #$0098,(a0)+
        move.w d5,(a0)+
        move.w d2,(a0)+
        move.w #$fffe,(a0)+
        move.w #$0098,(a0)+
        move.w #$0820,(a0)+
        move.w #$009c,(a0)+
        move.w #$8004,(a0)+
        move.w #$ffff,(a0)+
        move.w #$fffe,(a0)+
        move.l #$2000,$80(a6)
        move.w #0,$88(a6)
        jsr sync_beam
''')
    p.write_text(text)
    (stage / 'src/rom/blitter_handoff_observer.i').write_text(OBSERVER)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=104, variants='0 base;1 DPF;2 DDF+8CCK;4 DIW+16 lores pixels',
                            targets='low nibble4/15 CLXCON0040/C3; bit4 closing gate rather than opening',
                            fields={'12': 'input before DMA enable', '16': 'INTREQR completion witness bit2',
                                    '20': 'CLXDAT bit0', '22': 'second CLXDAT',
                                    '26': 'pre-read beam', '34': 'post-read beam'},
                            limitations='Finite Copper list; gate writes are WAIT+MOVE, not assumed electrical '
                            'timestamps. Inactive match0820 requires absent plane6=1. '
                            'Completion witness must be set. CPU samples after gate closes; no read alignment.'))

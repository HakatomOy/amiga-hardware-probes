"""Kind119: CPU overwrite versus cold Copper's first instruction fetch."""
import argparse
from pathlib import Path
import shutil

import build_dma_restart_boundary_rom as cold


def trials():
    return [(119, 8, control | gap << 3, phase, 0, repeat)
            for gap in range(4) for control in range(8)
            for phase in range(4) for repeat in range(2)]


def observer(variant):
    return f'''        dcb.b ${0xffb000 + variant * 0x80:x}-*,0
cold_fetch_race_{variant}:
        move.w #${0x8380 if variant & 1 else 0x8280:x},d1
        move.w 6(a6),d3
        move.w d1,$96(a6)
''' + '        nop\n' * (variant >> 3) + '''        move.w d2,(a1)
        move.w 6(a6),d4
.wait:
        move.w 6(a6),d0
        cmpi.w #$4460,d0
        bcs.s .wait
        move.w $1e(a6),d0
        andi.w #$000c,d0
        move.w d0,16(a4)
        move.w (a1),20(a4)
        move.w d3,12(a4)
        move.w d4,24(a4)
        move.w #$7fff,$96(a6)
        clr.w 32(a4)
        rts
'''


def transform(stage):
    cold.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #109,(a4)', 'cmpi.w #119,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    text = p.read_text().replace('lsl.l #8,d0', 'lsl.l #7,d0')
    old = '''        move.w #$4341,(a0)+
        move.w #$fffe,(a0)+
        move.w #$009c,(a0)+
        move.w #$8004,(a0)+'''
    new = '''        move.w #$009c,(a0)+
        move.w #$8004,(a0)+
        move.w #$009c,(a0)+
        move.w #$8008,(a0)+'''
    assert text.count(old) == 1
    text = text.replace(old, new)
    anchor = '        move.l #$2000,$80(a6)'
    text = text.replace(anchor, '''        btst #2,5(a4)
        beq.s .source_ready
        move.w #$0180,$2000
.source_ready:
''' + anchor)
    text = text.replace('        jsr sync_beam', '''        lea $2000,a1
        btst #1,5(a4)
        beq.s .store_target_ready
        lea $2010,a1
.store_target_ready:
        move.w #$0180,d2
        jsr sync_beam
        move.w #$8200,$96(a6)''')
    p.write_text(text)
    (stage / 'src/rom/blitter_handoff_observer.i').write_text(''.join(observer(v) for v in range(32)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    cold.base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
                    profile=dict(kind=119,
                                 variants='bit0 simultaneous BPLEN; bit1 unused-neighbor write; bit2 preseed new instruction; bits3:4 NOP gap',
                                 fields={'12': 'input beam', '16': 'INTREQR bits2/3',
                                         '20': 'CPU-written word', '24': 'diagnostic post-store beam'},
                                 limitations='256 ROM-only cases. Master DMA pre-enabled; cold COPEN. '
                                 'Overwrite first instruction009c with0180; bit2 records old instruction, '
                                 'bit3 independently witnesses finite Copper completion. '
                                 'Neighbor/preseed controls, no output timing alignment.'))

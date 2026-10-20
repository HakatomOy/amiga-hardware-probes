"""Kind77: CPU source overwrite versus one-word blitter A fetch."""
import argparse
from pathlib import Path
import shutil
import build_handoff_edge_rom as edge
import build_irq_stage_rom as base


def trials():
    return [(77, t, v | address | (n << 5), p, pad, r)
            for t in (0, 3, 6) for n in range(4)
            for v in (0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13)
            for address in (0, 16) for p in range(2)
            for pad in (0, 1) for r in range(2)]


def transform(stage):
    edge.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    s = p.read_text()
    assert s.count('cmpi.w #71,(a4)') == 1
    p.write_text(s.replace('cmpi.w #71,(a4)', 'cmpi.w #77,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    s = p.read_text()
    assert s.count('move.w #$0fff,d4') == 1
    s = s.replace('move.w #$0fff,d4', 'move.w #$09f0,d4')
    old = '''        move.l #$10000,d4
        btst #4,5(a4)
        beq.s .read_address_ready
        move.l #$f80000,d4'''
    new = '''        cmpi.w #6,2(a4)
        bne.s .not_preseeded
        move.w #$5555,$12000
.not_preseeded:
        move.l #$12000,d4
        btst #4,5(a4)
        beq.s .read_address_ready
        move.l #$12002,d4'''
    assert s.count(old) == 1
    p.write_text(s.replace(old, new))
    p = stage / 'src/rom/blitter_handoff_observer.i'
    s = p.read_text()
    assert s.count('        move.w 6(a6),12(a4)') == 8
    s = s.replace('        move.w 6(a6),12(a4)',
                  '        move.w #$5555,d0\n        move.w 6(a6),12(a4)')
    assert s.count('        move.w $02(a6),d0') == 8
    s = s.replace('        move.w $02(a6),d0', '        move.w d0,(a1)')
    assert s.count('move.w d4,34(a4)') == 8
    p.write_text(s.replace('move.w d4,34(a4)', 'move.w (a1),34(a4)'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
        profile=dict(kind=77, targets=['0 D-only', '3 AD source initially aaaa', '6 AD preseeded5555 positive control'],
            widths_words=[1], sources=['CPU BLTSIZE or inert write'],
            variants='bit0 priority;bits2:1 no/four/six planes;bit3 no-start;bit4 write unused source neighbor12002 instead of12000;bits6:5 NOP0..3',
            phases='phase0/1,pad0/1; exact pre-start beam authoritative',
            launch='Fixed MOVE.W D0,(A1) overwrite after start, value5555 preloaded before launch witness',
            units='packed beam,data/register words; no alignment',
            measurement_fields='kind71 except end_beam stores overwrite value5555, aux verifies written word after settling; irq_beam/irq_level identify fetched old/new source in D',
            limitations='Relative CPU/blitter ordering witness,not electrical timestamps. Same opcode for source/neighbor; preseed before ROM alignment. No Copper DMA.'))

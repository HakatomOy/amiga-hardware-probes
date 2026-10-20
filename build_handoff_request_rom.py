"""Kind76: one-word A-only/AD/D-only request handoff, identical read opcodes."""
import argparse
from pathlib import Path
import shutil
import build_handoff_edge_rom as edge
import build_irq_stage_rom as base


def trials():
    controls = (0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13)
    return [(76, target, control | source | (n << 5), phase, pad, repeat)
            for target in (0, 3, 6) for n in range(4)
            for control in controls for source in (0, 16)
            for phase in range(2) for pad in (0, 1) for repeat in range(2)]


def transform(stage):
    edge.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    s = p.read_text()
    assert s.count('cmpi.w #71,(a4)') == 1
    p.write_text(s.replace('cmpi.w #71,(a4)', 'cmpi.w #76,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    s = p.read_text()
    assert s.count('move.w #$0fff,d4') == 1
    s = s.replace('move.w #$0fff,d4', 'move.w #$08f0,d4')
    old = '''        move.l #$10000,d4
        btst #4,5(a4)
        beq.s .read_address_ready
        move.l #$f80000,d4'''
    new = '''        move.l #$dff002,d4
        btst #4,5(a4)
        beq.s .read_address_ready
        move.l #$10000,d4'''
    assert s.count(old) == 1
    p.write_text(s.replace(old, new))
    p = stage / 'src/rom/blitter_handoff_observer.i'
    s = p.read_text()
    assert s.count('        move.w $02(a6),d0') == 8
    p.write_text(s.replace('        move.w $02(a6),d0', '        move.w (a1),d0'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
        profile=dict(kind=76, targets=['0 D-only 01ff', '3 AD 09f0', '6 A-only 08f0'],
            widths_words=[1], sources=['CPU BLTSIZE or inert write'],
            variants='bit0 priority;bits2:1 no/four/six planes;bit3 no-start;bit4 first-read chip instead of DMACONR;bits6:5 NOP0..3',
            phases='phase0/1;launch NOP pad0/1; exact launch witness authoritative',
            launch='Identical MOVE.W (A1),D0 after indirect start/inert write',
            units='packed beam/data/register words; no alignment',
            measurement_fields='kind71 except end_beam is first-read word; launch_ref/end_ref/icr are three post-read beams; aux second DMACONR; irq_beam/irq_level settled D',
            limitations='A-only has no destination transfer; scratch destination must stay zero. No Copper enable. Software observations do not establish electrical edge timing.'))

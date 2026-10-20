"""Kind85: CIA destructive ICR versus PB read, then Paula ack and request samples."""
import argparse
from pathlib import Path
import shutil

import build_cia_request_rom as request
import build_irq_stage_rom as base


def trials():
    return [(85, 4, source, phase, delay, repeat)
            for source in (0, 2) for phase in (0, 1, 8, 9)
            for delay in range(16) for repeat in range(5)]


def transform(stage):
    request.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    path = stage / 'src/rom/experiment.asm'
    text = path.read_text()
    assert text.count('cmpi.w #68,(a4)') == 1
    path.write_text(text.replace('cmpi.w #68,(a4)', 'cmpi.w #85,(a4)'))
    path = stage / 'src/rom/irq_stage_kernel.i'
    text = path.read_text()
    assert text.count('addi.w #32,d0') == 1
    path.write_text(text.replace('addi.w #32,d0', 'addi.w #24,d0'))
    path = stage / 'src/rom/edge_kernel.asm'
    text = path.read_text()
    prefix, bodies = text.split('        dcb.b $ffda00-*,0', 1)
    a, b = bodies.split('        dcb.b $ffdc00-*,0', 1)
    blocks = []
    dispatch = {}
    for source, cia, original, body in (('a', 0xbfe001, 0xffda00, a),
                                        ('b', 0xbfd000, 0xffdc00, b)):
        dispatch[source] = []
        for clear in (False, True):
            for odd in (False, True):
                address = 0xffda00 + len(blocks) * 0x200
                dispatch[source].append(address)
                transfer = cia + (0xd00 if clear else 0x100)
                old = f'        move.b ${cia+0x100:06x},d1\n        move.w $1e(a6),d5'
                assert body.count(old) == 1
                gap = 'exg d2,d2' if odd else 'nop'
                changed = body.replace(old, f'        move.b ${transfer:06x},d1\n'
                                       '        move.w #$2008,$9c(a6)\n'
                                       f'        {gap}\n        move.w $1e(a6),d5')
                changed = changed.replace(f'.plain{original:x}', f'.plain{address:x}')
                blocks.append(f'        dcb.b ${address:06x}-*,0' + changed)
    path.write_text(prefix + '\n'.join(blocks))
    path = stage / 'src/rom/irq_stage_observer.i'
    text = path.read_text()
    for source, original in (('a', 0xffda00), ('b', 0xffdc00)):
        plain, odd, clear, clear_odd = dispatch[source]
        replacement = f'''.fast_timer_{source}:
        btst #3,7(a4)
        bne.s .clear_{source}
        btst #0,7(a4)
        bne.s .pb_odd_{source}
        jmp ${plain:06x}
.pb_odd_{source}:
        jmp ${odd:06x}
.clear_{source}:
        btst #0,7(a4)
        bne.s .clear_odd_{source}
        jmp ${clear:06x}
.clear_odd_{source}:
        jmp ${clear_odd:06x}'''
        old = f'.fast_timer_{source}:\n        jmp ${original:06x}'
        assert text.count(old) == 1
        text = text.replace(old, replacement)
    path.write_text(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm', required=True)
    parser.add_argument('--wsl', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    base.build(args.vasm, args.wsl, args.out, aligned=True, rows=trials(), transform=transform,
               profile=dict(kind=85, phases='bit0=Nop/EXG aperture; bit3=PB control/ICR clear',
                            fields='TA, raw PB or destructive ICR, four INTREQ reads after Paula ack',
                            limitation='Software observations constrain cancellation, not physical pin location.'))

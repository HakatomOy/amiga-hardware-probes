"""Kind86: paired CLXDAT read apertures around CPU pointer-write collisions."""
import argparse
from pathlib import Path
import shutil

import build_pointer_collision_rom as pointer
import build_irq_stage_rom as base


def trials():
    return [(86, target, control, phase, aperture, repeat)
            for target in (1, 2, 3) for control in (4, 5, 6, 7)
            for phase in (6, 7, 8, 9, 10, 20) for aperture in range(4)
            for repeat in range(5)]


def transform(stage):
    pointer.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    path = stage / 'src/rom/experiment.asm'
    text = path.read_text()
    assert text.count('cmpi.w #73,(a4)') == 1
    path.write_text(text.replace('cmpi.w #73,(a4)', 'cmpi.w #86,(a4)'))
    path = stage / 'src/rom/blitter_handoff_kernel.i'
    text = path.read_text()
    text = text.replace('blitter_handoff_trial:\n', 'blitter_handoff_trial:\n        move.l a3,-(sp)\n', 1)
    assert text.count('        rts\n') == 1
    text = text.replace('        rts\n', '        movea.l (sp)+,a3\n        rts\n', 1)
    text = text.replace('        jsr sync_beam', '''        move.w 8(a4),d0
        lsl.w #2,d0
        lea .readers(pc),a3
        movea.l (a3,d0.w),a3
        jsr sync_beam''')
    text = text.replace('        jsr sync_beam\n', '        jsr sync_beam\n        jsr $fb0000\n', 1)
    text = text.replace('#$4211', '#$4411').replace('#$4200', '#$4400')
    text = text.replace('#$4420', '#$4620')
    text = text.replace('cmpi.w #$4320,d0', 'cmpi.w #$4510,d0')
    start = text.index('        move.w 6(a6),26(a4)')
    end = text.index('.settled_line:', start)
    text = text[:start] + '        jsr (a3)\n' + text[end:]
    text += '\n.readers: dc.l $ffea00,$ffec00,$ffee00,$fff000\n'
    path.write_text(text)
    path = stage / 'src/rom/edge_kernel.asm'
    text = path.read_text()
    for address, gap in zip((0xffea00, 0xffec00, 0xffee00, 0xfff000),
                            ('\n        '.join(['nop'] * 3),
                             'exg d2,d2\n        nop\n        nop',
                             '\n        '.join(['nop'] * 7),
                             'exg d2,d2\n        ' + '\n        '.join(['nop'] * 6))):
        text += f'''
        dcb.b ${address:06x}-*,0
        move.w 6(a6),d5
        {gap}
        move.w $0e(a6),d0
        move.w $0e(a6),d1
        move.w 6(a6),d6
        move.w d5,26(a4)
        move.w d6,34(a4)
        move.w d0,20(a4)
        move.w d1,22(a4)
        move.w d0,d2
        andi.w #1,d2
        add.w d2,d2
        move.w d1,d3
        andi.w #1,d3
        or.w d3,d2
        move.w d2,38(a4)
        rts
'''
    path.write_text(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm', required=True)
    parser.add_argument('--wsl', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    base.build(args.vasm, args.wsl, args.out, rows=trials(), transform=transform,
               profile=dict(kind=86, targets=['BPL2PTL', 'BPL2PTH', 'BPL1PTL'],
                            phases='CPU write neighbors6/7/8/9/10/20; five phase repeats',
                            aperture='delay index selects6/7/14/15 CCK before consecutive CLXDAT reads',
                            measurement_fields='kind73 first/second/settled CLXDAT; stores after paired reads',
                            limitations='Exact brackets; no electrical sampling edge or trace alignment inferred.'))

"""Controlled collision probe: common-ROM input precedes COPEN/COPJMP."""
import argparse
from pathlib import Path
import shutil

import build_pointer_collision_rom as pointer
import build_copper_dma_collision_rom as collision
import build_irq_stage_rom as base


def trials(pointer_mode):
    source = pointer.trials() if pointer_mode else collision.trials()
    kind = 98 if pointer_mode else 99
    return [(kind, target, variant | (ram << 3), phase, delay, repeat)
            for ram in range(2) for _, target, variant, phase, delay, repeat in source]


def transform(stage, pointer_mode):
    (pointer.transform if pointer_mode else collision.transform)(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    path = stage/'src/rom/experiment.asm'
    previous, kind = (73, 98) if pointer_mode else (72, 99)
    text = path.read_text()
    anchor = f'cmpi.w #{previous},(a4)'
    assert text.count(anchor) == 1
    path.write_text(text.replace(anchor, f'cmpi.w #{kind},(a4)'))
    path = stage/'src/rom/blitter_handoff_kernel.i'
    text = path.read_text()
    anchor = '        jsr sync_beam\n'
    assert text.count(anchor) == 1
    setup, observer = text.split(anchor)
    assert observer.count('        move.w d6,$96(a6)') == 1
    # Copy the same instruction bytes for both venues before alignment. D3 is
    # reserved for the common input until after the observer returns.
    setup += '''        lea $ffb000,a0
        lea $30000,a1
        move.w #1023,d0
.copy_collision_observer:
        move.l (a0)+,(a1)+
        dbra d0,.copy_collision_observer
        lea $ffb000,a0
        btst #3,5(a4)
        beq.s .collision_venue_ready
        lea $30000,a0
.collision_venue_ready:
        jsr sync_beam
        jsr $fb0000
        jsr $ffbf80
        move.w d3,38(a4)
        rts
'''
    # Event line44, early read45, settled read46. Alignment completes well
    # before the event; validate that boundary in preflight before hardware.
    setup = setup.replace('#$4211', '#$4411')
    observer = observer.replace('#$4200', '#$4400').replace('#$4320', '#$4520').replace('#$4420', '#$4620')
    assert 'd3' not in observer
    path.write_text(setup)
    (stage/'src/rom/blitter_handoff_observer.i').write_text('''        dcb.b $ffb000-*,0
collision_controlled_observer:
''' + observer + '''
        dcb.b $ffbf80-*,0
collision_common_input:
        move.w 6(a6),d3
        jmp (a0)
''')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm', required=True)
    parser.add_argument('--wsl', action='store_true')
    parser.add_argument('--pointer', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    base.build(args.vasm, args.wsl, args.out, rows=trials(args.pointer),
               transform=lambda stage: transform(stage, args.pointer),
               profile=dict(kind=98 if args.pointer else 99,
                            variants='low2 controls; bit2 CPU writer; bit3 RAM observer',
                            fields={'38': 'common-ROM pre-COPEN/COPJMP input beam; all later beams are measurements'},
                            scratch='30000..30fff; observers ffb000..ffbf7f; common input ffbf80',
                            limitations='Input marker is not a pin timestamp. Qualify on pre-enable input only; never align output traces. Requires independent hardware repeats.'))

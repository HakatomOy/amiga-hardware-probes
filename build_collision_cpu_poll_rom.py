"""Kind108: locate the first beam-poll timing divergence under two-plane DMA."""
import argparse
from pathlib import Path
import shutil

import build_irq_stage_rom as base
import build_playfield_modes_rom as modes
import build_collision_cpu_clear_rom as controls

THRESHOLDS = (0x4260, 0x4280, 0x42A0, 0x42C0, 0x42E0, 0x4300, 0x4320,
              0x4340, 0x4360, 0x4380, 0x43A0, 0x43C0, 0x43E0, 0x4400,
              0x4410, 0x4420)


def trials():
    return [(108, 8, off << 3, phase, delay, repeat)
            for off in range(2) for phase in range(4)
            for delay in range(len(THRESHOLDS)) for repeat in range(2)]


def transform(stage):
    controls.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #107,(a4)', 'cmpi.w #108,(a4)'))
    setup = '''        moveq #0,d0
        move.w 8(a4),d0
        btst #3,5(a4)
        beq.s .address_ready
        addi.w #16,d0
.address_ready:
        lsl.l #7,d0
        addi.l #$ffb000,d0
        movea.l d0,a3
'''
    kernel = modes.KERNEL.replace('        jsr sync_beam', setup + '        jsr sync_beam')
    kernel = kernel.replace('blitter_handoff_trial:\n',
                            'blitter_handoff_trial:\n        movem.l d7/a3,-(sp)\n')
    kernel = kernel.replace('        rts', '        movem.l (sp)+,d7/a3\n        rts')
    kernel = kernel.replace('        jsr $ffb000', '        nop\n        jsr (a3)')
    (stage / 'src/rom/blitter_handoff_kernel.i').write_text(kernel)
    clear = '        move.w 6(a6),14(a4)'
    tail = clear + modes.OBSERVER.split(clear, 1)[1]
    # Save the last polling value after the critical clear, preserving its
    # original bus sequence. It cannot affect the already-recorded bracket.
    tail = tail.replace('        move.w d6,$144(a6)',
                        '        move.w d6,$144(a6)\n        move.w d0,18(a4)')
    observers = []
    for off in range(2):
        for delay, threshold in enumerate(THRESHOLDS):
            address = 0xffb000 + (off * 16 + delay) * 0x80
            observers.append(f'''        dcb.b ${address:x}-*,0
poll_observer_{off}_{delay}:
        move.w 6(a6),d3
        move.w #${0x8200 if off else 0x8300:x},$96(a6)
.poll:
        move.w 6(a6),d0
        cmpi.w #${threshold:x},d0
        bcs.s .poll
''' + tail)
    (stage / 'src/rom/blitter_handoff_observer.i').write_text(''.join(observers))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=108, thresholds=list(THRESHOLDS),
                            variants='bit3 DMA off; phase also selects constant plane bits',
                            fields={'12': 'observer entry', '14': 'pre-clear beam',
                                    '18': 'last VHPOSR polling value'},
                            limitations='Original polling opcodes and immediate DMACON write. '
                            'Last poll stored only after clear. No beam alignment.'))

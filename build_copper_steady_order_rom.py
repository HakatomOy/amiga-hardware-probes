"""Kind88: immediate Copper restart versus an already enabled, WAIT-gated stream."""
import argparse
from pathlib import Path
import shutil

import build_copper_cpu_quiet_rom as quiet
import build_irq_stage_rom as base


def trials():
    # Bit4 selects the settled WAIT control; bits7:5 retain the write NOP sweep.
    return [(88, target, 14 | mode | (n << 5), phase, 0, repeat)
            for target in (0, 3, 6) for n in range(8) for mode in (0, 16)
            for phase in range(2) for repeat in range(2)]


def transform(stage):
    quiet.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    path = stage / 'src/rom/experiment.asm'
    text = path.read_text()
    assert text.count('cmpi.w #83,(a4)') == 1
    path.write_text(text.replace('cmpi.w #83,(a4)', 'cmpi.w #88,(a4)'))
    path = stage / 'src/rom/blitter_handoff_kernel.i'
    text = path.read_text()
    anchor = '        move.l #$6000,$80(a6)'
    assert text.count(anchor) == 1
    text = text.replace(anchor, anchor + '''
        btst #4,5(a4)
        beq.s .restart_setup_done
        move.w #$42a1,$5ffc        ; fixed WAIT before the unchanged MOVE stream
        move.w #$fffe,$5ffe
        move.l #$5ffc,$80(a6)
        move.w #0,$88(a6)
        move.w #$8080,$96(a6)      ; settles before CPU beam alignment
.restart_setup_done:''')
    anchor = '        jsr sync_beam\n        jsr $fb0000'
    assert text.count(anchor) == 1
    text = text.replace(anchor, '''        jsr sync_beam
        move.w #$7fff,$9c(a6)      ; discard activity from the preceding frame
        jsr $fb0000''')
    path.write_text(text)
    path = stage / 'src/rom/blitter_handoff_observer.i'
    text = path.read_text()
    anchor = '        move.w #0,$88(a6)'
    assert text.count(anchor) == 8
    text = text.replace(anchor, '''        btst #4,5(a4)
        bne.s .no_copper            ; WAIT control has no local restart/enable
''' + anchor)
    path.write_text(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm', required=True)
    parser.add_argument('--wsl', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    base.build(args.vasm, args.wsl, args.out, rows=trials(), transform=transform,
               profile=dict(kind=88, targets=['MOVE0', 'MOVE4', 'MOVE8'],
                            variants='bit4: settled WAIT versus immediate restart; bits7:5:NOP0..7; no display DMA/blitter',
                            copper='WAIT $42a1,$fffe at5ffc in settled mode, then unchanged32-MOVE burst at6000; COPER completion',
                            units='CCK beam brackets and INTREQ bits; exact cohorts, no alignment',
                            limitations='Software discrimination of startup versus steady execution; not physical request/data edges.'))

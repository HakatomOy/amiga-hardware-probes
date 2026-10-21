"""Kind89: distinguish an initial BBUSY-clear window from completed blits."""
import argparse
from pathlib import Path
import shutil

import build_handoff_focus_rom as focus
import build_irq_stage_rom as base


def trials():
    # One/16-word AD; six planes with/without Copper; real/inert starts;
    # chip/ROM first-read controls; neighboring launch slots; two repeats.
    return [(89, target, variant | source, phase, pad, repeat)
            for target in (3, 5)
            for variant in (4, 5, 6, 7, 12, 13, 14, 15)
            for source in (0, 16) for phase in range(2)
            for pad in (3, 4, 5) for repeat in range(2)]


def transform(stage):
    focus.transform(stage, read_control=True)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    path = stage / 'src/rom/experiment.asm'
    text = path.read_text()
    assert text.count('cmpi.w #60,(a4)') == 1
    path.write_text(text.replace('cmpi.w #60,(a4)', 'cmpi.w #89,(a4)'))
    path = stage / 'src/rom/blitter_handoff_kernel.i'
    text = path.read_text()
    anchor = '        move.l #$6000,$80(a6)'
    assert text.count(anchor) == 1
    text = text.replace(anchor, '''        move.w #$009c,$607c       ; last of32 finite MOVEs is an activity witness
        move.w #$8010,$607e       ; COPER, leaving the early NOOP pressure intact
''' + anchor)
    path.write_text(text)
    path = stage / 'src/rom/blitter_handoff_observer.i'
    text = path.read_text()
    prefix, rest = text.split('.wait_busy:\n', 1)
    # Keep kind60's complete launch prefix, including MOVE.W #4095,D3,
    # and its first status-read opcode. Replace only the subsequent observer.
    assert rest.startswith('        move.w $02(a6),d0')
    path.write_text(prefix + '''        move.w $02(a6),d0       ; same first sample as kind60, without polling
        move.w (a1),d2             ; chip destination or ROM arbitration control
        move.w $02(a6),d1          ; second busy/zero sample
        move.w 6(a6),d3
        move.w (a0),d4             ; last destination, including16-word control
        move.w $02(a6),d6          ; third busy/zero sample
        move.w 6(a6),d5
        move.w d0,14(a4)
        move.w d2,16(a4)
        move.w d1,18(a4)
        move.w d3,20(a4)
        move.w d4,22(a4)
        move.w d6,24(a4)
        move.w d5,34(a4)
        rept 256
        nop
        endr
        move.w (a0),26(a4)         ; settled destination; no BLTCON0 rewrite
        move.w $1e(a6),28(a4)      ; settled BLIT and finite Copper witnesses
        move.w 6(a6),30(a4)
        clr.w 32(a4)
        rts
''')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm', required=True)
    parser.add_argument('--wsl', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    base.build(args.vasm, args.wsl, args.out, rows=trials(), transform=transform,
               profile=dict(kind=89, targets=['AD1', 'AD16'],
                            hypothesis='First clear poll may precede busy assertion rather than follow completion.',
                            competitor='Init/RGA arbitration delays the CPU observer until completion.',
                            launch='Exact kind60 prefix and first DMACONR opcode; no event alignment.',
                            variants='Same low5 bits as kind60: BLTPRI,DMA,no-start,chip/ROM first read.',
                            fields={'12': 'launch beam', '14': 'status0', '16': 'first chip/ROM read',
                                    '18': 'status1', '20': 'post-status1 beam', '22': 'early last destination',
                                    '24': 'status2', '26': 'settled last destination',
                                    '28': 'settled INTREQR', '30': 'settled beam', '34': 'post-status2 beam'},
                            qualification='Exact launch beam; settled D=AAAA for real and0 for inert; COPER in Copper modes.',
                            interpretation='A clear-to-busy transition in AD16 supports delayed assertion; clear plus settled D supports completion.',
                            limitations='Software samples combine bus arbitration and visibility; no electrical edge inference.'))

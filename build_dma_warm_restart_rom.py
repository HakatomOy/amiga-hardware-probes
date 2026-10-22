"""Kind112: cold enable versus an already waiting Copper and explicit restart."""
import argparse
from pathlib import Path
import shutil

import build_irq_stage_rom as base
import build_dma_restart_boundary_rom as cold

VARIANTS = (0, 1, 2, 3, 5, 7)


def trials():
    return [(112, 8, variant, phase, 0, repeat)
            for variant in VARIANTS for phase in range(4) for repeat in range(4)]


def transform(stage):
    cold.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #109,(a4)', 'cmpi.w #112,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    text = p.read_text().replace('        jsr sync_beam', '''        moveq #0,d1
        btst #2,5(a4)
        beq.s .early_gate_ready
        move.w #$8280,d1
.early_gate_ready:
        jsr sync_beam
        move.w d1,$96(a6)''')
    p.write_text(text)
    (stage / 'src/rom/blitter_handoff_observer.i').write_text(
        ''.join(cold.observer(v) for v in VARIANTS))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=112, variants='bit0 COPEN; bit1 COPJMP; bit2 pre-enable Copper at line40',
                            fields={'12': 'pre-enable beam', '24': 'post-write beam',
                                    '16': 'INTREQR completion bit2'},
                            limitations='96 ROM-only cases. Warm Copper first fetches at line40 and '
                            'waits for43:40 before measured enable on line42. Same immediate write '
                            'forms; only pre-enable beam qualifies. No alignment of outputs.'))

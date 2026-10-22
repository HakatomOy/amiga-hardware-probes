"""Kind105: distinguish first-word placement from comparator startup gating."""
import argparse
from pathlib import Path
import shutil

import build_irq_stage_rom as base
import build_playfield_gate_rom as gate


def trials():
    return [(105, 31, variant, pattern, delay, repeat)
            for pattern in range(4) for variant in (0, 1, 2, 4)
            for delay in range(24) for repeat in range(2)]


def transform(stage):
    gate.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #104,(a4)', 'cmpi.w #105,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    text = p.read_text().replace('        lea $18000,a0\n', '''        move.w 6(a4),d0
        add.w d0,d0
        lea .patterns(pc),a0
        move.w (a0,d0.w),d1
        move.w d1,d2
        lea $18000,a0
''')
    p.write_text(text + '\n.patterns:\n        dc.w $0000,$ffff,$8000,$0001\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=105, variants='0 base;1 DPF;2 DDF+8CCK;4 DIW+16 lores pixels',
                            phases='Repeated two-plane word0000/ffff/8000/0001',
                            fields={'12': 'input', '16': 'INTREQR completion witness bit2',
                                    '20': 'CLXDAT bit0', '22': 'second CLXDAT',
                                    '26': 'pre-read beam', '34': 'post-read beam'},
                            limitations='C3 gate opens at WAIT4420 and closes at4430+2*delay; '
                            'CLXCON0820 outside gate. WAIT positions are programmed, not electrical edges. '
                            'Positive/negative controls and finite Copper completion witness. No alignment.'))

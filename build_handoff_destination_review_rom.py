"""PR810: descending two-word D-side CPU restore race and neighbor controls."""
import argparse
from pathlib import Path
import shutil
import build_handoff_race_rom as race
import build_irq_stage_rom as base


def trials():
    return [(127, target, pri | neighbor | inactive | (n << 5), phase, 0, repeat)
            for target in (0, 3, 6) for pri in (0, 1)
            for neighbor in (0, 16) for inactive in (0, 8)
            for n in range(4) for phase in range(2) for repeat in range(2)]


def transform(stage):
    race.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #77,(a4)', 'cmpi.w #127,(a4)'))
    p = stage / 'src/rom/blitter_handoff_kernel.i'
    s = p.read_text()
    s = s.replace('move.l #$12000,$50(a6)', 'move.l #$12002,$50(a6)')
    s = s.replace('move.l #$10000,$54(a6)', 'move.l #$10002,$54(a6)')
    s = s.replace('        ; Compute BLTSIZE', '        move.w #2,$42(a6)\n        ; Compute BLTSIZE', 1)
    s = s.replace('.width_ready:\n', '.width_ready:\n        move.w #$0042,d5\n        movea.l #$10000,a0\n', 1)
    s = s.replace('move.l #$12000,d4', 'move.l #$10000,d4')
    s = s.replace('move.l #$12002,d4', 'move.l #$0fffe,d4')
    # Positive old-value control changes the source before launch; target6
    # should copy5555 to destination even if the later CPU restore loses.
    s = s.replace('move.w #$5555,$12000', 'move.w #$5555,$12000\n        move.w #$5555,$12002')
    p.write_text(s)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=127, variants='bit0=BLTPRI;bit3=no-start;bit4=neighbor0fffe;bits6:5=NOP0..3',
                            targets=['D-only', 'AD oldaaaa', 'AD old5555'],
                            limitations='Descending two-word blit10002->10000. CPU restores10000 or outside neighbor0fffe. Final words and exact launch brackets; no loader-specific workaround.'))

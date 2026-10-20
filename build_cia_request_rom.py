"""Kind68: four request samples eight CCK apart after calibrated TA/PB6 reads."""
import argparse
from pathlib import Path
import shutil
import build_cia_source_rom as source
import build_irq_stage_rom as base


def trials():
    return [(68, *row[1:]) for row in source.trials()]


def transform(stage):
    source.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #66,(a4)', 'cmpi.w #68,(a4)'))
    p = stage / 'src/rom/edge_kernel.asm'
    s = p.read_text()
    for cia in (0xbfe001, 0xbfd000):
        old = f'''        moveq #0,d7
        move.b ${cia+0x400:06x},d7
        move.w 6(a6),d6
        moveq #0,d4
        move.b ${cia+0xd00:06x},d4'''
        new = '''        nop
        move.w $1e(a6),d2
        nop
        move.w $1e(a6),d4
        nop
        move.w $1e(a6),d7
        move.w 6(a6),d6'''
        assert old in s
        s = s.replace(old, new)
    s = s.replace('        move.w d7,28(a4)\n        move.w d4,30(a4)',
                  '        move.w d2,28(a4)\n        move.w d4,30(a4)\n        move.w d7,38(a4)')
    p.write_text(s)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, aligned=True, rows=trials(), transform=transform,
               profile=dict(kind=68, sample_spacing_cck=8,
                            measurements='TA before, PB6, four INTREQR samples; no ICR read until cleanup',
                            qualification='Exact independent PRA, launch and observation beam brackets',
                            limitations='Software readback; does not identify an electrical pin separately from Paula input sampling'))

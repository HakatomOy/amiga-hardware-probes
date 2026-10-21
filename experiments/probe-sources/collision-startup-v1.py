"""Kind100: bracket initial DMA enable/restart before collision polling."""
import argparse
from pathlib import Path
import shutil
import build_controlled_collision_rom as controlled
import build_irq_stage_rom as base


def trials():
    return [(100,1,control | (ram << 3),pad,0,repeat)
            for ram in range(2) for control in (0,1,3)
            for pad in (0,1,2,6) for repeat in range(4)]


def transform(stage):
    controlled.transform(stage, True)
    shutil.copyfile(__file__, stage/Path(__file__).name)
    path=stage/'src/rom/experiment.asm'
    text=path.read_text();assert text.count('cmpi.w #98,(a4)')==1
    path.write_text(text.replace('cmpi.w #98,(a4)','cmpi.w #100,(a4)'))
    path=stage/'src/rom/blitter_handoff_kernel.i'
    text=path.read_text();assert text.count('        move.w d3,38(a4)')==1
    path.write_text(text.replace('        move.w d3,38(a4)',
        '        move.w d1,36(a4)\n        move.w d4,24(a4)\n        move.w d3,38(a4)'))
    path=stage/'src/rom/blitter_handoff_observer.i'
    text=path.read_text();anchor='        move.w d6,$96(a6)\n        move.w #0,$88(a6)'
    assert text.count(anchor)==1
    path.write_text(text.replace(anchor,'        move.w 6(a6),d1\n'+anchor+'\n        move.w 6(a6),d4'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm',required=True);p.add_argument('--wsl',action='store_true')
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    base.build(a.vasm,a.wsl,a.out,rows=trials(),transform=transform,
        profile=dict(kind=100,variants='low2 main/planes-off/positive; bit3 RAM venue; phase launch padding0/1/2/6; four repeats',
            fields={'36':'pre-COPEN beam','24':'immediate post-COPJMP beam','38':'common-ROM input before venue jump'},
            limitations='Added reads perturb the sequence deliberately; compare this ROM only. All downstream markers measured, not qualification. No trace alignment.'))

"""Kind83: direct Copper data-word race with display DMA disabled."""
import argparse
from pathlib import Path
import shutil

import build_copper_cpu_order_rom as order
import build_irq_stage_rom as base


def trials():
    return [(83,)+row[1:] for row in order.trials()]


def transform(stage):
    order.transform(stage)
    shutil.copyfile(__file__,stage/Path(__file__).name)
    path=stage/'src/rom/experiment.asm'
    text=path.read_text()
    assert text.count('cmpi.w #81,(a4)')==1
    path.write_text(text.replace('cmpi.w #81,(a4)','cmpi.w #83,(a4)'))
    path=stage/'src/rom/blitter_handoff_kernel.i'
    text=path.read_text()
    assert text.count('move.w #$6200,$100(a6)')==1
    path.write_text(text.replace('move.w #$6200,$100(a6)','move.w #$0200,$100(a6)'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm',required=True)
    parser.add_argument('--wsl',action='store_true')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    base.build(args.vasm,args.wsl,args.out,rows=trials(),transform=transform,
        profile=dict(kind=83,targets=['MOVE0','MOVE4','MOVE8','MOVE12'],
                     sources=['kind81 data-word protocol; zero active bitplanes in both DMA modes'],
                     masks=None,masked_fields=None,
                     measurement_fields='kind81; compare against exact observed launch cohorts,not kind81 clock alignment',
                     limitations='Separates general CPU/Copper ordering from six-plane/line-end starvation;no active blitter, no trace alignment.'))

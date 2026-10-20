"""Kind82: CPU changes Copper instruction opcode instead of its data word."""
import argparse
from pathlib import Path
import shutil

import build_copper_cpu_order_rom as data
import build_irq_stage_rom as base


def trials():
    return [(82,)+row[1:] for row in data.trials()]


def transform(stage):
    data.transform(stage)
    shutil.copyfile(__file__,stage/Path(__file__).name)
    path=stage/'src/rom/experiment.asm'
    text=path.read_text()
    assert text.count('cmpi.w #81,(a4)')==1
    path.write_text(text.replace('cmpi.w #81,(a4)','cmpi.w #82,(a4)'))
    path=stage/'src/rom/blitter_handoff_kernel.i'
    text=path.read_text()
    for old,new in [('addi.l #$6002,d4','addi.l #$6000,d4'),
                    ('move.w #$009c,-2(a1)','move.w #$01fe,(a1)'),
                    ('move.w #$8002,(a1)','move.w #$8004,2(a1)')]:
        assert text.count(old)==1
        text=text.replace(old,new)
    path.write_text(text)
    path=stage/'src/rom/blitter_handoff_observer.i'
    text=path.read_text()
    assert text.count('move.w #$8004,d0')==8
    path.write_text(text.replace('move.w #$8004,d0','move.w #$009c,d0'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm',required=True)
    parser.add_argument('--wsl',action='store_true')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    base.build(args.vasm,args.wsl,args.out,rows=trials(),transform=transform,
        profile=dict(kind=82,targets=['MOVE0','MOVE4','MOVE8','MOVE12'],
                     sources=['CPU replaces Copper IR1 NOP01fe with INTREQ009c; IR2 constant8004; BLTSIZE always inert'],
                     masks=None,masked_fields=None,
                     measurement_fields='kind81; settled SOFT bit2=CPU opcode visible,0=oldNOP; COPER bit4=stream complete; aux=stored009c',
                     limitations='Paired opcode/data fetch controls,not electrical timestamps; exact launch brackets; no alignment.'))

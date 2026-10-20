"""Kind75: source-mask and four/six-plane neighbors for startup eligibility."""
import argparse
from pathlib import Path
import shutil
import build_handoff_edge_rom as edge
import build_irq_stage_rom as base


def trials():
    return [(75,t,v|(n<<5),p,pad,r) for t in (0,3,6) for n in range(4)
            for v in (0,1,2,3,4,5,8,9,10,11,12,13) for p in range(2)
            for pad in (0,2) for r in range(2)]


def transform(stage):
    edge.transform(stage)
    shutil.copyfile(__file__,stage/Path(__file__).name)
    p=stage/'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #71,(a4)','cmpi.w #75,(a4)'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm',required=True);p.add_argument('--wsl',action='store_true')
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    base.build(a.vasm,a.wsl,a.out,rows=trials(),transform=transform,
        profile=dict(kind=75,targets=['0 D-only one word','3 AD one word','6 ABCD one word'],
            sources=['CPU BLTSIZE or inert write'],masks=None,masked_fields=None,
            phases='launch0/1,pad0/2; post-start NOP0..3 in variant bits7:5',
            variants='lowbit priority;bits2:1 zero/four/six-plane DMA;bit3 no-start',
            event_offset='Original measured launch retained',watchdog='No outcome-dependent polling',
            launch='status-first observer after CPU size/inert write',
            units='packed beam,data and register flags;no alignment',
            measurement_fields='kind71 fields unchanged: three post-read beams,status0/status1,request and settled destination words',
            limitations='Source masks and fixed DMA discriminate startup eligibility; software snapshots do not directly locate electrical bus ownership.'))

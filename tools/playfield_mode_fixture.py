"""Export the repeated A500 mode matrix as a compact Copperline test fixture."""
import argparse
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import experiment as e


def consensus(runs):
    groups=defaultdict(set)
    owners=defaultdict(set)
    repeats=defaultdict(lambda:defaultdict(set))
    for index,rows in enumerate(runs):
        for row in rows:
            if row['kind']!=101:raise ValueError('expected playfield mode probe kind101')
            key=(row['target'],row['phase'],(row['variant']>>1)&1,row['variant']&1)
            groups[key].add(row['counter']&0x23)
            owners[key].add(index)
            repeats[key][index].add(row['repeat'])
    expected={(target,pixel,sprite,dual) for target in range(16) for pixel in range(4)
              for sprite in range(2) for dual in range(2)}
    if set(groups)!=expected:raise ValueError('mode matrix is incomplete')
    for key in expected:
        if len(groups[key])!=1:raise ValueError(f'conflicting collision observations: {key}')
        if len(owners[key])<2 or any(len(r)<2 for r in repeats[key].values()):
            raise ValueError('each case needs two runs and two repeats per run')
    return {key:next(iter(values)) for key,values in groups.items()}


def export(run,out):
    spec=e.read(run/'experiment.json');build=e.read(run/'rom/manifest.json')
    report=e.read(run/'comparison.json')
    runs=[e.load_capture(e.resolve(p),build,spec['capture'],reference=True)[1] for p in report['references']]
    for rows in runs:e.check_coverage(rows,spec['capture'])
    values=consensus(runs)
    header=('# A500 PAL, stock68000, 512KiB chip/512KiB slow; two HW runs, two repeats.\n'
            '# ROM '+build['rom_sha256']+'\n'
            '# Source references/playfield-modes-v1; CLXDAT masked to bits0/1/5.\n'
            '# target=CLXCON enable-mask*4+desired; pixel=constant BPL1/BPL2; sprite0 on/off; DPF.\n'
            '# BPLDAT starts zero; constant DMA data follows.\n'
            'target,pixel,sprite,dual,clxdat\n')
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(header+''.join(','.join(map(str,(*key,value)))+'\n' for key,value in sorted(values.items())))
    changes={name:sum(bool(values[t,p,s,0]&mask)!=bool(values[t,p,s,1]&mask)
                     for t in range(16) for p in range(4) for s in range(2))
             for name,mask in [('pf_pf',1),('sprite_pf1',2),('sprite_pf2',32)]}
    return dict(cases=len(values),unique_mode_pairs=128,mode_differences=changes,fixture=str(out),rom_sha256=build['rom_sha256'])


if __name__=='__main__':
    import json
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('run',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    try:print(json.dumps(export(a.run,a.out)))
    except (OSError,KeyError,ValueError) as error:p.exit(1,str(error)+'\n')

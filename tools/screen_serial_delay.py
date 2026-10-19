"""Screen kind64 flag-delay hypotheses; never replace compiled-emulator replay."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import rom_results


def screen(rows):
    errors=Counter({d:0 for d in range(9)});excluded=Counter();used=0
    for r in rows:
        if r['kind']!=64 or r['variant'] not in (0,1) or r['phase'] not in range(4) or r['status']:
            raise ValueError('not a valid kind64 observation')
        latch=(15,31,63,127)[r['phase']];before=r['end_beam'];after=r['end_ref']
        if after<3:
            excluded['possible_reload_before_final_TB_read']+=1;continue
        if (before-after)%(latch+1)!=6:
            excluded['counter_bracket_not_six_E_clocks']+=1;continue
        # Identical moveq/CIA-read sequences place ICR midway between TA
        # transfers, three E-clocks before the final TA observation. The
        # final TB read is three E-clocks later; after>=3 prevents another
        # underflow in that gap. Retain this assumption in the report.
        elapsed=(r['aux']-(15+16*r['variant']))*(latch+1)+latch-after-3
        for delay in errors:
            errors[delay]+=bool(r['icr']&8)!=(elapsed>=delay)
        used+=1
    return dict(observations=used,excluded=dict(excluded),errors_by_delay_E=dict(errors),
                assumptions=['TA/ICR/TA transfers are symmetric, three E-clocks apart.',
                             'Screen eventUF15(single)/31(queued); byte period16 underflows.',
                             'Exclude possible reload before final TB read; no timestamp alignment.'],
                limitation='Hypothesis screening only; acceptance requires actual emulator replay and neighbors.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hardware',type=Path,action='append',required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();rows=[];sources=set()
    for path in a.hardware:
        meta,record=rom_results.decode((path/'results.bin').read_bytes());rows+=record;sources.add(meta['source_id'])
    if len(sources)!=1:p.error('source mismatch')
    report=screen(rows);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

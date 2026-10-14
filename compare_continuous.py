#!/usr/bin/env python3
"""Compare timer captures at matching frozen E-clock duration, with strict provenance."""
import argparse, collections, json
from pathlib import Path
from rom_results import decode, FIELDS

KINDS={6,7,8,9,12,13,14}
COUNTERS=('counter','aux','second_counter_or_beam','second_icr_or_level')

def compare(hardware,candidate):
    hm,h=decode(hardware);cm,c=decode(candidate)
    if hm['source_id']!=cm['source_id'] or len(h)!=len(c):
        raise ValueError('Source or record-count mismatch')
    if any(r['status'] for r in h+c): raise ValueError('Unsuccessful trial in capture')
    groups={}; failures=[]
    for index,(a,b) in enumerate(zip(h,c)):
        if [a[k] for k in FIELDS[:6]]!=[b[k] for k in FIELDS[:6]]:
            raise ValueError('Descriptor mismatch at record '+str(index))
        if a['kind'] not in KINDS: continue
        key=f"{a['kind']}/{a['target']}/{a['variant']}"
        g=groups.setdefault(key,dict(kind=a['kind'],target=a['target'],variant=a['variant'],records=0,
                                    clock_matched=0,counter_mismatches={k:0 for k in COUNTERS},
                                    control_or_timer_icr_mismatches=0))
        g['records']+=1
        if a['reference_ticks']!=b['reference_ticks']:continue
        g['clock_matched']+=1
        differences={k:[a[k],b[k]] for k in COUNTERS if a[k]!=b[k]}
        for k in differences:g['counter_mismatches'][k]+=1
        mask=9 if a['kind']==14 else 3
        if (a['icr']^b['icr'])&mask:
            g['control_or_timer_icr_mismatches']+=1
            differences['icr_masked']=[a['icr']&mask,b['icr']&mask]
        if differences:failures.append(dict(index=index,descriptor=[a[k] for k in FIELDS[:6]],differences=differences))
    if not groups:raise ValueError('Not a continuous/mode/pulse capture')
    calibration={}
    for label,rows in (('hardware',h),('candidate',c)):
        controls=[r for r in rows if r['kind']==9 and r['variant']==200]
        offsets=collections.Counter(r['reference_ticks']-(200-r['counter']) for r in controls)
        calibration[label]=dict(offsets)
        if len(offsets)==1:
            offset=next(iter(offsets));zero=collections.defaultdict(lambda:[0,0]);curve=[0,0]
            for r in rows:
                if r['kind']!=9 or not r['variant']:continue
                latch=r['variant'];n=r['reference_ticks']-offset
                internal=(latch-n)%(latch+1)
                expected=latch if internal==0 else internal
                curve[0]+=1;curve[1]+=r['counter']==expected
                if internal==0:
                    zero[str(latch)][0]+=1;zero[str(latch)][1]+=r['counter']==latch
            calibration[label]['zero_phase_samples_and_reload_matches']=dict(zero)
            calibration[label]['read_curve_samples_and_matches']=curve
    return dict(hardware=hm,candidate=cm,groups=list(groups.values()),
                matched_clock_records=sum(g['clock_matched'] for g in groups.values()),
                counter_mismatch_records=len(failures),failures=failures,live_read_calibration=calibration)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('hardware',type=Path);p.add_argument('candidate',type=Path)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    report=compare(a.hardware.read_bytes(),a.candidate.read_bytes())
    a.out.write_text(json.dumps(report,indent=2)+'\n')
    print(f"Matched {report['matched_clock_records']} E-clock durations; "
          f"{report['counter_mismatch_records']} mismatched counter/control records")

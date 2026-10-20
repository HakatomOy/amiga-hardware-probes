"""Counterfactual CIA source-delay screen using verified, unaligned read clocks.

This screens hypotheses only. It never changes comparison qualification or
proves an electrical pin delay. Report common support to avoid favoring delays
with fewer available neighboring latch values.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import experiment as e

NAMES = ('Paula_request', 'request1', 'request2', 'request3')


def read_clocks(trace, rows):
    pattern = re.compile(r'^CPUBUS kind=custom addr=00dff01e .*? v=([0-9a-f]+) h=([0-9a-f]+) ', re.M)
    clocks = [int(v, 16)*227+int(h, 16) for v, h in pattern.findall(trace)]
    if len(clocks) != len(rows)*5:
        raise ValueError('requires exactly four request reads and one settled read per descriptor')
    result = []
    for i, row in enumerate(rows):
        launch = row['launch_ref']
        anchor = (launch >> 8)*227+(launch & 255)
        times = tuple((t-anchor) % (312*227) for t in clocks[i*5:i*5+4])
        if not all(0 <= b-a <= 16 for a,b in zip(times,times[1:])):
            raise ValueError('unexpected request ordering/spacing')
        result.append(times)
    return result


def screen(hardware, candidate, policy, clocks, delays=range(9)):
    fields = [next(f for f in policy['measurements'] if f['name']==name) for name in NAMES]
    if len(clocks)!=len(candidate):
        raise ValueError('clock/descriptor count differs')
    def cohort(r, latch):
        return (r['kind'],r['target'],r['variant'],r['phase'],latch,
                *(e.value(r,f) for f in policy['qualification']))
    table = {}
    for r,times in zip(candidate,clocks):
        table.setdefault(cohort(r,r['delay']),set()).add((times,tuple(e.value(r,f) for f in fields)))
    results = []
    for delay in delays:
        compared = {}
        for ri,r in enumerate(hardware):
            original = {v[0] for v in table.get(cohort(r,r['delay']),set())}
            if len(original)!=1:
                continue
            times = next(iter(original))
            for i,field in enumerate(fields):
                values = set()
                for k in range(-15,16):
                    for other,vector in table.get(cohort(r,r['delay']+k),set()):
                        for j in range(4):
                            if 5*k-(other[j]-times[i])==delay:
                                values.add(vector[j])
                if len(values)==1:
                    compared[ri,i] = next(iter(values)) != e.value(r,field)
        results.append((delay,compared))
    common=set.intersection(*(set(v) for _,v in results)) if results else set()
    return dict(model='Counterfactual source delay; exact qualification, actual grant clocks; not fix acceptance',
                total_fields=len(hardware)*4, common_fields=len(common),
                pairwise=[dict(delays_CCK=[a,b],common_fields=len(set(x)&set(y)),
                               differences=[sum(x[k] for k in set(x)&set(y)),
                                            sum(y[k] for k in set(x)&set(y))])
                          for index,(a,x) in enumerate(results) for b,y in results[index+1:]],
                results=[dict(delay_CCK=d,compared_fields=len(v),different_fields=sum(v.values()),
                              unavailable_or_ambiguous=len(hardware)*4-len(v),
                              common_differences=sum(v[k] for k in common)) for d,v in results])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('run',type=Path)
    p.add_argument('--trace-run',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    packet=(a.run/'candidate/results.bin').read_bytes()
    if packet!=(a.trace_run/'results.bin').read_bytes():
        raise ValueError('observational trace packet differs from baseline')
    spec=e.read(a.run/'experiment.json')
    report=e.read(a.run/'comparison.json')
    _,candidate=e.rom_results.decode(packet)
    hardware=[]
    for ref in report['references']:
        hardware.extend(e.rom_results.decode((Path(ref)/'results.bin').read_bytes())[1])
    trace=(a.trace_run/'run.log').read_bytes()
    clocks=read_clocks(trace.decode(),candidate)
    result=screen(hardware,candidate,spec['comparison'],clocks)
    result.update(packet_sha256=e.digest(packet),trace_sha256=e.digest(trace),
                  interval_counts=dict(Counter(b-a for t in clocks for a,b in zip(t,t[1:]))))
    e.write(a.out,result)
    print(json.dumps(result))

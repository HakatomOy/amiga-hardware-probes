#!/usr/bin/env python3
"""Validate the measured fixed-WAIT/STOP phase rule independently per capture."""
import argparse, json
from pathlib import Path
from rom_results import decode

def check(data):
    meta, rows = decode(data)
    phase=[]; stop=[]; ambiguous=0
    for row in rows:
        if row['kind']==5:
            # This suite uses a continuous timer with latch 200 (period 201).
            expected=(row['aux']-8)%201
            stop.append(dict(trial=[row[k] for k in ('target','phase','delay','repeat')],
                             ok=row['counter']==expected and row['second_counter_or_beam']==expected and row['status']==0))
        if row['kind']==10 and row['target']==3 and row['variant'] in (5,6) and row['delay'] in (0,4):
            entry=row['aux']; irq=row['irq_beam']
            if (entry&255)<2 or (irq&255)<2:
                ambiguous+=1; continue
            parity=((entry>>8)*227+(entry&255))&1
            expected=37 if parity==(1 if row['variant']==5 else 0) else 38
            actual=(irq>>8)*227+(irq&255)-96*227-64
            phase.append(dict(trial=[row[k] for k in ('variant','phase','delay','repeat')],
                              expected=expected,actual=actual,ok=expected==actual and row['status']==0 and row['irq_level']==1))
    if not phase or not stop: raise ValueError('Expected a focused STOP/phase capture')
    return dict(metadata=meta,phase_trials=len(phase),phase_matches=sum(r['ok'] for r in phase),
                ambiguous_entry_or_irq=ambiguous,stop_trials=len(stop),stop_matches=sum(r['ok'] for r in stop),
                phase_failures=[r for r in phase if not r['ok']],stop_failures=[r for r in stop if not r['ok']])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('--out',type=Path)
    a=p.parse_args();report=check(a.capture.read_bytes());text=json.dumps(report,indent=2)+'\n'
    if a.out:a.out.write_text(text)
    print(text)

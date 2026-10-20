"""Bind handoff traces to immutable descriptors and summarize exact PAL beam deltas.

No event alignment. START-relative clocks describe emulator scheduling only;
physical comparisons retain their original launch qualification and beams.
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


def beam_delta(hardware, candidate):
    # VHPOSR supplies only the low eight vertical bits. These fixed observers
    # are on line66 (occasionally the next line), not across a PAL frame edge.
    # Do not invent the missing VPOSR bit or silently align an ambiguous wrap.
    if abs((hardware >> 8) - (candidate >> 8)) > 1:
        raise ValueError('beam witnesses need same/adjacent known lines, not frame alignment')
    if (hardware & 255) >= 227 or (candidate & 255) >= 227:
        raise ValueError('horizontal witness outside PAL227 line')
    def clocks(v):
        return (v >> 8)*227+(v & 255)
    return clocks(hardware)-clocks(candidate)


def bind_trace(lines, rows, access_addresses=(0xdff002,)):
    real=[r for r in rows if not r['variant']&8]
    blocks=[]
    current=None
    pending_grant=None
    for number,line in enumerate(lines,1):
        if line.startswith('CPUBUS ') and 'addr=00dff058 ' in line:
            pending_grant=dict(line=number,text=line.rstrip())
        start=re.match(r'BLTP (\d+) (\d+) (\d+) START .*?size=([0-9a-f]+)',line)
        if start:
            if len(blocks)>=len(real):
                raise ValueError('more starts than real descriptors')
            r=real[len(blocks)]
            frame,v,h,size=(int(start[1]),int(start[2]),int(start[3]),int(start[4],16))
            if size != (0x41,0x42,0x50)[r['target']%3]:
                raise ValueError('start width disagrees with descriptor ordering')
            current=dict(case=list(e.key(r)),start_line=number,start=[frame,v,h],start_grant=pending_grant,slots=[],accesses=[])
            blocks.append(current)
            pending_grant=None
        if current is not None:
            if line.startswith('BLTP ') and (' TICK ' in line or ' END ' in line):
                current['slots'].append(dict(line=number,text=line.rstrip()))
            if line.startswith('CPUBUS ') and len(current['accesses'])<2:
                address=re.search(r'addr=([0-9a-f]+)',line)
                if address and int(address[1],16) in access_addresses:
                    current['accesses'].append(dict(line=number,text=line.rstrip()))
    if len(blocks)!=len(real):
        raise ValueError('start/descriptor count differs')
    return blocks


def summarize(cases, fields):
    groups=Counter()
    for case in cases.values():
        if case['status']!='mismatches':
            continue
        desc=case['case']
        differences=[]
        for field,expected,actual in zip(fields,case['expected'],case['actual']):
            if expected!=actual:
                delta=beam_delta(expected,actual) if field['unit']=='packed beam' else None
                differences.append((field.get('name',field['field']),delta))
        groups[(desc[1],desc[2]&31,desc[2]>>5,tuple(differences))]+=1
    return [dict(count=n,target=k[0],control=k[1],post_nops=k[2],differences=k[3]) for k,n in groups.items()]


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('run',type=Path)
    p.add_argument('--trace-run',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--case')
    p.add_argument('--addresses', default='0xdff002',
                   help='CPU witness addresses to index; retain the first two accesses per case')
    a=p.parse_args()
    packet=(a.run/'candidate/results.bin').read_bytes()
    if packet!=(a.trace_run/'results.bin').read_bytes():
        raise ValueError('trace replay packet differs')
    _,rows=e.rom_results.decode(packet)
    with (a.trace_run/'run.log').open() as stream:
        blocks=bind_trace(stream,rows,tuple(int(v,0) for v in a.addresses.split(',')))
    spec=e.read(a.run/'experiment.json')
    groups=summarize(e.read(a.run/'cases.json'),spec['comparison']['measurements'])
    e.write(a.out,dict(packet_sha256=e.digest(packet),units='PAL227 CCK/line; signed HW minus emulator on known adjacent lines; no frame alignment',groups=groups,trace_cases=blocks))
    if a.case:
        wanted=list(map(int,a.case.split(',')))
        block=next(b for b in blocks if b['case']==wanted)
        slots=block['slots'];block['slots']=slots if len(slots)<=24 else slots[:12]+slots[-12:]
        print(json.dumps(block))
    else:
        print(json.dumps(dict(cases=len(rows),trace_starts=len(blocks),mismatch_groups=len(groups),detail=str(a.out))))

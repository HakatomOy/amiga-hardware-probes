"""Bound CPU-write and Copper-fetch evidence for kind81/83 ordering failures."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import experiment as e


def index_trace(lines, rows, selected):
    if rows and rows[0]['kind'] == 83:
        return index_independent_streams(lines, rows, selected)
    current = None
    index = 0
    result = {}
    for number, line in enumerate(lines, 1):
        if line.startswith('CPUBUS kind=custom addr=00dff1fe '):
            if index >= len(rows):
                raise ValueError('extra inert start')
            row = rows[index]
            index += 1
            case = ','.join(map(str,e.key(row)))
            if case in selected:
                current = dict(case=case, address=0x6002+(row['target']//3)*16,
                               start=dict(line=number,text=line.strip()))
                result[case] = current
            else:
                current = None
        if current is None:
            continue
        if line.startswith('CPUBUS kind=write ') and 'write' not in current:
            match = re.search(r'addr=([0-9a-f]+)',line)
            if match and int(match[1],16) == current['address']:
                current['write'] = dict(line=number,text=line.strip())
        if line.startswith('COPPROBE MOVE') and 'reg=09c ' in line:
            if 'val=8002' in line or 'val=8004' in line:
                current.setdefault('fetch',dict(line=number,text=line.strip()))
            if 'val=8010' in line:
                current = None
    if index != len(rows) or set(result) != set(selected):
        raise ValueError('trace/descriptor coverage differs')
    if any('write' not in case or 'fetch' not in case for case in result.values()):
        raise ValueError('selected write/fetch not present before completion marker')
    return finish_index(result)


def finish_index(result):
    for case in result.values():
        positions = []
        for event in ('write','fetch'):
            match = re.search(r' v=([0-9a-f]+) h=([0-9a-f]+)',case[event]['text'])
            if not match:
                raise ValueError('trace lacks grant/fetch positions')
            v,h = (int(x,16) for x in match.groups())
            if h >= 227:
                raise ValueError('requires PAL227 positions')
            positions.append((v,h))
        if abs(positions[0][0]-positions[1][0])>1:
            raise ValueError('ambiguous frame span')
        case['fetch_minus_cpu_grant_cck'] = sum((b-a)*scale for a,b,scale in
            zip(positions[0],positions[1],(227,1)))
    return result


def index_independent_streams(lines, rows, selected):
    # Quiet Copper can fetch before the CPU's inert launch witness. Bind CPU
    # transfers by witness order and Copper streams independently by COPER,
    # retaining early fetches rather than dropping or aligning those cases.
    copper_rows = [r for r in rows if r['variant'] & 6 == 6]
    result = {key: dict(case=key) for key in sorted(selected)}
    cpu_index = copper_index = 0
    current = None
    for number, line in enumerate(lines, 1):
        event = dict(line=number, text=line.strip())
        if line.startswith('CPUBUS kind=custom addr=00dff1fe '):
            if cpu_index >= len(rows):
                raise ValueError('extra inert start')
            row = rows[cpu_index]
            cpu_index += 1
            current = result.get(','.join(map(str, e.key(row))))
            if current is not None:
                current.update(address=0x6002+(row['target']//3)*16, start=event)
        if current is not None and line.startswith('CPUBUS kind=write '):
            match = re.search(r'addr=([0-9a-f]+)', line)
            if match and int(match[1], 16) == current['address'] and 'write' not in current:
                current['write'] = event
        if line.startswith('COPPROBE MOVE') and 'reg=09c ' in line:
            if copper_index >= len(copper_rows):
                raise ValueError('extra Copper stream')
            key = ','.join(map(str, e.key(copper_rows[copper_index])))
            if key in result and ('val=8002' in line or 'val=8004' in line):
                if 'fetch' in result[key]:
                    raise ValueError('duplicate selected fetch')
                result[key]['fetch'] = event
            if 'val=8010' in line:
                copper_index += 1
    if cpu_index != len(rows) or copper_index != len(copper_rows):
        raise ValueError('independent CPU/Copper descriptor coverage differs')
    if any(not {'start', 'write', 'fetch'} <= case.keys() for case in result.values()):
        raise ValueError('selected write/fetch not present')
    return finish_index(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    parser.add_argument('--trace-run',required=True,type=Path)
    parser.add_argument('--screen-write-phases',action='store_true',
                        help='screen grant/return visibility on all MOVE8 Copper cases; not fix validation')
    parser.add_argument('--all-instructions', action='store_true',
                        help='include every selected instruction position in the phase screen')
    args = parser.parse_args()
    trace, run = args.trace_run,args.run
    if not e.read(trace/'trace-verification.json')['byte_identical']:
        raise ValueError('unqualified diagnostic replay')
    data = (trace/'results.bin').read_bytes()
    if data != (run/'candidate/results.bin').read_bytes():
        raise ValueError('trace packet differs from comparison candidate')
    _, rows = e.rom_results.decode(data)
    if len({r['kind'] for r in rows}) != 1 or any(r['kind'] not in (81,83) for r in rows):
        raise ValueError('requires uniform kind81 or kind83')
    fields = e.read(run/'experiment.json')['comparison']['measurements']
    index = next(i for i,f in enumerate(fields) if f.get('name') == 'Copper_order')
    cases = e.read(run/'cases.json')
    selected = {key for key,case in cases.items() if case['status']=='mismatches'
                and case['expected'][index] != case['actual'][index]}
    if args.screen_write_phases:
        selected = {key for key,case in cases.items() if case['status'] in ('matches','mismatches')
                    and (args.all_instructions or case['case'][1] == 6)
                    and (case['case'][2] & 6) == 6}
    with (trace/'run.log').open() as stream:
        result = index_trace(stream,rows,selected)
    e.write(trace/'order-trace-summary.json',result)
    distribution = Counter(case['fetch_minus_cpu_grant_cck'] for case in result.values())
    output = dict(selected_cases=len(result),fetch_minus_cpu_grant_cck=dict(distribution),
                  examples=list(result.values())[:3],detail=str(trace/'order-trace-summary.json'),
                  early_flags=early_flags(cases,index))
    if args.screen_write_phases:
        output['phase_screen'] = screen_phases(result,cases,index)
        e.write(trace/'write-phase-screen.json',output['phase_screen'])
    print(json.dumps(output))


def early_flags(cases, final_index):
    counts = Counter(qualified=0,clock_mismatch=0,early_differences=0,
                     early_differences_with_matching_final_order=0)
    examples = []
    final_matching_examples = []
    for key,case in cases.items():
        if case['status'] not in ('matches','mismatches'):
            continue
        candidate = case['candidate']
        reference = case['hardware']
        if any(any(row[f] != candidate[f] for f in ('launch_ref','end_ref','icr')) for row in reference):
            counts['clock_mismatch'] += 1
            continue
        expected = {row['counter'] & 0x16 for row in reference}
        if len(expected) != 1:
            raise ValueError('early flags are not independently stable')
        counts['qualified'] += 1
        actual = candidate['counter'] & 0x16
        if actual not in expected:
            counts['early_differences'] += 1
            final_matches = case['expected'][final_index] == case['actual'][final_index]
            counts['early_differences_with_matching_final_order'] += final_matches
            if len(examples)<3:
                examples.append(dict(case=key,expected=list(expected),actual=actual,final_matches=final_matches))
            if final_matches and len(final_matching_examples)<3:
                final_matching_examples.append(dict(case=key,expected=list(expected),actual=actual))
    return dict(counts=dict(counts),examples=examples,final_matching_examples=final_matching_examples,
                units='INTREQ bits0x16 at unchanged raw read brackets; no alignment.')


def screen_phases(indexed, cases, field):
    results = []
    for offset in (0,1,2):
        counts = Counter(matches=0,mismatches=0,repairs=0,regressions=0)
        for key,detail in indexed.items():
            case = cases[key]
            expected,actual = case['expected'][field],case['actual'][field]
            difference = detail['fetch_minus_cpu_grant_cck']
            if actual != (4 if difference >= 2 else 2):
                raise ValueError('return-phase model does not reproduce captured flags; reject screen')
            predicted = 4 if difference >= offset else 2
            counts['matches' if predicted == expected else 'mismatches'] += 1
            counts['repairs'] += actual != expected and predicted == expected
            counts['regressions'] += actual == expected and predicted != expected
        results.append(dict(write_visible_CCK_after_grant=offset,**counts))
    return dict(cases=len(indexed),results=results,
                limitation='Counterfactual data visibility only, fixed observed emulator grants/fetches. No time alignment; not patch validation.')


if __name__=='__main__':
    main()

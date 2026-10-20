"""Summarize source races separately from status and beam timing (kinds77/78)."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import experiment as e


def summarize(cases, fields):
    names = [f.get('name', f['field']) for f in fields]
    destination = names.index('first_D')
    beam_indices = [i for i, f in enumerate(fields) if f['unit'] == 'packed beam']
    totals = Counter(cases=0, destination_differences=0, beam_differences=0,
                     control_destination_differences=0, race_cases=0,
                     no_start_beam_differences=0, copper_beam_differences=0)
    groups = defaultdict(lambda: dict(cases=0, hardware=Counter(), model=Counter(),
                                     differences=0, representatives=[]))
    for case_id, case in cases.items():
        if case['status'] not in ('matches', 'mismatches'):
            raise ValueError('ordering summary requires qualified stable complete cases')
        kind, target, variant, phase, pad, repeat = case['case']
        if kind not in (77, 78) or target not in (0, 3, 6):
            raise ValueError('expected kind77/78 descriptors')
        hw, model = case['expected'], case['actual']
        if len(hw) != len(fields) or len(model) != len(fields):
            raise ValueError('measurement vector length differs from contract')
        different = hw[destination] != model[destination]
        totals['cases'] += 1
        totals['destination_differences'] += different
        beam_difference = any(hw[i] != model[i] for i in beam_indices)
        totals['beam_differences'] += beam_difference
        totals['no_start_beam_differences'] += bool(variant & 8) and beam_difference
        totals['copper_beam_differences'] += ((variant >> 1) & 3) == 3 and beam_difference
        race = target == 3 and not variant & 8
        if not race:
            totals['control_destination_differences'] += different
            continue
        if hw[destination] not in (0xaaaa, 0x5555) or model[destination] not in (0xaaaa, 0x5555):
            raise ValueError('race destination is neither old nor new source')
        totals['race_cases'] += 1
        key = ((variant >> 1) & 3, variant & 1, bool(variant & 16), variant >> 5)
        g = groups[key]
        g['cases'] += 1
        g['hardware'][f'{hw[destination]:04x}'] += 1
        g['model'][f'{model[destination]:04x}'] += 1
        g['differences'] += different
        if different and len(g['representatives']) < 3:
            g['representatives'].append(case_id)
    result = []
    for (dma, nasty, neighbor, nops), g in sorted(groups.items()):
        result.append(dict(dma_planes=(0, 4, 6, 6)[dma], copper=dma == 3, nasty=bool(nasty),
                           neighbor_write=neighbor, post_nops=nops, **g))
    return dict(counts=dict(totals), groups=result,
                units='Destination words: aaaa=old,5555=new. Beam differences are exact raw witnesses,not aligned event timestamps.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('run', type=Path)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    spec = e.read(a.run / 'experiment.json')
    result = summarize(e.read(a.run / 'cases.json'), spec['comparison']['measurements'])
    e.write(a.out, result)
    print(json.dumps(dict(counts=result['counts'], changed_ordering_groups=[g for g in result['groups']
        if g['differences']][:8], detail=str(a.out))))

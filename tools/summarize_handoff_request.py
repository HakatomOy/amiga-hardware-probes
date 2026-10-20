"""Summarize kind76 source/D request contrasts without inspecting matching rows."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import experiment as e
from tools.summarize_handoff_trace import beam_delta


def summarize(cases, fields):
    groups = defaultdict(lambda: dict(total=0, timing=0, data=0, deltas=Counter(), cases=[]))
    wrap_sensitive = []
    for case_id, case in cases.items():
        if case['status'] not in ('matches', 'mismatches'):
            raise ValueError('request contrasts require qualified, stable, complete cases')
        kind, target, variant, phase, pad, repeat = case['case']
        if kind != 76 or target not in (0, 3, 6):
            raise ValueError('expected kind76 request descriptors')
        key = (target, (variant >> 1) & 3, bool(variant & 16), bool(variant & 8))
        group = groups[key]
        group['total'] += 1
        if len(case['expected']) != len(fields) or len(case['actual']) != len(fields):
            raise ValueError('measurement vector length differs from contract')
        deltas = []
        data = False
        for field, hw, model in zip(fields, case['expected'], case['actual']):
            if field['unit'] == 'packed beam':
                delta = beam_delta(hw, model)
                deltas.append(delta)
                if abs(delta) > 227 // 2:
                    wrap_sensitive.append(dict(case=case_id, field=field.get('name', field['field']),
                        hardware=hw, candidate=model, encoded_delta=delta))
            else:
                data |= hw != model
        timing = any(deltas)
        group['timing'] += timing
        group['data'] += data
        group['deltas'][tuple(deltas)] += 1
        if (timing or data) and len(group['cases']) < 3:
            group['cases'].append(case_id)
    result = []
    for (target, dma, chip, inert), group in sorted(groups.items()):
        result.append(dict(channel={0: 'D', 3: 'AD', 6: 'A'}[target],
            dma_planes=(0, 4, 6)[dma], first_read='chip' if chip else 'DMACONR',
            no_start=inert, cases=group['total'], timing_differences=group['timing'],
            data_differences=group['data'], beam_deltas=[dict(hw_minus_model=list(k), cases=n)
                for k, n in sorted(group['deltas'].items())], representatives=group['cases']))
    return dict(units='PAL227 CCK/line arithmetic on raw VHPOSR witnesses; HW minus model; no alignment',
                wrap_note='Near-line-length arithmetic differences are retained, not interpreted as physical lateness; inspect raw carry-phase witnesses.',
                wrap_sensitive=wrap_sensitive,
                beam_fields=[f.get('name', f['field']) for f in fields if f['unit'] == 'packed beam'],
                groups=result)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('run', type=Path)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    spec = e.read(a.run / 'experiment.json')
    result = summarize(e.read(a.run / 'cases.json'), spec['comparison']['measurements'])
    e.write(a.out, result)
    # Six lines summarize the uncertainty; full source/DMA distributions stay in files.
    totals = defaultdict(Counter)
    for group in result['groups']:
        totals[(group['channel'], group['no_start'])].update(
            cases=group['cases'], timing=group['timing_differences'], data=group['data_differences'])
    print(json.dumps(dict(contrasts=[dict(channel=k[0], no_start=k[1], **v)
        for k, v in sorted(totals.items())], detail=str(a.out))))

"""Print bounded kind104/105 gate sweeps; retain conflicts and all case IDs in JSON."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rom_results


def summarize(rows):
    groups = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row['kind'] not in (104, 105) or row['status'] != 0:
            raise ValueError('Expected valid kind104/105 observations')
        key = (row['kind'], row['target'], row['phase'], row['variant'])
        groups[key][row['delay']].append(row)
    result = []
    for key, delays in sorted(groups.items()):
        bits = []
        details = []
        for delay in range(max(delays) + 1):
            cases = delays.get(delay, [])
            values = {row['counter'] & 1 for row in cases}
            bits.append(str(next(iter(values))) if len(values) == 1 else '?' if values else '-')
            details.append(dict(delay=delay, values=sorted(values),
                                ids=[','.join(str(row[f]) for f in rom_results.FIELDS[:6])
                                     for row in cases]))
        result.append(dict(kind=key[0], target=key[1], pattern=key[2], variant=key[3],
                           bits=''.join(bits), details=details))
    return dict(cases=len(rows), invalid_witness=sum(row['end_beam'] & 4 == 0 for row in rows),
                nonzero_second=sum(row['icr'] & 1 != 0 for row in rows), groups=result,
                units='One character per programmed WAIT delay; no alignment or electrical timestamp inference')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('packet', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--pattern', type=int)
    p.add_argument('--limit', type=int, default=16, choices=range(1, 33))
    a = p.parse_args()
    _, rows = rom_results.decode(a.packet.read_bytes())
    result = summarize(rows)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + '\n')
    selected = [g for g in result['groups'] if a.pattern is None or g['pattern'] == a.pattern]
    result['omitted_groups'] = len(selected[a.limit:])
    result['groups'] = [{k: v for k, v in g.items() if k != 'details'} for g in selected[:a.limit]]
    result['detail'] = str(a.out)
    print(json.dumps(result))

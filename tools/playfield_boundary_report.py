"""Summarize kind103 without aligning CPU windows or discarding conflicting repeats."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rom_results


def report(packet, out):
    _, rows = rom_results.decode(Path(packet).read_bytes())
    groups = defaultdict(lambda: defaultdict(set))
    for row in rows:
        if row['kind'] != 103 or row['status'] != 0:
            raise ValueError('Expected valid kind103 observations')
        key = (row['target'], row['phase'], row['variant'])
        groups[key][row['delay']].add(tuple(row[f] for f in
            ('launch_ref', 'end_beam', 'irq_level', 'aux', 'counter', 'icr')))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    summary = []
    conflicts = 0
    varying_windows = 0
    with out.open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(('target', 'pixel', 'variant', 'delay', 'pre_clear',
                         'post_clear', 'pre_read', 'post_read', 'sample', 'second'))
        for key, delays in sorted(groups.items()):
            patterns = defaultdict(list)
            for delay, observations in sorted(delays.items()):
                varying_windows += len({o[:4] for o in observations}) != 1
                conflicts += len({(o[4] & 1, o[5] & 1) for o in observations}) != 1
                for observation in sorted(observations):
                    writer.writerow((*key, delay, *(f'{v:04x}' for v in observation)))
                    patterns[(observation[4] & 1, observation[5] & 1)].append(
                        dict(delay=delay, beams=[f'{v:04x}' for v in observation[:4]]))
            summary.append(dict(target=key[0], pixel=key[1], variant=key[2],
                                patterns=[dict(bits=bits, count=len(cases),
                                               first=cases[0], last=cases[-1])
                                          for bits, cases in sorted(patterns.items())]))
    return dict(cases=len(rows), conflicting_collision_groups=conflicts,
                varying_bracket_groups=varying_windows, csv=str(out), groups=summary)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('packet', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--limit', type=int, default=8, choices=range(1, 17))
    a = p.parse_args()
    result = report(a.packet, a.out)
    Path(str(a.out) + '.json').write_text(json.dumps(result, indent=2) + '\n')
    result['groups'] = [g for g in result['groups'] if g['pixel'] == 3][:a.limit]
    print(json.dumps(result))

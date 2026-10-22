"""Export independently repeated Copper-gate observations for Copperline unit tests."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import experiment as e


def consensus(runs, expected):
    values = defaultdict(set)
    seen = defaultdict(lambda: defaultdict(set))
    for index, rows in enumerate(runs):
        for row in rows:
            if row['kind'] not in (104, 105) or row['status'] or not row['end_beam'] & 4 or row['icr'] & 1:
                raise ValueError('invalid collision gate control')
            key = tuple(row[f] for f in ('kind', 'target', 'variant', 'phase', 'delay'))
            values[key].add(row['counter'] & 1)
            seen[key][index].add(row['repeat'])
    if set(values) != expected:
        raise ValueError('incomplete gate matrix')
    for key in expected:
        if len(values[key]) != 1:
            raise ValueError('conflicting gate observation')
        if len(seen[key]) < 2 or any(repeats != {0, 1} for repeats in seen[key].values()):
            raise ValueError('two independent runs and both repeats required')
    return {key: next(iter(v)) for key, v in values.items()}


def export(paths, out):
    combined = {}
    hashes = []
    for path in paths:
        spec = e.read(path / 'experiment.json')
        build = e.read(path / 'rom/manifest.json')
        report = e.read(path / 'comparison.json')
        runs = [e.load_capture(e.resolve(ref), build, spec['capture'], reference=True)[1]
                for ref in report['references']]
        for rows in runs:
            e.check_coverage(rows, spec['capture'])
        values = consensus(runs, {tuple(t[:5]) for t in build['trials']})
        if combined.keys() & values.keys():
            raise ValueError('duplicate experiment matrix')
        combined.update(values)
        hashes.append(build['rom_sha256'])
    text = '# A500 PAL, stock68000; two independent runs and two repeats per condition.\n'
    text += ''.join('# ROM ' + digest + '\n' for digest in hashes)
    text += '# references/playfield-gate-v1 and playfield-word-gate-v1; no CPU read during gate.\n'
    text += 'kind,target,variant,pattern,delay,pf_pf\n'
    text += ''.join(','.join(map(str, (*key, value))) + '\n' for key, value in sorted(combined.items()))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    return dict(cases=len(combined), fixture=str(out), rom_sha256=hashes)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('runs', type=Path, nargs='+')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(export(a.runs, a.out)))

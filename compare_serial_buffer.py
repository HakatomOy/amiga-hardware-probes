#!/usr/bin/env python3
"""Compare serial completion flags at exact observed Timer-A underflow brackets."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import rom_results
from build_serial_buffer_rom import SAMPLES


def key(r):
    return tuple(r[f] for f in rom_results.FIELDS[:6])


def brackets(r):
    return (r['launch_beam'], r['launch_ref'], r['end_beam'], r['end_ref'],
            r['irq_level'], r['saved_pc_offset'] >> 16,
            r['saved_pc_offset'] & 65535, r['aux'],
            r['second_counter_or_beam'], r['second_icr_or_level'])


def measures(r):
    return tuple(r[f] & 8 for f in ('counter', 'icr', 'irq_beam'))


def validate(r):
    if (r['kind'] != 63 or r['target'] not in (0, 1) or r['variant'] not in range(4)
            or r['phase'] not in (0, 1) or r['delay'] not in SAMPLES + (14,15,16,17,18)
            or r['repeat'] not in (0, 1) or r['status']):
        raise ValueError('invalid descriptor or capture status')
    b = brackets(r)
    absent = ({0, 1} if r['variant'] == 0 else set()) | ({2, 3} if r['variant'] != 2 else set())
    for i in range(0, 10, 2):
        if i in absent:
            if b[i:i+2] != (65535, 65535):
                raise ValueError('unexpected absent-write bracket')
        elif not 0 <= b[i] <= b[i+1] < 128:
            raise ValueError('invalid underflow bracket')


def load_packet(path):
    p = Path(path)
    meta, rows = rom_results.decode((p / 'results.bin' if p.is_dir() else p).read_bytes())
    if len({key(r) for r in rows}) != len(rows):
        raise ValueError('duplicate descriptor')
    return meta, rows


def load(path):
    return load_packet(path)[1]


def compare(hardware, candidate):
    refs = defaultdict(list)
    counts = Counter(total=len(candidate), matches=0, mismatches=0, missing_results=0,
                     invalid_captures=0, no_identical_bracket=0, unstable_reference=0)
    for r in hardware:
        try:
            validate(r)
        except ValueError:
            counts['invalid_captures'] += 1
            continue
        refs[key(r)[:-1] + brackets(r)].append(r)
    counts['missing_results'] = len({key(r) for r in hardware} - {key(r) for r in candidate})
    groups = defaultdict(list)
    for r in candidate:
        try:
            validate(r)
        except ValueError:
            counts['invalid_captures'] += 1
            continue
        rows = refs.get(key(r)[:-1] + brackets(r), [])
        if not rows:
            counts['no_identical_bracket'] += 1
            continue
        values = {measures(x) for x in rows}
        if len(values) != 1:
            counts['unstable_reference'] += 1
            continue
        expected = next(iter(values))
        actual = measures(r)
        counts['matches' if expected == actual else 'mismatches'] += 1
        if expected != actual:
            groups[(r['variant'], expected, actual)].append(dict(case=key(r), brackets=brackets(r)))
    return dict(counts=dict(counts), units='observed Timer-A underflows; exact brackets; no alignment',
                groups=[dict(variant=v, expected=e, actual=a, count=len(rows),
                             first_divergent_snapshot=next(i for i in range(3) if e[i] != a[i]),
                             representatives=rows[:3]) for (v,e,a),rows in
                        sorted(groups.items(), key=lambda x: (-len(x[1]), x[0]))])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hardware', type=Path, action='append', required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--case', help='comma-separated six-field descriptor; return full records')
    a = p.parse_args()
    packets = [load_packet(path) for path in a.hardware]
    cm, candidate = load_packet(a.candidate)
    if len({m['source_id'] for m, _ in packets} | {cm['source_id']}) != 1:
        p.error('source_id mismatch; compare only the identical ROM experiment')
    hw = [r for _, rows in packets for r in rows]
    report = compare(hw, candidate)
    if a.case:
        selected = tuple(int(x, 0) for x in a.case.split(','))
        report['detail'] = dict(hardware=[r for r in hw if key(r) == selected],
                                candidate=[r for r in candidate if key(r) == selected])
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(report['counts'], report=str(a.out))))

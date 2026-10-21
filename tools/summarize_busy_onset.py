"""Summarize kind89 busy sequences without converting samples into chip edges."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rom_results


def summarize(rows):
    counts = Counter(cases=len(rows))
    groups = defaultdict(list)
    for row in rows:
        if row['kind'] != 89 or row['status'] != 0:
            raise ValueError('requires completed kind89 rows')
        busy = tuple(bool(row[field] & 0x4000)
                     for field in ('launch_ref', 'end_ref', 'irq_beam'))
        real = not row['variant'] & 8
        rises = any(not a and b for a, b in zip(busy, busy[1:]))
        counts['real' if real else 'inert'] += 1
        if real:
            counts['real_first_clear'] += not busy[0]
            counts['real_clear_to_busy'] += rises
            counts['real16_clear_to_busy'] += rises and row['target'] == 5
            counts['real_first_clear_last_D_still_zero'] += not busy[0] and row['icr'] == 0
        key = (row['target'], (row['variant'] >> 1) & 3, real,
               'ROM' if row['variant'] & 16 else 'chip', busy,
               row['icr'], row['irq_level'])
        groups[key].append(','.join(str(row[field]) for field in rom_results.FIELDS[:6]))
    patterns = [dict(count=len(ids), target=k[0], dma=k[1], real=k[2], first_read=k[3],
                     busy=list(k[4]), early_last_D=k[5], settled_D=k[6], representatives=ids[:3])
                for k, ids in sorted(groups.items(), key=lambda item: (-len(item[1]), str(item[0])))]
    return dict(counts=dict(counts), groups=patterns,
                units='Raw DMACONR bit14 and destination words; exact stored case IDs; no alignment.',
                interpretation='An observed clear-to-busy transition supports delayed assertion. '
                               'No transition alone does not prove completion; samples can miss an interval.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packet', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=3, choices=range(1, 9))
    args = parser.parse_args()
    _, rows = rom_results.decode(args.packet.read_bytes())
    report = summarize(rows)
    report['packet'] = str(args.packet.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(counts=report['counts'], groups=report['groups'][:args.limit],
                          full_report=str(args.out), interpretation=report['interpretation'])))

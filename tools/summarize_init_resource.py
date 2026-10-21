"""Compare kind90 Copper-state controls at exact launch cohorts; never align."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rom_results


def summarize(rows):
    cohorts = defaultdict(dict)
    for row in rows:
        if row['kind'] != 90 or row['status'] != 0:
            raise ValueError('requires completed kind90 results')
        mode = row['variant'] >> 8
        if mode not in range(3):
            raise ValueError('unknown Copper mode')
        key = (row['target'], row['variant'] & 255, row['phase'], row['delay'], row['repeat'])
        if mode in cohorts[key]:
            raise ValueError('duplicate mode in descriptor cohort')
        cohorts[key][mode] = row
    counts = Counter(cases=len(rows), descriptor_cohorts=len(cohorts), exact_launch_cohorts=0,
                     unmatched_launch_cohorts=0, race_cohorts=0, source_changes=0,
                     same_source_changed_observation=0)
    groups = defaultdict(list)
    for key, modes in cohorts.items():
        if set(modes) != {0, 1, 2}:
            raise ValueError('missing Copper control mode')
        ordered = [modes[i] for i in range(3)]
        if len({r['launch_beam'] for r in ordered}) != 1:
            counts['unmatched_launch_cohorts'] += 1
            continue
        counts['exact_launch_cohorts'] += 1
        # Controls remain in the full capture and comparator. Only actual
        # source races enter this cross-mode diagnostic.
        if key[0] != 3 or key[1] & 24:
            continue
        counts['race_cohorts'] += 1
        words = tuple(r['irq_level'] for r in ordered)
        observations = tuple((r['end_ref'] & 0x6000, r['counter'],
                              r['icr'] & 0x6000, r['irq_beam']) for r in ordered)
        changed_source = len(set(words)) != 1
        changed_observation = len(set(observations)) != 1
        counts['source_changes'] += changed_source
        counts['same_source_changed_observation'] += not changed_source and changed_observation
        signature = (words, observations)
        groups[signature].append(','.join(map(str, key)))
    patterns = [dict(count=len(ids), fetched_source=list(k[0]), observations=k[1],
                     representatives=ids[:3]) for k, ids in sorted(
                         groups.items(), key=lambda item: (-len(item[1]), str(item[0])))]
    return dict(counts=dict(counts), modes=['off', 'settled_WAIT', 'active'],
                groups=patterns, units='Raw words and packed beam samples; exact launch only.',
                cohort_id='target,variant_low8,phase,delay,repeat; retrieve each mode with variant_low8+(mode<<8)',
                interpretation='A source change constrains fetch/write ordering; unchanged source '
                               'with changed observations does not by itself prove identical engine timing.')


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
    print(json.dumps(dict(counts=report['counts'], modes=report['modes'],
                          groups=report['groups'][:args.limit], full_report=str(args.out))))

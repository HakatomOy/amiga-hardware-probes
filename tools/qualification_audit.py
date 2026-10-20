"""Summarize exact qualification coverage without aligning or changing captures."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import experiment as e


def audit(candidate, references, fields):
    def identity(row):
        return tuple(row[f] for f in e.rom_results.FIELDS[:6])

    tables = []
    for rows in references:
        table = {identity(r): r for r in rows}
        if len(table) != len(rows):
            raise ValueError('duplicate reference descriptor')
        tables.append(table)
    result = []
    for field in fields:
        pairs = Counter()
        missing = 0
        for row in candidate:
            for table in tables:
                reference = table.get(identity(row))
                if reference is None:
                    missing += 1
                else:
                    pairs[e.value(reference, field), e.value(row, field)] += 1
        result.append(dict(name=field.get('name', field['field']), unit=field['unit'],
                           matched=sum(n for (a, b), n in pairs.items() if a == b),
                           different=sum(n for (a, b), n in pairs.items() if a != b),
                           missing=missing,
                           pairs=[dict(hardware=a, candidate=b, count=n)
                                  for (a, b), n in pairs.most_common()]))
    support = []
    for rows in [candidate, *references]:
        cohorts = defaultdict(set)
        for row in rows:
            cohorts[identity(row)[:-1]].add(tuple(e.value(row, f) for f in fields))
        support.append(dict(Counter(map(len, cohorts.values()))))
    return dict(fields=result, qualification_cohorts_per_condition=support,
                rule='Same descriptor, raw declared units; no offsets, scaling or time alignment. '
                     'Support counts do not imply overlapping cohorts or qualify measurements.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    spec = e.read(args.run / 'experiment.json')
    report = e.read(args.run / 'comparison.json')
    candidate_path = args.run / 'candidate/results.bin'
    paths = [Path(ref) / 'results.bin' for ref in report['references']]
    candidate = e.rom_results.decode(candidate_path.read_bytes())[1]
    references = [e.rom_results.decode(p.read_bytes())[1] for p in paths]
    result = audit(candidate, references, spec['comparison']['qualification'])
    result['packet_sha256'] = [e.digest(p.read_bytes()) for p in [candidate_path, *paths]]
    e.write(args.out, result)
    print(json.dumps({**result, 'fields': [{**f, 'pairs': f['pairs'][:3]}
                                         for f in result['fields']], 'detail': str(args.out)}))


if __name__ == '__main__':
    main()

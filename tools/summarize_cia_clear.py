"""Summarize qualified kind85 ICR-clear/PB-control evidence; never align clocks."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import experiment as e


def summarize(cases, measurements):
    indices = {f['name']: i for i, f in enumerate(measurements)}
    requests = [indices[n] for n in ('Paula_request', 'request1', 'request2', 'request3')]
    counts = Counter()
    examples = []
    for key, case in sorted(cases.items()):
        if case['case'][0] != 85:
            raise ValueError('requires kind85 clear experiment')
        if case['status'] not in ('matches', 'mismatches'):
            counts['unqualified'] += 1
            continue
        counts['qualified'] += 1
        counts['model_mismatches'] += case['status'] == 'mismatches'
        vector = case['expected']
        if not case['case'][3] & 8:
            counts['PB_control'] += 1
            counts['PB_control_request_observed'] += any(vector[i] for i in requests)
            continue
        counts['ICR_clear'] += 1
        if vector[indices['CIA_snapshot']] & 0x80:
            counts['ICR_asserted'] += 1
            reasserts = any(vector[i] for i in requests)
            counts['asserted_then_ack_reasserts' if reasserts else 'asserted_then_ack_stays_clear'] += 1
            if len(examples) < 3:
                examples.append(dict(case=key, icr=vector[indices['CIA_snapshot']],
                                     requests=[vector[i] for i in requests]))
        else:
            counts['ICR_not_asserted'] += 1
    discriminating = (counts['ICR_asserted'] > 0 and counts['ICR_not_asserted'] > 0
                      and counts['PB_control_request_observed'] > 0 and counts['unqualified'] == 0)
    return dict(counts=dict(counts), discriminating=discriminating, examples=examples,
                rule='Stable exact qualification only; ICR bit7 is a software observation, '
                     'not an electrical pin timestamp. No request in this window does not '
                     'rule out every shorter pending pulse or locate the physical stage.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = summarize(e.read(args.run / 'cases.json'),
                       e.read(args.run / 'experiment.json')['comparison']['measurements'])
    e.write(args.out, result)
    print(json.dumps({**result, 'detail': str(args.out)}))


if __name__ == '__main__':
    main()

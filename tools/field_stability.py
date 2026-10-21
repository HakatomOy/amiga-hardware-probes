"""Report per-field repeated HW agreement without weakening case acceptance."""
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import json
from tools import experiment as e


def summarize(reference_runs, candidate, policy):
    cohorts = defaultdict(list)
    owners = defaultdict(set)
    def cohort(row):
        return e.key(row)[:-1] + tuple(e.value(row, f) for f in policy['qualification'])
    for index, rows in enumerate(reference_runs):
        for row in rows:
            key = cohort(row)
            cohorts[key].append(row)
            owners[key].add(index)
    report = {}
    for field in policy['measurements']:
        counts = Counter()
        examples = []
        for row in candidate:
            key = cohort(row)
            values = {e.value(r, field) for r in cohorts[key]}
            actual = e.value(row, field)
            if len(owners[key]) < 2:
                status = 'insufficient_independent_repeats'
            elif len(values) > 1:
                status = 'unstable'
            else:
                status = 'match' if actual in values else 'mismatch'
            counts[status] += 1
            if status == 'mismatch' and len(examples) < 2:
                examples.append(dict(case=','.join(map(str,e.key(row))),
                                     hardware=sorted(values), candidate=actual))
        report[field.get('name',field['field'])] = dict(unit=field['unit'], counts=dict(counts), examples=examples)
    return dict(diagnostic_only=True, acceptance_contract_changed=False, alignment='exact',
                reference_runs=len(reference_runs), fields=report)


def run(path):
    spec = e.read(path/'experiment.json')
    build = e.read(path/'rom/manifest.json')
    comparison = e.read(path/'comparison.json')
    refs = [e.load_capture(e.resolve(p),build,spec['capture'],reference=True)[1]
            for p in comparison['references']]
    candidate = e.load_capture(path/'candidate',build,spec['capture'])[1]
    return summarize(refs,candidate,spec['comparison'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('run',type=Path)
    p.add_argument('--fields',required=True,help='Comma-separated measurement names; at most eight')
    a=p.parse_args()
    try:
        names=a.fields.split(',')
        if not 1<=len(names)<=8:raise ValueError('select one through eight fields')
        report=run(a.run)
        if set(names)-report['fields'].keys():raise ValueError('unknown measurement field')
        e.write(a.run/'field-stability-diagnostic.json',report)
        print(json.dumps(dict(report,fields={n:report['fields'][n] for n in names},detail=str(a.run/'field-stability-diagnostic.json'))))
    except (OSError,ValueError,KeyError) as error:
        p.exit(1,json.dumps(dict(status='invalid_field_diagnostic',error=str(error)[:400]))+'\n')

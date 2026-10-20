"""Bounded baseline-delta packets; derived cache never authorizes a capture."""
import hashlib
import json
from pathlib import Path
import uuid


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_bytes(canonical(value) + b'\n')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def families(report, scope):
    """IDs describe exact signatures within a contract, not inferred causes."""
    result = {}
    for group in report.get('groups', []):
        identity = sha(canonical(dict(version=1, scope=scope, pattern=group['pattern'])))
        result['F-' + identity] = group
    return result


def comparison_contract(comparison):
    # A hypothesis's acceptance target does not change measured signatures.
    return {k:v for k,v in comparison.items() if k != 'required_field_repairs'}


def family_delta(report, previous, scope):
    current, prior = families(report, scope), families(previous, scope)
    changed = []
    unchanged_groups = unchanged_cases = 0
    for identity in sorted(current.keys() | prior.keys()):
        after, before = current.get(identity), prior.get(identity)
        count, old = (after or {}).get('count', 0), (before or {}).get('count', 0)
        if after is not None and before is not None and count == old:
            unchanged_groups += 1
            unchanged_cases += count
            continue
        change = 'new' if before is None else 'resolved' if after is None else 'count_changed'
        changed.append(dict(id=identity, change=change, before=old, after=count,
                            pattern=(after or before)['pattern'],
                            first_divergent_field=(after or before).get('first_divergent_field'),
                            shared_conditions=(after or before).get('shared_conditions', {}),
                            representatives=(after or before).get('representatives', [])[:3]))
    changed.sort(key=lambda g: (-abs(g['after'] - g['before']), g['id']))
    return dict(changed=changed, unchanged_groups=unchanged_groups,
                unchanged_cases=unchanged_cases)


def packet(run, cache, baseline=None, limit=5, refresh=False):
    if not 1 <= limit <= 16:
        raise ValueError('evidence limit must be between 1 and 16')
    run = Path(run).resolve()
    paths = [run / name for name in ('summary.json', 'comparison.json', 'experiment.json')]
    if baseline:
        baseline = Path(baseline).resolve()
        paths += [baseline / name for name in ('comparison.json', 'experiment.json')]
        paths += [run/'cases.json', baseline/'cases.json']
    # Hash full inputs, not timestamps. Analyzer changes invalidate derived output
    # independently of the replay cache. Cache payloads are verified on every hit.
    signature = dict(version=1, limit=limit, baseline=str(baseline) if baseline else None,
                     analyzer=sha(Path(__file__).read_bytes()),
                     comparator=sha(Path(__file__).with_name('experiment.py').read_bytes()),
                     inputs={str(p): sha(p.read_bytes()) for p in paths})
    key = sha(canonical(signature))
    entry = Path(cache) / 'evidence' / (key + '.json')
    reused = False
    if not refresh and entry.is_file():
        try:
            stored = read(entry)
            reused = (stored['signature'] == signature
                      and stored['sha256'] == sha(canonical(stored['packet'])))
        except (ValueError, KeyError, TypeError, OSError):
            reused = False
    if reused:
        result = stored['packet']
    else:
        summary, report, spec = (read(p) for p in paths[:3])
        case_delta = report.get('delta')
        scope = dict(experiment=spec['id'], comparison=comparison_contract(spec['comparison']))
        if baseline:
            previous, prior_spec = (read(p) for p in paths[3:5])
            if (prior_spec['id'] != spec['id']
                    or comparison_contract(prior_spec['comparison']) != comparison_contract(spec['comparison'])):
                raise ValueError('baseline comparison contract differs')
            if (not report.get('reference_hashes')
                    or previous.get('reference_hashes') != report['reference_hashes']):
                raise ValueError('baseline hardware reference hashes differ or are missing')
            changes = family_delta(report, previous, scope)
            from tools.experiment import delta
            case_delta = delta(read(paths[6]), read(paths[5]),
                               [f.get('name', f['field']) for f in spec['comparison']['measurements']])
        else:
            changes = report.get('family_delta')
            if changes is None:
                changes = family_delta(report, {}, scope)
        changed = changes['changed']
        result = dict(schema_version=1, status=summary['status'], identity=summary.get('identity'),
                      comparison_baseline=str(baseline) if baseline else spec.get('baseline'),
                      counts=report['counts'], delta=(case_delta or {}).get('counts'),
                      changed_case_examples={k: v[:3] for k, v in
                          (case_delta or {}).get('representatives', {}).items()
                          if k not in ('unchanged_matches', 'unchanged_differences')},
                      alignment=report.get('alignment'), repeatability=report.get('repeatability'),
                      changed_families=changed[:limit], changed_family_count=len(changed),
                      unchanged_families=changes['unchanged_groups'],
                      unchanged_family_cases=changes['unchanged_cases'],
                      measurement_units=[dict(name=f.get('name', f['field']), unit=f['unit'])
                                         for f in spec['comparison']['measurements']],
                      qualification=[{k: v for k, v in f.items() if k != 'meaning'}
                                     for f in spec['comparison']['qualification']],
                      references=report.get('references', []),
                      details=dict(run=str(run), comparison=str(run/'comparison.json'),
                                   contract=str(run/'experiment.json'),
                                   cases=str(run/'cases.json'),
                                   command=['python', 'tools/experiment.py', 'detail', str(run),
                                            '--case', 'CASE_ID', '--window', '6']),
                      note='Family IDs are exact signatures, not proven common causes. '
                           'Unchanged counts can hide changed membership; inspect case deltas too.')
        for family in result['changed_families']:
            family['detail_run'] = (str(baseline) if baseline else None) if family['change'] == 'resolved' else str(run)
            if family['change'] == 'resolved' and not baseline:
                family['baseline_capture'] = spec.get('baseline')
        write(entry, dict(signature=signature, packet=result, sha256=sha(canonical(result))))
    exported = dict(result, cache=dict(key=key, reused=reused, entry=str(entry)))
    write(run/'evidence.json', exported)
    return exported

#!/usr/bin/env python3
"""File-backed experiment batches, exact comparisons, and bounded agent reports."""
import argparse
import contextlib
from collections import Counter, defaultdict
from itertools import zip_longest
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import rom_results
from tools import evidence

DESCRIPTOR = rom_results.FIELDS[:6]
TIERS = ('focused', 'neighbor', 'broad')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def replay_fingerprint(identity, seconds, inputs):
    """Capture behavior only: report/qualification edits do not invalidate replay."""
    return dict(identity=identity, seconds=seconds, capture_adapter_version=1,
                decoder_sha256=digest(Path(rom_results.__file__).read_bytes()),
                capture_tool_sha256=digest((ROOT/'run_rom.py').read_bytes())
                if (ROOT/'run_rom.py').exists() else None, inputs=inputs)


def resolve(value):
    p = Path(value)
    return (p if p.is_absolute() else ROOT / p).resolve()


def key(row):
    return tuple(row[f] for f in DESCRIPTOR)


def value(row, field):
    result = row[field['field']] >> field.get('shift', 0)
    return result & field.get('mask', 0xffffffff)


def validate_spec(spec):
    if spec.get('version') != 1 or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', spec.get('id', '')):
        raise ValueError('version=1 and a lowercase experiment id are required')
    for name in ('hypothesis', 'competitor', 'test', 'next_question'):
        if not isinstance(spec.get(name), str) or not spec[name].strip():
            raise ValueError(f'missing experiment uncertainty: {name}')
    if len(spec.get('outcomes', {})) < 2 or not all(spec['outcomes'].values()):
        raise ValueError('declare at least two possible outcomes and their implications')
    if spec.get('purpose', 'investigation') not in ('investigation', 'regression'):
        raise ValueError('unknown experiment purpose')
    if spec.get('purpose') == 'regression' and not (spec.get('baseline') and spec.get('references')):
        raise ValueError('regression replay requires a frozen baseline and saved references')
    capture = spec['capture']
    if capture['minimum_seconds'] <= 0 or capture['expected_cases'] <= 0:
        raise ValueError('positive minimum duration and expected case count required')
    if capture.get('validator') not in (None, 'serial', 'irq', 'handoff','bus'):
        raise ValueError('unknown capture validator')
    if capture.get('status_is_measurement') and capture.get('validator')!='bus':
        raise ValueError('overloaded status data requires the bus domain validator')
    comparison = spec['comparison']
    if comparison.get('alignment') != 'exact' or not comparison.get('measurements'):
        raise ValueError('explicit measurements and exact alignment required')
    required = comparison.get('required_field_repairs', {})
    names = {f.get('name',f['field']) for f in comparison['measurements']}
    if (not isinstance(required, dict)
            or any(k not in names or type(v) is not int or v < 1 for k,v in required.items())
            or (required and not spec.get('baseline'))):
        raise ValueError('required_field_repairs needs a baseline and positive counts for declared measurements')
    known = set(rom_results.FIELDS) - {'pc_hi', 'pc_lo'} | {'saved_pc_offset', 'reference_ticks'}
    for f in comparison['measurements'] + comparison['qualification'] + capture.get('coverage',[]):
        if f['field'] not in known or not f.get('unit') or not f.get('meaning'):
            raise ValueError('each measured/qualification field requires a valid field, unit and meaning')
        if f.get('shift', 0) not in range(32) or not 0 <= f.get('mask', 0xffffffff) <= 0xffffffff:
            raise ValueError('invalid field mask/shift')
        if f.get('pattern', 'values') not in ('values', 'delta'):
            raise ValueError('pattern must be values or delta; deltas never align captures')
    for rule in capture.get('coverage',[]):
        if not rule.get('require_values') or any(k not in DESCRIPTOR for k in rule.get('where',{})):
            raise ValueError('coverage requires values and optional descriptor-only conditions')
        for condition in rule.get('where', {}).values():
            if isinstance(condition, dict):
                if (set(condition) != {'mask', 'equals'}
                        or not all(isinstance(v, int) and 0 <= v <= 65535 for v in condition.values())
                        or condition['equals'] & ~condition['mask']):
                    raise ValueError('masked coverage condition requires mask and equals within descriptor bits')
            elif not isinstance(condition, int):
                raise ValueError('coverage conditions must be integers or mask/equals objects')
    if spec.get('traces') and not spec['traces'].get('unit'):
        raise ValueError('trace time unit must be explicit')
    names = [f.get('name', f['field']) for f in comparison['measurements']]
    if len(names) != len(set(names)):
        raise ValueError('measurement names must be unique')
    for command in spec.get('build', []) + spec.get('validation', []):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', command.get('name', '')):
            raise ValueError('command needs a safe name')
        if not command.get('argv') or not all(isinstance(x, str) for x in command['argv']):
            raise ValueError('commands must be argument arrays, never shell strings')
        if command.get('cache') and (not command.get('inputs') or not command.get('outputs')):
            raise ValueError('cached commands require explicit input globs and output files')
    commands = spec.get('build', []) + spec.get('validation', [])
    if len({x['name'] for x in commands}) != len(commands):
        raise ValueError('command names must be unique')
    tiers = [TIERS.index(c['tier']) for c in spec.get('validation', [])]
    if tiers != sorted(tiers):
        raise ValueError('validation must run focused, neighbor, then broad')
    return spec


def load_capture(path, build, contract, reference=False):
    path = Path(path)
    data = (path / 'results.bin' if path.is_dir() else path).read_bytes()
    meta, rows = rom_results.decode(data)
    if meta['source_id'] != build['source_id']:
        raise ValueError(f'{path}: source_id mismatch')
    if len(rows) != contract['expected_cases'] or len(rows) != build['trial_count']:
        raise ValueError(f'{path}: wrong case count')
    if [list(key(r)) for r in rows] != build['trials'] or len({key(r) for r in rows}) != len(rows):
        raise ValueError(f'{path}: descriptor mismatch or duplicates')
    if contract.get('status_is_measurement') and any(r['kind']!=55 for r in rows):
        raise ValueError('status-as-measurement is only defined for kind55')
    if not contract.get('status_is_measurement') and any(r['status'] not in contract.get('valid_statuses', [0]) for r in rows):
        raise ValueError(f'{path}: invalid capture status')
    if contract.get('validator'):
        import importlib
        module = importlib.import_module({'serial': 'compare_serial_buffer', 'irq': 'compare_irq_stage','bus':'compare_bus_marker',
                                         'handoff': 'compare_handoff_focus'}[contract['validator']])
        if contract['validator']=='bus':module.load(path)
        else:
            for row in rows:module.validate(row)
    if reference:
        provenance = read(path / 'manifest.json')
        for f, expected in (('source_id', build['source_id']), ('test_rom_sha256', build['rom_sha256']),
                            ('results_sha256', digest(data))):
            if provenance.get(f) != expected:
                raise ValueError(f'{path}: reference {f} mismatch')
        if not all(provenance.get(f) for f in ('hardware', 'capture_method', 'repeatability')):
            raise ValueError(f'{path}: reference provenance incomplete')
        restoration = provenance.get('restoration', {})
        if not restoration.get('restored_verified') or not restoration.get('reset_release_verified') or restoration.get('errors'):
            raise ValueError(f'{path}: unverified hardware restoration')
    return meta, rows


def check_coverage(rows,contract):
    report=[]
    for rule in contract.get('coverage',[]):
        selected=[r for r in rows if all(
            (r[k] & v['mask'] == v['equals']) if isinstance(v, dict) else r[k] == v
            for k,v in rule.get('where',{}).items())]
        distribution=Counter(value(r,rule) for r in selected)
        unexpected = set(distribution) - set(rule.get('allowed_values', distribution))
        if unexpected:
            raise ValueError(f"capture coverage control {rule['field']} has unexpected values {sorted(unexpected)}")
        required=rule['require_values']
        missing=[x for x in required if x not in distribution]
        if missing:
            raise ValueError(f"capture coverage missing {rule['field']} values {missing}; revise the observer or coverage contract")
        report.append(dict(field=rule['field'],unit=rule['unit'],selected_cases=len(selected),
                           where=rule.get('where',{}),required_counts={x:distribution[x] for x in required}))
    return report


def repeat_cohorts(runs, candidate, policy):
    """Separate within-run repeats from independently recaptured phase cohorts."""
    def cohort(r):
        return key(r)[:-1] + tuple(value(r, f) for f in policy['qualification'])
    owners = defaultdict(set)
    for index, rows in enumerate(runs):
        for row in rows:
            owners[cohort(row)].add(index)
    independently_repeated = {k for k, indices in owners.items() if len(indices) > 1}
    return dict(reference_cohorts=len(owners),
                independently_repeated_cohorts=len(independently_repeated),
                candidate_cases_with_independent_repeats=sum(cohort(r) in independently_repeated for r in candidate),
                note='Zero conflicts does not establish cross-run repeatability when phase cohorts do not overlap.')


def compare(hardware, candidate, policy):
    """Only compare identical descriptor/qualification cohorts; never shift time."""
    fields = policy['measurements']
    def measured(r):
        return tuple(value(r, f) for f in fields)
    def cohort(r):
        return key(r)[:-1] + tuple(value(r, f) for f in policy['qualification'])
    refs = defaultdict(list)
    for r in hardware:
        refs[cohort(r)].append(r)
    cases = {}
    groups = defaultdict(list)
    counts = Counter(total=len(candidate), matches=0, mismatches=0, missing_results=0,
                     excluded=0, unstable_reference=0, invalid_captures=0)
    counts['reference_conflicting_cohorts'] = sum(len({measured(r) for r in rows}) > 1 for rows in refs.values())
    expected_keys = {key(r) for r in hardware}
    counts['missing_results'] = len(expected_keys - {key(r) for r in candidate})
    for r in candidate:
        k = ','.join(map(str, key(r)))
        detail = dict(case=key(r), candidate=r, qualification=cohort(r)[5:])
        reference = refs.get(cohort(r), [])
        observations = {measured(x) for x in reference}
        if not observations:
            status = 'excluded'
        elif len(observations) > 1:
            status = 'unstable_reference'
        else:
            expected = next(iter(observations))
            actual = measured(r)
            status = 'matches' if expected == actual else 'mismatches'
            detail['expected'] = expected
            detail['actual'] = actual
            if expected != actual:
                pattern = tuple((f.get('name', f['field']),
                                 ('delta', a-e) if f.get('pattern') == 'delta' else ('values', e, a), f['unit'])
                                for f, e, a in zip(fields, expected, actual) if e != a)
                detail['first_divergent_field'] = pattern[0][0]
                groups[pattern].append(k)
        detail.update(status=status, hardware=reference)
        cases[k] = detail
        counts[status] += 1
    return dict(counts=dict(counts), alignment='exact',
                groups=[dict(count=len(ids), pattern=p, representatives=ids[:3],
                             shared_conditions={f: cases[ids[0]]['candidate'][f] for f in DESCRIPTOR
                                 if len({cases[i]['candidate'][f] for i in ids}) == 1},
                             first_divergent_field=p[0][0]) for p, ids in
                        sorted(groups.items(), key=lambda item: (-len(item[1]), repr(item[0])))]), cases


def delta(before, after, names=()):
    counts = Counter(repairs=0, regressions=0, unchanged_differences=0,
                     changed_differences=0, unchanged_matches=0, excluded_cases=0,
                     qualification_regressions=0, new_cases=0, missing_results=0)
    counts.update(field_repairs=0,field_regressions=0,cases_with_field_regressions=0)
    field_repairs=Counter();field_regressions=Counter()
    examples = defaultdict(list)
    for k in sorted(before.keys() | after.keys()):
        a, b = before.get(k), after.get(k)
        if (a and b and a['status'] in ('matches','mismatches') and b['status'] in ('matches','mismatches')
                and a['qualification']==b['qualification'] and a['expected']==b['expected']):
            regressed=False
            for i,(expected,old,new) in enumerate(zip(a['expected'],a['actual'],b['actual'])):
                label=names[i] if i<len(names) else str(i)
                if old!=expected and new==expected:field_repairs[label]+=1;counts['field_repairs']+=1
                if old==expected and new!=expected:
                    field_regressions[label]+=1;counts['field_regressions']+=1;regressed=True
            counts['cases_with_field_regressions']+=regressed
        if b is None:
            category = 'missing_results'
        elif a is None:
            category = 'new_cases'
        elif b['status'] not in ('matches', 'mismatches'):
            category = 'excluded_cases'
            if a['status'] in ('matches', 'mismatches'):
                counts['qualification_regressions'] += 1
        elif a['status'] not in ('matches', 'mismatches'):
            category = 'new_cases'
        elif a['qualification'] != b['qualification'] or a['expected'] != b['expected']:
            # Changing a timing bracket is evidence, never an automatic repair.
            category = 'qualification_regressions'
        elif a['status'] == 'matches':
            category = 'unchanged_matches' if b['status'] == 'matches' else 'regressions'
        elif b['status'] == 'matches':
            category = 'repairs'
        else:
            category = 'unchanged_differences' if a['actual'] == b['actual'] else 'changed_differences'
        counts[category] += 1
        if len(examples[category]) < 3:
            examples[category].append(k)
    return dict(counts=dict(counts), representatives=dict(examples),
                repaired_fields=dict(field_repairs),regressed_fields=dict(field_regressions))


def require_repairs(spec, report):
    repairs = report.get('delta', {}).get('repaired_fields', {})
    unmet = {name: dict(required=count, observed=repairs.get(name, 0))
             for name,count in spec['comparison'].get('required_field_repairs', {}).items()
             if repairs.get(name, 0) < count}
    if unmet:
        raise ValueError('declared repair target not met; broader validation not run: '
                         + json.dumps(unmet, sort_keys=True))


def bounded_failure(stdout, stderr):
    """Find the first diagnostic, not an arbitrary tail; never read logs into output."""
    lines = []
    failed_tests = []
    for path in (stderr, stdout):
        with Path(path).open(encoding='utf-8', errors='replace') as stream:
            prefix = []
            selected = None
            for line in stream:
                line = line.rstrip()[:300]
                failed = re.match(r'^(?:FAILED (\S+)|test (.+) \.\.\. FAILED)$', line)
                if failed:
                    name = next(group for group in failed.groups() if group)
                    if name not in failed_tests:
                        failed_tests.append(name)
                if len(prefix) < 5:
                    prefix.append(line)
                if selected is None and re.search(r'error|failed|exception|panic|assert', line, re.I):
                    selected = [line]
                elif selected is not None and len(selected) < 6:
                    selected.append(line)
            lines.extend(selected or prefix)
    names = []
    used = 0
    for name in failed_tests:
        if used + len(name) + 1 > 800:
            break
        names.append(name)
        used += len(name) + 1
    header = (f'Failed tests ({len(failed_tests)}; listed {len(names)}):\n'
              + '\n'.join(names) + '\n') if failed_tests else ''
    return (header + '\n'.join(dict.fromkeys(lines)))[:1800]


def fingerprints(patterns, variables):
    result = {}
    for pattern in patterns:
        expanded = pattern.format_map(variables)
        matches = sorted(glob.glob(str(resolve(expanded)), recursive=True))
        files = [Path(p) for p in matches if Path(p).is_file()]
        if not files:
            raise ValueError(f'fingerprint input matches no files: {expanded}')
        for p in files:
            result[str(p.resolve())] = digest(p.read_bytes())
    return result


def command_run(spec, out, variables, cache):
    name = spec['name']
    argv = [part.format_map(variables) for part in spec['argv']]
    workdir = resolve(spec.get('cwd', '.').format_map(variables))
    # Environment changes invalidate reuse, but values (possibly credentials)
    # are represented only by a hash in file-backed provenance.
    environment = dict(os.environ, **spec.get('env', {}))
    signature = dict(argv=argv, cwd=str(workdir),
                     environment_sha256=digest(json.dumps(environment, sort_keys=True).encode()))
    launcher = shutil.which(argv[0], path=environment.get('PATH'))
    if launcher and Path(launcher).is_file():
        signature['launcher_sha256'] = digest(Path(launcher).read_bytes())
    if len(argv) > 1 and argv[1].endswith('.py'):
        script = Path(argv[1])
        script = script if script.is_absolute() else workdir / script
        if script.is_file():
            signature['script_sha256'] = digest(script.read_bytes())
    if spec.get('cache'):
        signature['inputs'] = fingerprints(spec['inputs'], variables)
        outputs = [resolve(p.format_map(variables)) for p in spec['outputs']]
        cache_key = digest(json.dumps(signature, sort_keys=True).encode())
        cache_file = cache / (name + '-' + cache_key + '.json')
        if cache_file.exists() and all(p.is_file() for p in outputs):
            prior = read(cache_file)
            hashes = {str(p): digest(p.read_bytes()) for p in outputs}
            if hashes == prior['outputs']:
                result = dict(name=name, exit=0, reused=True, duration=0, provenance=str(cache_file))
                write(out / (name + '.command.json'), result)
                return result
    stdout, stderr = out / (name + '.stdout.log'), out / (name + '.stderr.log')
    started = time.monotonic()
    with stdout.open('w', encoding='utf-8') as left, stderr.open('w', encoding='utf-8') as right:
        try:
            options = dict(creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW) if os.name == 'nt' else dict(start_new_session=True)
            proc = subprocess.Popen(argv, cwd=workdir, env=environment, stdout=left, stderr=right,
                                    stdin=subprocess.DEVNULL, shell=False, **options)
            try:
                code = proc.wait(timeout=spec.get('timeout_seconds', 3600))
            except subprocess.TimeoutExpired:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                                   stdout=left, stderr=right, check=False)
                else:
                    os.killpg(proc.pid, signal.SIGKILL)
                if proc.poll() is None:
                    proc.kill()
                proc.wait()
                right.write('Command timed out; owned process tree terminated.\n')
                code = 124
        except OSError as error:
            right.write(str(error))
            code = 127
    result = dict(name=name, exit=code, duration=round(time.monotonic()-started, 2),
                  stdout=str(stdout), stderr=str(stderr), signature=signature, reused=False)
    if code:
        result['excerpt'] = bounded_failure(stdout, stderr)
    elif spec.get('cache'):
        # Source changes during a build cannot seed a reusable artifact.
        if fingerprints(spec['inputs'], variables) != signature['inputs']:
            raise ValueError(f'{name}: inputs changed during command')
        hashes = {str(p): digest(p.read_bytes()) for p in outputs}
        write(cache_file, dict(outputs=hashes, command=result))
    write(out / (name + '.command.json'), result)
    return result


def emit(out, stage, details, live=False):
    event = dict(stage=stage, **details)
    write(out / 'status.json', event)
    with (out / 'events.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(event) + '\n')
    if live:
        print(json.dumps(event), flush=True)


def stalled(record, spec):
    return (spec.get('purpose') != 'regression'
            and record.get('no_new_evidence', 0) >= 2
            and record.get('hypothesis') == spec['hypothesis']
            and record.get('test') == spec['test']
            and record.get('smaller_reproducer') == spec.get('smaller_reproducer'))


def run(spec_path, out, hardware=False, events=False, through='broad', overrides=None):
    spec = validate_spec(read(spec_path))
    spec.update(overrides or {})
    if hardware and spec.get('purpose') == 'regression':
        raise ValueError('regression replay cannot request new hardware; use an investigation')
    record_path = resolve(spec['investigation'])
    record = read(record_path) if record_path.exists() else {}
    if stalled(record, spec):
        raise ValueError('two runs added no evidence; revise hypothesis/test or identify a smaller reproducer')
    out = resolve(out)
    out.mkdir(parents=True, exist_ok=False)
    write(out / 'experiment.json', spec)
    variables = dict(root=str(ROOT), out=str(out), python=sys.executable)
    variables.update({k: str(resolve(spec[k])) for k in ('binary', 'romdir', 'config')})
    cache = ROOT / 'captures/.experiment-cache'
    summary = dict(experiment=spec['id'], status='failed', output=str(out), commands=[])
    try:
        for command in spec.get('build', []):
            result = command_run(command, out, variables, cache)
            summary['commands'].append(result)
            emit(out, 'build', {k: result[k] for k in ('name', 'exit', 'reused')}, events)
            if result['exit']:
                raise ValueError(f"{result['name']} failed: {result.get('excerpt', '')}")
        romdir = Path(variables['romdir'])
        build = read(romdir / 'manifest.json')
        if digest((romdir / 'a500-timing-rom.bin').read_bytes()) != build['rom_sha256']:
            raise ValueError('ROM hash differs from build manifest')
        if spec.get('rom_sha256', build['rom_sha256']) != build['rom_sha256']:
            raise ValueError('experiment pins a different ROM')
        if build['trial_count'] != spec['capture']['expected_cases']:
            raise ValueError('manifest expected case count differs from built ROM')
        frozen_rom = out / 'rom'
        frozen_rom.mkdir()
        for name in ('manifest.json', 'a500-timing-rom.bin', 'a500-timing-rom-onerom.bin'):
            if (romdir / name).exists():
                shutil.copyfile(romdir / name, frozen_rom / name)
        if digest((frozen_rom / 'a500-timing-rom.bin').read_bytes()) != build['rom_sha256']:
            raise ValueError('ROM changed during snapshot')
        write(frozen_rom / 'manifest.json', build)
        romdir = frozen_rom
        binary = out / 'emulator.exe'
        shutil.copy2(variables['binary'], binary)
        config = out / 'machine.toml'
        shutil.copyfile(variables['config'], config)
        summary['identity'] = dict(binary_sha256=digest(binary.read_bytes()),
                                   config_sha256=digest(config.read_bytes()),
                                   rom_sha256=build['rom_sha256'], source_id=build['source_id'])
        variables.update(binary=str(binary), config=str(config), romdir=str(romdir))
        write(out / 'build-manifest.json', build)
        seconds = max(spec['capture']['minimum_seconds'], spec['capture'].get('seconds', 0))
        capture_cmd = dict(name='preflight', argv=['{python}', '{root}/run_rom.py', '--binary', '{binary}',
                           '--config', '{config}', '--romdir', '{romdir}', '--out', '{out}/candidate',
                           '--seconds', str(seconds)], timeout_seconds=spec['capture'].get('timeout_seconds', 900))
        replay_contract = replay_fingerprint(summary['identity'], seconds,
                          fingerprints(spec.get('replay_inputs', []), variables))
        replay_key = digest(json.dumps(replay_contract, sort_keys=True).encode())
        replay_cache = cache / ('replay-' + replay_key)
        reused_capture = spec.get('reuse_preflight', False) and (replay_cache/'results.bin').exists()
        if reused_capture:
            origin = read(replay_cache/'origin.json')
            if origin.get('capture_contract') != replay_contract:
                raise ValueError('cached capture contract differs')
            if read(replay_cache/'build-manifest.json') != build:
                raise ValueError('cached build metadata differs')
            load_capture(replay_cache, build, spec['capture'])
            if read(replay_cache/'origin.json')['results_sha256'] != digest((replay_cache/'results.bin').read_bytes()):
                raise ValueError('cached preflight packet hash mismatch')
            (out / 'candidate').mkdir()
            shutil.copyfile(replay_cache / 'results.bin', out / 'candidate/results.bin')
            write(out / 'candidate/build-manifest.json', build)
            write(out / 'candidate/reuse.json', dict(original=read(replay_cache/'origin.json'),
                                                    identity=summary['identity']))
        else:
            result = command_run(capture_cmd, out, variables, cache)
            summary['commands'].append(result)
            if result['exit']:
                raise ValueError(f"preflight failed: {result.get('excerpt', '')}")
        _, candidate = load_capture(out / 'candidate', build, spec['capture'])
        if spec.get('reuse_preflight', False) and not reused_capture:
            replay_cache.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(out / 'candidate/results.bin', replay_cache / 'results.bin')
            write(replay_cache / 'build-manifest.json', build)
            write(replay_cache / 'origin.json', dict(run=str(out), identity=summary['identity'],
                                                    capture_contract=replay_contract,
                                                    results_sha256=digest((out/'candidate/results.bin').read_bytes())))
        coverage=check_coverage(candidate,spec['capture'])
        emit(out, 'preflight', dict(cases=len(candidate), seconds=seconds, reused=reused_capture,coverage=coverage), events)
        if through=='preflight':
            summary.update(status='preflight',counts=dict(cases=len(candidate),complete=True),
                           next_step='Preflight complete; continue with saved references or a planned hardware run.')
            write(out/'summary.json',summary);emit(out,'complete',compact(summary),events)
            return summary
        references = [resolve(p) for p in spec.get('references', [])]
        if hardware:
            from tools import run_onerom_live, save_reference
            count = spec.get('hardware', {}).get('repeats', 2)
            if count < 2:
                raise ValueError('new hardware experiments require at least two independent runs')
            references = []
            for index in range(count):
                destination = out / f'hardware-{index+1}'
                # The existing runner owns reset, live substitution and verified restoration.
                with (out / f'hardware-{index+1}.log').open('w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    run_onerom_live.collect_live(resolve(spec['hardware']['onerom']), romdir, destination,
                                                 spec['hardware'].get('timeout_seconds', 240), None)
                reference = out / f'reference-{index+1}'
                save_reference.save(destination, reference,
                                    'Repeatability computed below; inspect repeatability.json before versioning.',
                                    spec['hardware']['limitations'])
                references.append(reference)
                emit(out, 'hardware', dict(run=index+1, restoration='verified'), events)
        if not references:
            raise ValueError('provide saved references or explicitly request --hardware')
        hardware_rows = []
        reference_runs = []
        reference_coverage = []
        hashes = []
        for path in references:
            meta, rows = load_capture(path, build, spec['capture'], reference=True)
            reference_coverage.append(dict(reference=str(path), coverage=check_coverage(rows, spec['capture'])))
            hashes.append(meta['sha256'])
            hardware_rows.extend(rows)
            reference_runs.append(rows)
        report, cases = compare(hardware_rows, candidate, spec['comparison'])
        report['references'] = list(map(str, references))
        report['reference_coverage'] = reference_coverage
        report['reference_hashes'] = hashes
        report['repeatability'] = dict(runs=len(references), packets_identical=len(set(hashes)) == 1,
                                       unstable_cases=report['counts']['unstable_reference'],
                                       conflicting_cohorts=report['counts']['reference_conflicting_cohorts'],
                                       **repeat_cohorts(reference_runs, candidate, spec['comparison']))
        if hardware:
            write(out / 'repeatability.json', report['repeatability'])
            for path in references:
                manifest = read(path / 'manifest.json')
                manifest['repeatability'] = report['repeatability']
                write(path / 'manifest.json', manifest)
        baseline = spec.get('baseline')
        if baseline:
            _, before = load_capture(resolve(baseline), build, spec['capture'])
            previous_report, previous_cases = compare(hardware_rows, before, spec['comparison'])
            report['delta'] = delta(previous_cases, cases,[f.get('name',f['field']) for f in spec['comparison']['measurements']])
        else:
            previous_report = dict(groups=[])
        report['family_delta'] = evidence.family_delta(
            report, previous_report, dict(experiment=spec['id'], comparison=evidence.comparison_contract(spec['comparison'])))
        prior_patterns = {json.dumps(g['pattern']) for g in previous_report['groups']}
        current_patterns = {json.dumps(g['pattern']) for g in report['groups']}
        report['pattern_delta'] = dict(new=len(current_patterns-prior_patterns),
                                       resolved=len(prior_patterns-current_patterns),
                                       unchanged=len(prior_patterns & current_patterns),
                                       representatives=[g for g in report['groups']
                                           if json.dumps(g['pattern']) not in prior_patterns][:3])
        write(out / 'cases.json', cases)
        write(out / 'comparison.json', report)
        summary['counts'] = report['counts']
        summary['delta'] = report.get('delta', {}).get('counts')
        summary['patterns'] = report['pattern_delta']
        emit(out, 'comparison', dict(counts=summary['counts'], delta=summary['delta']), events)
        changes = summary['delta'] or {}
        if any(changes.get(k, 0) for k in ('regressions', 'field_regressions', 'qualification_regressions', 'missing_results')):
            raise ValueError('focused comparison regressed; broader validation not run')
        if (report['counts']['excluded'] > spec['comparison'].get('max_excluded', 0)
                or report['counts']['unstable_reference'] > spec['comparison'].get('max_unstable', 0)):
            raise ValueError('qualification/instability exceeds declared budget; revise experiment or preserve constraint')
        require_repairs(spec, report)
        for command in spec.get('validation', []):
            if through == 'comparison' or TIERS.index(command['tier']) > TIERS.index(through):
                break
            result = command_run(command, out, variables, cache)
            summary['commands'].append(dict(tier=command['tier'], **result))
            emit(out, 'validation', dict(tier=command['tier'], name=result['name'],
                                        exit=result['exit'], reused=result['reused']), events)
            if result['exit']:
                raise ValueError(f"{result['name']} failed: {result.get('excerpt', '')}")
        fingerprint = digest(json.dumps(dict(groups=report['groups'], counts=report['counts'],
                                             delta=changes, references=hashes), sort_keys=True).encode())
        no_new = record.get('evidence_fingerprint') == fingerprint
        record.update(experiment=spec['id'], run=str(out), identity=summary['identity'],
                      hypothesis=spec['hypothesis'], competitor=spec['competitor'], test=spec['test'],
                      smaller_reproducer=spec.get('smaller_reproducer'), outcomes=spec['outcomes'],
                      next_question=spec['next_question'], references=list(map(str, references)),
                      evidence_fingerprint=fingerprint,
                      no_new_evidence=record.get('no_new_evidence', 0)+1 if no_new else 0,
                      validation=[{k: c[k] for k in ('name', 'exit', 'tier') if k in c}
                                  for c in summary['commands']], decision='review evidence')
        write(record_path, record)
        summary.update(status='review', investigation=str(record_path), validation_through=through,
                       next_step='Choose patch, narrow, measure, preserve, or accept with decide; inspect only changed cases.')
    except Exception as error:
        summary['error'] = str(error)[:2000]
        failed = next((c for c in reversed(summary['commands']) if c['exit']), {})
        summary['logs'] = {k: failed[k] for k in ('stdout', 'stderr') if k in failed} or dict(directory=str(out))
        fingerprint = digest(json.dumps({k:summary.get(k) for k in ('error','counts','delta','patterns')},sort_keys=True).encode())
        record.update(run=str(out), hypothesis=spec['hypothesis'], test=spec['test'],
                      smaller_reproducer=spec.get('smaller_reproducer'), next_question=spec['next_question'],
                      no_new_evidence=record.get('no_new_evidence', 0)+1
                      if record.get('evidence_fingerprint') == fingerprint else 0,
                      evidence_fingerprint=fingerprint, decision='validation failed')
        write(record_path, record)
    if (out / 'comparison.json').is_file():
        summary['evidence'] = str(out / 'evidence.json')
    write(out / 'summary.json', summary)
    if (out / 'comparison.json').is_file():
        evidence.packet(out, cache)
    emit(out, 'complete', compact(summary), events)
    return summary


def compact(summary):
    return {k: summary[k] for k in ('status', 'output', 'counts', 'delta', 'patterns', 'validation_through', 'error', 'logs', 'investigation', 'next_step', 'evidence') if k in summary}


def retry_output_command(command, variables, logs, redirects):
    """Keep failed child runs intact and redirect later consumers consistently."""
    argv = [arg.format(**variables) for arg in command['argv']]
    original = None
    if '--out' in argv:
        original = Path(argv[argv.index('--out')+1])
        resolved = Path(redirects.get(str(original), str(original)))
        if resolved.exists():
            root = Path(variables['out'])
            if not original.is_absolute() or not original.is_relative_to(root):
                raise ValueError('retry output outside run requires an explicit revised plan')
            target = logs/'outputs'/original.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            redirects[str(original)] = str(target)
    for index, arg in enumerate(argv):
        for old, new in sorted(redirects.items(), key=lambda item: -len(item[0])):
            path = Path(arg)
            if path.is_absolute() and path.is_relative_to(Path(old)):
                argv[index] = str(Path(new)/path.relative_to(Path(old)))
                break
    # command_run formats once; preserve literal braces in already-expanded code.
    return command | dict(argv=[arg.replace('{', '{{').replace('}', '}}') for arg in argv])


def resume(out, through='broad', repeat=()):
    """Retry validation only, retaining frozen captures and all previous logs."""
    out=resolve(out);spec=validate_spec(read(out/'experiment.json'));summary=read(out/'summary.json')
    record_path=resolve(spec['investigation']);record=read(record_path)
    if record.get('run')!=str(out):raise ValueError('cannot resume a stale investigation run')
    identity=summary['identity']
    for path,name in ((out/'emulator.exe','binary_sha256'),(out/'machine.toml','config_sha256'),
                      (out/'rom/a500-timing-rom.bin','rom_sha256')):
        if digest(path.read_bytes())!=identity[name]:raise ValueError('frozen artifact changed; start a new run')
    build=read(out/'build-manifest.json')
    meta,_=load_capture(out/'candidate',build,spec['capture'])
    candidate_meta=read(out/'candidate/results.json')['metadata'] if (out/'candidate/results.json').exists() else None
    if candidate_meta and meta['sha256']!=candidate_meta['sha256']:raise ValueError('candidate packet changed')
    if not candidate_meta:
        origin=read(out/'candidate/reuse.json')['original']
        if meta['sha256']!=origin['results_sha256']:raise ValueError('cached candidate packet changed')
    report=read(out/'comparison.json')
    hashes=[load_capture(resolve(p),build,spec['capture'],True)[0]['sha256'] for p in report['references']]
    if hashes!=report['reference_hashes']:raise ValueError('hardware evidence changed; start a new run')
    changes=report.get('delta',{}).get('counts',{})
    if any(changes.get(k,0) for k in ('regressions','field_regressions','qualification_regressions','missing_results')):
        raise ValueError('cannot resume a regressed comparison')
    if (report['counts']['excluded']>spec['comparison'].get('max_excluded',0)
            or report['counts']['unstable_reference']>spec['comparison'].get('max_unstable',0)):
        raise ValueError('cannot resume an unqualified comparison')
    require_repairs(spec, report)
    if any(name not in {c['name'] for c in spec.get('validation',[])} for name in repeat):
        raise ValueError('repeat names must be declared validation commands')
    attempts=out/'validation-retries';attempts.mkdir(exist_ok=True)
    logs=attempts/str(len(list(attempts.iterdir()))+1);logs.mkdir()
    variables=dict(root=str(ROOT),out=str(out),python=sys.executable,binary=str(out/'emulator.exe'),
                   config=str(out/'machine.toml'),romdir=str(out/'rom'))
    cache=ROOT/'captures/.experiment-cache'
    successful={c['name'] for c in summary['commands'] if c['exit']==0}
    pending=[c for c in spec.get('validation',[]) if TIERS.index(c['tier'])<=TIERS.index(through)
             and (c['name'] not in successful or c['name'] in repeat)]
    if not pending:raise ValueError('no validation remains at this tier; do not repeat unchanged checks')
    summary.setdefault('validation_attempts',[])
    redirects=summary.setdefault('validation_output_redirects',{})
    summary.pop('error',None);summary.pop('logs',None)
    try:
        for command in spec.get('validation',[]):
            if TIERS.index(command['tier'])>TIERS.index(through):break
            if command['name'] in successful and command['name'] not in repeat:continue
            retried=retry_output_command(command,variables,logs,redirects)
            result=dict(tier=command['tier'],**command_run(retried,logs,variables,cache))
            old=[c for c in summary['commands'] if c['name']==command['name']]
            summary['validation_attempts']+=old
            summary['commands']=[c for c in summary['commands'] if c['name']!=command['name']]+[result]
            emit(out,'validation',dict(name=result['name'],tier=command['tier'],exit=result['exit'],retry=True))
            if result['exit']:raise ValueError(f"{result['name']} failed: {result.get('excerpt','')}")
        summary.update(status='review',validation_through=through)
        record.update(decision='review evidence',
                      no_new_evidence=0 if any(c['name'] not in successful for c in pending) else record.get('no_new_evidence',0),
                      validation=[{k:c[k] for k in ('name','exit','tier') if k in c} for c in summary['commands']])
    except Exception as error:
        summary.update(status='failed',error=str(error)[:2000],logs=dict(directory=str(logs)))
        record['decision']='validation failed'
    summary['evidence'] = str(out/'evidence.json')
    write(record_path,record);write(out/'summary.json',summary)
    evidence.packet(out,cache)
    emit(out,'complete',compact(summary))
    return summary


def trace_window(left, right, case, window):
    def selected(path):
        rows = []
        with resolve(path).open(encoding='utf-8') as stream:
            for line in stream:
                event = json.loads(line)
                if tuple(event.pop('case')) == tuple(case):
                    rows.append(event)
        return rows
    a, b = selected(left), selected(right)
    first = next((i for i, (x, y) in enumerate(zip_longest(a, b)) if x != y), None)
    if first is None:
        return dict(first_divergent_event=None, alignment='none')
    start, end = max(0, first-window), first+window+1
    return dict(first_divergent_event=first, alignment='none', start=start,
                hardware=a[start:end], candidate=b[start:end])


def decide(out, action, reason, evidence):
    out = resolve(out)
    spec = read(out / 'experiment.json')
    summary = read(out / 'summary.json')
    if summary['status'] != 'review' and action in ('accept','patch'):
        raise ValueError('failed/incomplete run cannot be accepted or directly patched; record a narrowed/revised experiment')
    if not reason.strip() or not evidence or any(not resolve(p).exists() for p in evidence):
        raise ValueError('a reason and existing evidence paths are required')
    if action == 'accept':
        tiers = {c.get('tier') for c in summary['commands'] if c['exit'] == 0}
        if not {'neighbor', 'broad'} <= tiers or not spec.get('baseline'):
            raise ValueError('accept requires baseline comparison, neighboring and broad validation')
    record_path = resolve(spec['investigation'])
    record = read(record_path)
    if record['run'] != str(out):
        raise ValueError('decision refers to a stale run; current investigation has advanced')
    record.update(decision=action, decision_reason=reason, evidence=evidence)
    write(record_path, record)
    write(out / 'decision.json', dict(action=action, reason=reason, evidence=evidence))
    return dict(decision=action, investigation=str(record_path))


def restart(record):
    data = read(resolve(record))
    # Deliberately bounded; the record links detailed history rather than copying it.
    selected = {k: data[k] for k in ('experiment', 'run', 'accepted_commits', 'identity', 'hypothesis', 'competitor', 'test',
                                   'next_question', 'decision', 'decision_reason', 'no_new_evidence') if k in data}
    selected['record'] = str(resolve(record))
    omitted = {}
    for k in ('confirmed_facts', 'rejected_hypotheses', 'references', 'source_files', 'evidence', 'validation', 'history'):
        selected[k] = data.get(k, [])[:8]
        if len(data.get(k, [])) > 8:
            omitted[k] = len(data[k])-8
    if omitted:
        selected['omitted_entries_retrieve_from_record'] = omitted
    if len(json.dumps(selected)) > 8000:
        raise ValueError('restart record exceeds8000 characters; move history to files and shorten current facts')
    return selected


def archive(out, destination):
    """Version verified packets and provenance only; never copy live ROM backups."""
    out, destination = resolve(out), resolve(destination)
    report = read(out / 'comparison.json')
    build = read(out / 'build-manifest.json')
    spec = read(out / 'experiment.json')
    if destination.exists():
        raise ValueError('reference destination already exists')
    sources = [resolve(p) for p in report['references']]
    for p in sources:
        load_capture(p, build, spec['capture'], reference=True)
    destination.mkdir(parents=True)
    for index, path in enumerate(sources, 1):
        target = destination / f'run{index}'
        target.mkdir()
        shutil.copyfile(path / 'results.bin', target / 'results.bin')
        manifest = read(path / 'manifest.json')
        manifest.update(reference_id=f'{destination.name}-run{index}', original_reference=str(path))
        write(target / 'manifest.json', manifest)
    return dict(references=str(destination), runs=len(sources))


def packets(before, after, suites, binary=None, config=None):
    """A strict unchanged-packet gate; changed neighbors require HW interpretation."""
    if bool(binary) != bool(config):
        raise ValueError('binary and config identity checks must be supplied together')
    if binary:
        parent = resolve(after)
        identity = read(parent/'summary.json')
        expected_binary = digest(resolve(binary).read_bytes())
        expected_config = digest(resolve(config).read_bytes())
        if (identity['binary_sha256'] != expected_binary or identity['config_sha256'] != expected_config
                or digest((parent/'emulator.exe').read_bytes()) != expected_binary
                or digest((parent/'machine.toml').read_bytes()) != expected_config):
            raise ValueError('replayed binary/config identity differs; rerun neighbors')
        for suite in suites:
            invocation = read(parent/suite/'invocation.json')
            if invocation['binary_sha256'] != expected_binary or invocation.get('binary_changed_during_run'):
                raise ValueError(f'{suite}: invalid replay binary provenance')
    counts = Counter(suites=len(suites), unchanged_cases=0, changed_cases=0, missing_suites=0)
    representatives = []
    for suite in suites:
        a, b = resolve(before)/suite/'results.bin', resolve(after)/suite/'results.bin'
        if not a.exists() or not b.exists():
            counts['missing_suites'] += 1
            continue
        am, ar = rom_results.decode(a.read_bytes())
        bm, br = rom_results.decode(b.read_bytes())
        if am['source_id'] != bm['source_id']:
            raise ValueError(f'{suite}: source mismatch')
        left, right = {key(r): r for r in ar}, {key(r): r for r in br}
        if len(left) != len(ar) or len(right) != len(br):
            raise ValueError(f'{suite}: duplicate descriptors')
        for case in sorted(left.keys() | right.keys()):
            same = left.get(case) == right.get(case)
            counts['unchanged_cases' if same else 'changed_cases'] += 1
            if not same and len(representatives) < 3:
                representatives.append(dict(suite=suite, case=case,
                    fields=[f for f in set(left.get(case, {})) | set(right.get(case, {}))
                            if left.get(case, {}).get(f) != right.get(case, {}).get(f)]))
    return dict(counts=dict(counts), representatives=representatives,
                status='failed' if counts['changed_cases'] or counts['missing_suites'] else 'unchanged')


def aggregate(out, status, group_by, fields, limit=8, paired=False):
    """Summarize selected evidence without dumping matching records."""
    out = resolve(out)
    spec = read(out/'experiment.json')
    definitions = {f.get('name', f['field']): f for f in
                   spec['comparison']['measurements'] + spec['comparison']['qualification']}
    if any(f not in definitions for f in fields) or any(f not in DESCRIPTOR for f in group_by):
        raise ValueError('use declared measurement names and descriptor grouping fields')
    measurements = {f.get('name',f['field']): i for i,f in enumerate(spec['comparison']['measurements'])}
    if paired and (status not in ('matches','mismatches') or any(f not in measurements for f in fields)):
        raise ValueError('paired aggregation requires stable matched/mismatched measurement fields')
    groups = defaultdict(list)
    for case, detail in read(out/'cases.json').items():
        if detail['status'] == status:
            r = detail['candidate']
            groups[tuple(r[f] for f in group_by)].append((case,detail))
    result = []
    for condition, rows in sorted(groups.items(), key=lambda item:(-len(item[1]),item[0]))[:limit]:
        observed = {}
        for name in fields:
            distribution = Counter(value(detail['candidate'],definitions[name]) for _,detail in rows)
            observed[name] = dict(unit=definitions[name]['unit'], minimum=min(distribution),
                                  maximum=max(distribution), distinct=len(distribution),
                                  common=distribution.most_common(3))
            if paired:
                i = measurements[name]
                pairs = Counter((detail['expected'][i], detail['actual'][i]) for _,detail in rows)
                observed[name].update(expected_actual_pairs=pairs.most_common(3),
                                      different_cases=sum(n for (a,b),n in pairs.items() if a != b))
        result.append(dict(condition=dict(zip(group_by,condition)), count=len(rows),
                           fields=observed, representatives=[case for case,_ in rows[:3]]))
    return dict(status=status, cases=sum(map(len,groups.values())), groups_total=len(groups),
                groups=result, note='Declared extraction only; no alignment or conversion of packed timing values.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('run')
    p.add_argument('manifest', type=Path)
    p.add_argument('--out', required=True)
    p.add_argument('--hardware', action='store_true', help='perform new live runs instead of reusing references')
    p.add_argument('--events', action='store_true', help='emit stage completion events, never raw logs')
    p.add_argument('--binary',help='override the candidate with a frozen parent-run executable')
    p.add_argument('--config',help='override with the parent-run configuration')
    p.add_argument('--through', choices=('preflight','comparison') + TIERS, default='broad', help='stop at this validation tier; partial runs cannot be accepted')
    for name in ('status', 'detail', 'decide', 'archive'):
        p = sub.add_parser(name)
        p.add_argument('run')
        if name == 'detail':
            p.add_argument('--case', required=True)
            p.add_argument('--window', type=int, default=6, choices=range(0, 33))
        if name == 'decide':
            p.add_argument('--action', required=True, choices=('patch', 'narrow', 'measure', 'preserve', 'accept'))
            p.add_argument('--reason', required=True)
            p.add_argument('--evidence', action='append', required=True)
        if name == 'archive':
            p.add_argument('--out', required=True)
    p = sub.add_parser('restart')
    p.add_argument('record')
    p.add_argument('--out', required=True)
    p = sub.add_parser('packets')
    p.add_argument('--before', required=True)
    p.add_argument('--after', required=True)
    p.add_argument('--suite', action='append', required=True)
    p.add_argument('--binary')
    p.add_argument('--config')
    p = sub.add_parser('aggregate')
    p.add_argument('run')
    p.add_argument('--status', choices=('matches','mismatches','excluded','unstable_reference'), default='mismatches')
    p.add_argument('--group-by', default='target,variant,phase')
    p.add_argument('--fields', default='')
    p.add_argument('--limit', type=int, default=8, choices=range(1,17))
    p.add_argument('--paired', action='store_true', help='bounded hardware/candidate value pairs; no time conversion')
    p = sub.add_parser('resume')
    p.add_argument('run')
    p.add_argument('--through', choices=TIERS,default='broad')
    p.add_argument('--repeat',action='append',default=[])
    p = sub.add_parser('evidence', help='bounded delta packet; full detail stays in files')
    p.add_argument('run')
    p.add_argument('--baseline', help='prior run with identical comparison contract and references')
    p.add_argument('--limit', type=int, default=5, choices=range(1,17))
    p.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'evidence':
            result = evidence.packet(resolve(args.run), ROOT/'captures/.experiment-cache',
                                     resolve(args.baseline) if args.baseline else None,
                                     args.limit, args.refresh)
            print(json.dumps(result))
            return 0
        if args.command == 'run':
            overrides={k:getattr(args,k) for k in ('binary','config') if getattr(args,k)}
            result = run(args.manifest, args.out, args.hardware, args.events, args.through,overrides)
            if not args.events:
                print(json.dumps(compact(result)))
            return 1 if result['status'] == 'failed' else 0
        if args.command == 'packets':
            result = packets(args.before, args.after, args.suite, args.binary, args.config)
            print(json.dumps(result))
            return 1 if result['status'] == 'failed' else 0
        if args.command == 'aggregate':
            result = aggregate(args.run, args.status, [x for x in args.group_by.split(',') if x],
                               [x for x in args.fields.split(',') if x], args.limit, args.paired)
            print(json.dumps(result))
            return 0
        if args.command == 'resume':
            result=resume(args.run,args.through,args.repeat)
            print(json.dumps(compact(result)))
            return 1 if result['status']=='failed' else 0
        if args.command == 'status':
            result = read(resolve(args.run) / 'status.json')
        elif args.command == 'detail':
            out = resolve(args.run)
            result = read(out / 'cases.json')[args.case]
            spec = read(out / 'experiment.json')
            if spec.get('traces'):
                result['trace'] = trace_window(spec['traces']['hardware'], spec['traces']['candidate'], result['case'], args.window)
                result['trace']['unit'] = spec['traces']['unit']
            else:
                result['trace'] = 'No event traces supplied; raw snapshot fields retained above.'
        elif args.command == 'decide':
            result = decide(args.run, args.action, args.reason, args.evidence)
        elif args.command == 'archive':
            result = archive(args.run, args.out)
        else:
            packet = restart(args.record)
            write(resolve(args.out), packet)
            result = dict(restart_packet=str(resolve(args.out)))
        print(json.dumps(result))
        return 0
    except Exception as error:
        print(json.dumps(dict(status='failed', error=str(error)[:2000])))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

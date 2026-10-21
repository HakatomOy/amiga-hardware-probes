"""Screen explicit emulator environments against unchanged saved-HW contracts.

This is a counterfactual screen, never an acceptance command. The declared
baseline packet must be byte-identical before any other variant is launched.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import experiment as e
from run_rom import load_emulator_environment


def scenario_spec(base, environment, record):
    spec = json.loads(json.dumps(base))
    spec['capture']['environment_json'] = str(environment.resolve())
    spec['investigation'] = str(record.resolve())
    return spec


def checked_names(recipe):
    for section in ('variants', 'scenarios'):
        if not recipe.get(section):
            raise ValueError(f'{section} must not be empty')
        if any(not re.fullmatch(r'[a-z0-9_-]+', name) for name in recipe[section]):
            raise ValueError('variant/scenario names must be simple path components')
    baseline = recipe['baseline']
    if baseline['variant'] not in recipe['variants'] or baseline['scenario'] not in recipe['scenarios']:
        raise ValueError('baseline must name a declared variant and scenario')


def screen(recipe_path, out, binary, workers=3):
    recipe = e.read(recipe_path)
    checked_names(recipe)
    if not 1 <= workers <= 3:
        raise ValueError('workers must be1..3; hardware is never run by this tool')
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    frozen = out / 'emulator.exe'
    shutil.copy2(binary, frozen)
    e.write(out / 'recipe.json', recipe)
    e.write(out / 'identity.json', dict(binary_sha256=e.digest(frozen.read_bytes()),
                                      acceptance_performed=False))
    specs = out / 'specs'
    specs.mkdir()
    for variant, settings in recipe['variants'].items():
        env = specs / (variant + '.environment.json')
        e.write(env, settings)
        load_emulator_environment(env)

    def run(pair):
        variant, scenario = pair
        name = variant + '-' + scenario
        spec = scenario_spec(e.read(e.resolve(recipe['scenarios'][scenario])),
                             specs / (variant + '.environment.json'), out / (name + '.record.json'))
        manifest = specs / (name + '.json')
        e.write(manifest, spec)
        result = e.command_run(dict(name=name, argv=[sys.executable, 'tools/experiment.py', 'run',
            str(manifest), '--binary', str(frozen), '--out', str(out / name), '--through', 'comparison']),
            out, {}, out / 'cache')
        status = e.read(out / name / 'status.json')
        counts = status.get('counts', {})
        if 'total' not in counts or counts.get('invalid_captures') or counts.get('missing_results'):
            raise ValueError(f'{name}: capture failed before a valid comparison; inspect {out / name}')
        delta = status.get('delta') or {}
        report = dict(variant=variant, scenario=scenario, exit=result['exit'], counts=counts,
                      new_fields=delta.get('field_regressions'),
                      qualification_changes=delta.get('qualification_regressions'),
                      error=status.get('error'), detail=str(out / name))
        print(json.dumps(report), flush=True)
        return report

    baseline = recipe['baseline']
    first = (baseline['variant'], baseline['scenario'])
    results = [run(first)]
    packet = out / ('-'.join(first)) / 'candidate/results.bin'
    if packet.read_bytes() != e.resolve(baseline['packet']).read_bytes():
        raise ValueError(f'baseline packet differs; screen invalid; inspect {out}')
    e.write(out / 'baseline-verification.json', dict(byte_identical=True,
                                                    packet_sha256=e.digest(packet.read_bytes())))
    pairs = [(v, s) for v in recipe['variants'] for s in recipe['scenarios'] if (v, s) != first]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results.extend(pool.map(run, pairs))
    e.write(out / 'results.json', dict(status='screen_complete', acceptance_performed=False,
                                     baseline_byte_identical=True, results=results))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    try:
        screen(args.recipe, args.out, args.binary, args.workers)
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps(dict(status='screen_invalid', error=str(error)[:600])))
        raise SystemExit(1)

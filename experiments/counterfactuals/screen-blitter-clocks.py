"""Batch an explicitly experimental blitter-clock binary; never an acceptance gate."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--baseline-results', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    binary = args.binary.resolve()
    baseline = hashlib.sha256(args.baseline_results.read_bytes()).hexdigest()
    template = json.loads((ROOT / 'experiments/workflows/copper-transfer-handoff-witness.json').read_text())

    def run(pair):
        mode, refresh = pair
        folder = out / f'cpu{mode}-refresh{refresh}'
        folder.mkdir()
        settings = dict(COPPERLINE_EXPERIMENT_CPU_FREE=str(mode),
                        COPPERLINE_EXPERIMENT_INIT_REFRESH=str(refresh))
        settings_path = folder / 'experimental-environment.json'
        settings_path.write_text(json.dumps(settings, indent=2) + '\n')
        spec = json.loads(json.dumps(template))
        spec['capture']['environment_json'] = str(settings_path)
        spec.update(id='blitter-clock-screen', reuse_preflight=False,
                    investigation=str(folder / 'investigation.json'),
                    replay_inputs=[str(settings_path)],
                    hypothesis='Counterfactual screen only: eligible clocks on CPU ownership and pre-refresh Init.',
                    test='Require exact reference cohorts and compare fields; validate mode0/refresh0 against the frozen parent packet.')
        manifest = folder / 'manifest.json'
        manifest.write_text(json.dumps(spec, indent=2) + '\n')
        environment = dict(os.environ, **settings)
        with (folder / 'driver.log').open('w') as log:
            completed = subprocess.run([sys.executable, str(ROOT / 'tools/experiment.py'),
                                        'run', str(manifest), '--out', str(folder / 'run'),
                                        '--binary', str(binary), '--through', 'comparison'],
                                       cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
        summary = json.loads((folder / 'run/summary.json').read_text())
        packet = folder / 'run/candidate/results.bin'
        packet_hash = hashlib.sha256(packet.read_bytes()).hexdigest() if packet.exists() else None
        result = dict(cpu_mode=mode, init_refresh=refresh, exit=completed.returncode,
                      counts=summary.get('counts'), delta=summary.get('delta'),
                      error=summary.get('error'), packet_sha256=packet_hash,
                      evidence=str(folder / 'run/comparison.json'))
        if pair == (0, 0) and packet_hash != baseline:
            raise ValueError('control packet differs from frozen parent; reject the entire screen')
        print(json.dumps(result), flush=True)
        return result

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(run, [(mode, refresh) for refresh in (0, 1) for mode in range(4)]))
    (out / 'screen.json').write_text(json.dumps(dict(
        experimental_only=True, binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        baseline_sha256=baseline, control_verified=True, results=results,
        limitation='Environment is part of each explicit replay input; no live HW, no alignment. '
                   'Rebuild the selected behavior without experimental branches and run all gates before acceptance.'
    ), indent=2) + '\n')


if __name__ == '__main__':
    main()

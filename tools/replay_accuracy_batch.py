"""Run independent reference suites with bounded concurrency and file-backed logs.

Counts retain replay_accuracy's qualification rules. A successful child process
does not imply every historical hardware comparison matches.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.replay_accuracy import SUITES


def run_suite(name, out, binary, config):
    stdout = out / f'{name}.stdout.log'
    stderr = out / f'{name}.stderr.log'
    command = [sys.executable, str(ROOT / 'tools/replay_accuracy.py'),
               '--binary', str(binary), '--config', str(config),
               '--suite', name, '--out', str(out / name)]
    try:
        with stdout.open('wb') as a, stderr.open('wb') as b:
            result = subprocess.run(command, cwd=ROOT, stdout=a, stderr=b)
        summary = json.loads((out / name / 'summary.json').read_text())
        return dict(exit=result.returncode, **summary['suites'][name],
                    stdout=str(stdout), stderr=str(stderr))
    except Exception as error:
        return dict(exit=1, error=str(error)[:400], stdout=str(stdout), stderr=str(stderr))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--suite', action='append', choices=SUITES)
    parser.add_argument('--jobs', type=int, choices=range(1, 5), default=2)
    args = parser.parse_args()
    suites = list(dict.fromkeys(args.suite or SUITES))
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    binary = out / 'emulator.exe'
    config = out / 'machine.toml'
    shutil.copyfile(args.binary, binary)
    shutil.copyfile(args.config, config)
    summary = dict(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                   config_sha256=hashlib.sha256(config.read_bytes()).hexdigest(), suites={})
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        pending = {pool.submit(run_suite, name, out, binary, config): name for name in suites}
        for future in as_completed(pending):
            name = pending[future]
            result = future.result()
            summary['suites'][name] = result
            (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
            print(json.dumps(dict(suite=name, exit=result['exit'],
                                  counts=result.get('raw_counts'), error=result.get('error'))), flush=True)
    return int(any(result['exit'] for result in summary['suites'].values()))


if __name__ == '__main__':
    raise SystemExit(main())

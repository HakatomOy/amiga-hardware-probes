"""Interleave two immutable emulator binaries; keep benchmark output in files."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--profile', required=True, help='provenance label, e.g. ci or release')
    parser.add_argument('--seconds', type=float, default=2)
    parser.add_argument('--repeats', type=int, default=5)
    args = parser.parse_args()
    if args.seconds <= 0 or args.repeats < 3:
        parser.error('positive emulated duration and at least three repeats required')
    paths = {name: getattr(args, name).resolve() for name in ('before', 'after', 'config', 'rom')}
    hashes = {name: digest(path) for name, path in paths.items()}
    args.out.mkdir(parents=True, exist_ok=False)
    runs = []
    # One warmup pair, then reverse order on alternate measured pairs.
    for repeat in range(-1, args.repeats):
        for label in (('before', 'after') if repeat % 2 == 0 else ('after', 'before')):
            command = [str(paths[label]), '--factory', '--config', str(paths['config']),
                       '--noaudio', '--no-jit', '--benchmark-until', str(args.seconds),
                       str(paths['rom'])]
            stem = args.out / f'{label}-{repeat}'
            started = time.perf_counter()
            with stem.with_suffix('.stdout.log').open('wb') as stdout, stem.with_suffix('.stderr.log').open('wb') as stderr:
                completed = subprocess.run(command, stdout=stdout, stderr=stderr,
                                           cwd=args.out.resolve(), timeout=180)
            duration = time.perf_counter() - started
            if completed.returncode != 0:
                raise RuntimeError(f'{label} exit={completed.returncode}; full logs: {stem}')
            if any(digest(path) != hashes[name] for name, path in paths.items()):
                raise ValueError('benchmark input changed during run')
            runs.append(dict(label=label, repeat=repeat, wall_seconds=duration, command=command))
    summary = {}
    for label in ('before', 'after'):
        values = [r['wall_seconds'] for r in runs if r['label'] == label and r['repeat'] >= 0]
        summary[label] = dict(median=statistics.median(values), minimum=min(values), maximum=max(values))
    result = dict(profile=args.profile, emulated_seconds=args.seconds, hashes=hashes,
                  runs=runs, process_wall_seconds=summary,
                  median_ratio=summary['after']['median'] / summary['before']['median'],
                  limitation='Includes process startup and fixed ROM workload. CI timings do not establish release performance.')
    (args.out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'runs'}))


if __name__ == '__main__':
    main()

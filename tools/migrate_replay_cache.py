"""Import old replay keys only after verifying their complete old capture fingerprint."""
import argparse
import json
from pathlib import Path
import shutil
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import experiment as e


def migrate(runner_sha):
    cache = ROOT/'captures/.experiment-cache'
    imported = skipped = 0
    for origin_path in cache.glob('replay-*/origin.json'):
        origin = e.read(origin_path)
        if 'capture_contract' in origin:
            continue
        run = Path(origin['run'])
        if not run.is_relative_to(ROOT/'captures'):
            raise ValueError('origin is outside capture workspace')
        spec = e.read(run/'experiment.json')
        build = e.read(run/'build-manifest.json')
        summary = e.read(run/'summary.json')
        identity = summary['identity']
        variables = dict(root=str(ROOT), out=str(run), python=sys.executable,
                         binary=str(run/'emulator.exe'), config=str(run/'machine.toml'),
                         romdir=str(run/'rom'))
        seconds = max(spec['capture']['minimum_seconds'], spec['capture'].get('seconds', 0))
        contract = e.replay_fingerprint(identity, seconds,
                    e.fingerprints(spec.get('replay_inputs', []), variables))
        old_contract = {k: v for k, v in contract.items() if k != 'capture_adapter_version'}
        old_contract['runner_sha256'] = runner_sha
        key = e.digest(json.dumps(old_contract, sort_keys=True).encode())
        if origin_path.parent.name != 'replay-' + key:
            skipped += 1
            continue
        for file, name in [('emulator.exe','binary_sha256'),('machine.toml','config_sha256'),
                           ('rom/a500-timing-rom.bin','rom_sha256')]:
            if e.digest((run/file).read_bytes()) != identity[name]:
                raise ValueError('origin artifact changed')
        packet = (origin_path.parent/'results.bin').read_bytes()
        if origin['identity'] != identity or e.digest(packet) != origin['results_sha256']:
            raise ValueError('cache identity or packet changed')
        meta, rows = e.rom_results.decode(packet)
        if meta['source_id'] != build['source_id'] or [list(e.key(r)) for r in rows] != build['trials']:
            raise ValueError('cached source or descriptors changed')
        target = cache/('replay-' + e.digest(json.dumps(contract, sort_keys=True).encode()))
        if target.exists():
            skipped += 1
            continue
        target.mkdir()
        shutil.copyfile(origin_path.parent/'results.bin', target/'results.bin')
        e.write(target/'build-manifest.json', build)
        e.write(target/'origin.json', origin | dict(capture_contract=contract,
                    migrated_from=str(origin_path.parent), verified_old_runner_sha256=runner_sha))
        imported += 1
    return dict(imported=imported, skipped=skipped)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runner-sha256', required=True)
    print(json.dumps(migrate(p.parse_args().runner_sha256)))

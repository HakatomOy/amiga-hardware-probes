#!/usr/bin/env python3
"""Compare validated standalone RAM-probe captures without mistaking phase for latency."""
import argparse, collections, json
from pathlib import Path
import rom_results


def load(folder):
    meta, rows = rom_results.decode((folder / 'results.bin').read_bytes())
    manifest = json.loads((folder / 'build-manifest.json').read_text())
    if meta['source_id'] != manifest['source_id']:
        raise ValueError('Capture and manifest disagree')
    if meta['timeouts'] or meta['skipped']:
        raise ValueError('Incomplete trial coverage')
    if [tuple(r[k] for k in rom_results.FIELDS[:6]) for r in rows] != [tuple(r) for r in manifest['trials']]:
        raise ValueError('Trial descriptors disagree')
    return meta, rows


def histogram(values):
    return dict(sorted(collections.Counter(values).items()))


def compare(hw, emu):
    hm, hr = load(hw)
    em, er = load(emu)
    if hm['source_id'] != em['source_id']:
        raise ValueError('Different measured ROMs')
    report = dict(hardware=hm, emulator=em, groups=[])
    keys = sorted({(r['kind'], r['target'], r['variant']) for r in hr})
    for kind, target, variant in keys:
        pairs = [(a, b) for a, b in zip(hr, er)
                 if (a['kind'], a['target'], a['variant']) == (kind, target, variant)]
        group = dict(kind=kind, target=target, variant=variant, samples=len(pairs))
        if kind == 16:
            group['live_deltas'] = histogram(b['counter']-a['counter'] for a, b in pairs)
            group['stopped_deltas'] = histogram(b['aux']-a['aux'] for a, b in pairs)
        elif kind == 15:
            raw = lambda r: (r['icr'] << 16) | r['counter']
            group['hardware_raw'] = histogram(raw(a) for a, b in pairs)
            group['emulator_raw'] = histogram(raw(b) for a, b in pairs)
            if target == 1:
                group['hardware_width'] = histogram(a['aux'] for a, b in pairs)
                group['emulator_width'] = histogram(b['aux'] for a, b in pairs)
        elif kind == 17:
            def elapsed(r):
                start, end = r['launch_beam'], r['end_beam']
                return ((end >> 8)-(start >> 8))*227+(end & 255)-(start & 255)
            group['heights'] = {}
            for height in sorted({a['delay'] for a, b in pairs}):
                sub = [(a, b) for a, b in pairs if a['delay'] == height]
                group['heights'][height] = dict(
                    hardware_cck=histogram(elapsed(a) for a, b in sub),
                    emulator_cck=histogram(elapsed(b) for a, b in sub))
            group['note'] = 'PAL only; retain raw distributions and reject horizontal-wrap ambiguity before fitting.'
        else:
            raise ValueError(f'Unsupported experiment kind {kind}')
        report['groups'].append(group)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('hardware', type=Path)
    parser.add_argument('emulator', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = json.dumps(compare(args.hardware, args.emulator), indent=2)+'\n'
    if args.out:
        args.out.write_text(result)
    else:
        print(result, end='')

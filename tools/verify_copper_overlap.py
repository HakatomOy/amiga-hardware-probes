"""Verify witnessed kind78 replay has Copper transfers during each enabled blit."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import rom_results


def analyze(lines, rows):
    real = [r for r in rows if not r['variant'] & 8]
    if any(r['kind'] not in (78, 80) for r in rows):
        raise ValueError('requires kind78/80 descriptors')
    index, current = 0, None
    counts = Counter(real_blits=0, copper_blits=0, with_overlap_moves=0, with_copper_owner=0)
    examples = []
    for number, line in enumerate(lines, 1):
        if line.startswith('BLTP ') and ' START ' in line:
            if current is not None or index >= len(real):
                raise ValueError('unexpected or overlapping START')
            row = real[index]
            index += 1
            current = dict(case=[row[k] for k in rom_results.FIELDS[:6]],
                           copper=((row['variant'] >> 1) & 3) == 3,
                           moves=0, owners=0, representative_lines=[])
        if current is None:
            continue
        if line.startswith('COPPROBE MOVE'):
            current['moves'] += 1
            if len(current['representative_lines']) < 3:
                current['representative_lines'].append(number)
        if 'OWNER Copper' in line:
            current['owners'] += 1
        if line.startswith('BLTP ') and ' END ' in line:
            counts['real_blits'] += 1
            if current['copper']:
                counts['copper_blits'] += 1
                counts['with_overlap_moves'] += current['moves'] > 0
                counts['with_copper_owner'] += current['owners'] > 0
                if not current['moves'] or not current['owners']:
                    raise ValueError(f"no verified Copper overlap: {current['case']}")
                if len(examples) < 3:
                    examples.append(current)
            current = None
    if current is not None or index != len(real) or not counts['copper_blits']:
        raise ValueError('incomplete trace or no enabled Copper blits')
    return dict(counts=dict(counts), examples=examples,
                limitation='Emulator overlap witness only; hardware activity is qualified by settled COPER. No event alignment.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace_run', type=Path)
    args = parser.parse_args()
    folder = args.trace_run
    if not json.loads((folder/'trace-verification.json').read_text())['byte_identical']:
        raise ValueError('diagnostic capture is not byte-identical to qualified replay')
    _, rows = rom_results.decode((folder/'results.bin').read_bytes())
    with (folder/'run.log').open() as stream:
        result = analyze(stream, rows)
    (folder/'copper-overlap.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()

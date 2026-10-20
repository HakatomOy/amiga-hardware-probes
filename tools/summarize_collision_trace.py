"""Index first collision-latch producers for selected qualified mismatches."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import experiment as e


def index_trace(lines, rows, selected):
    kinds = {r['kind'] for r in rows}
    if len(kinds) != 1 or not kinds <= {72, 73, 86}:
        raise ValueError('requires uniform kind72/73/86')
    reads_per_case = 3 if kinds == {72} else 4
    result = {key: dict(events=[], reads=[]) for key in sorted(selected)}
    read_count = 0
    for number, line in enumerate(lines, 1):
        is_read = line.startswith('CPUBUS kind=custom addr=00dff00e ')
        is_event = 'CLXPROBE ' in line
        if not is_read and not is_event:
            continue
        index, stage = divmod(read_count, reads_per_case)
        if index >= len(rows):
            if is_read:
                raise ValueError('extra CLXDAT read')
            continue
        key = ','.join(map(str, e.key(rows[index])))
        if key in result:
            item = dict(line=number, stage=stage, text=line.strip())
            if is_read:
                result[key]['reads'].append(item)
            elif stage != 0:
                result[key]['events'].append(item)
        read_count += is_read
    if read_count != len(rows) * reads_per_case:
        raise ValueError('CLXDAT read/descriptor coverage differs')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--trace-run', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    packet = (args.trace_run / 'results.bin').read_bytes()
    if packet != (args.run / 'candidate/results.bin').read_bytes():
        raise ValueError('diagnostic packet differs from comparison candidate')
    if not e.read(args.trace_run / 'trace-verification.json')['byte_identical']:
        raise ValueError('diagnostic replay not verified')
    rows = e.rom_results.decode(packet)[1]
    cases = e.read(args.run / 'cases.json')
    selected = {key for key, c in cases.items() if c['status'] == 'mismatches'}
    with (args.trace_run / 'run.log').open() as stream:
        indexed = index_trace(stream, rows, selected)
    e.write(args.out, indexed)
    groups = Counter()
    examples = []
    for key, detail in indexed.items():
        events = [x for x in detail['events'] if x['stage'] == 1]
        for event in events:
            source = re.search(r'CLXPROBE (\w+) v=([0-9a-f]+)', event['text'])
            if source:
                groups[source[1], int(source[2], 16)] += 1
        if len(examples) < 3:
            examples.append(dict(case=key, first_read=detail['reads'][1], producers=events[:2]))
    print(json.dumps(dict(selected=len(indexed), first_read_producers=[
        dict(source=k[0], vpos=k[1], count=n) for k, n in groups.items()],
        examples=examples, detail=str(args.out))))


if __name__ == '__main__':
    main()

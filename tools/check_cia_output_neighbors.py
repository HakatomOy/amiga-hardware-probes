"""Check settled CIA output evidence, preserving all unrelated legacy snapshots.

Kind53's live PB6 snapshot lacks an exact E-high bracket. Changes to that bit
must be validated by the separate calibrated kind66/69 contracts; this gate
reports them without crediting repairs. Everything else remains byte-identical.
"""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import experiment as e
import compare_cia_hardware as cia


def check_rows(hardware, baseline, candidate):
    if [e.key(r) for r in baseline] != [e.key(r) for r in candidate]:
        raise ValueError('legacy descriptor sequence changed')
    changes = []
    for old, new in zip(baseline, candidate):
        fields = [k for k in old if old[k] != new[k]]
        if not fields:
            continue
        if (new['kind'] != 53 or fields != ['irq_level']
                or (old['irq_level'] ^ new['irq_level']) & ~0x40):
            raise ValueError('unexpected legacy field change: ' + str(e.key(new)))
        changes.append(e.key(new))
    before, after = cia.compare(hardware, baseline), cia.compare(hardware, candidate)
    if before['counts'] != after['counts'] or after['counts']['mismatch']:
        raise ValueError('qualified settled output or qualification budget regressed')
    return dict(qualified=after['counts'], unqualified_live_pb6_changes=len(changes),
                representatives=changes[:3],
                note='Live changes are not credited as repairs; calibrated kind66/69 acceptance is required.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('before', 'after', 'binary', 'config'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    # This also verifies the replay snapshot and each suite's invocation hashes.
    e.packets(a.before, a.after, ['cia-output', 'cia-irq', 'irq-stages'], a.binary, a.config)
    unchanged = e.packets(a.before, a.after, ['cia-irq', 'irq-stages'], a.binary, a.config)
    if unchanged['status'] != 'unchanged':
        raise ValueError('legacy IRQ packets changed')
    summary = e.read(a.after / 'summary.json')
    _, hw = cia.load(Path(summary['suites']['cia-output']['reference']))
    _, old = cia.load(a.before / 'cia-output')
    _, new = cia.load(a.after / 'cia-output')
    result = check_rows(hw, old, new)
    for name, matched, unstable in [('serial-buffer', 320, 0), ('serial-boundary', 38, 2)]:
        counts = summary['suites'][name]['raw_counts']
        if counts['matches'] != matched or counts['mismatches'] or counts['missing_results'] or counts['invalid_captures'] or counts['no_identical_bracket'] or counts['unstable_reference'] != unstable:
            raise ValueError('serial neighbor changed: ' + name)
    e.write(a.after / 'cia-output-gate.json', result)
    print(json.dumps(result))

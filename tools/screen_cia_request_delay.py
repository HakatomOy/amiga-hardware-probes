"""Screen whole-E request delays using a one-shot latch sweep, without aligning traces.

Counterfactual only: increasing a one-shot latch by N postpones its sole event
by N E-clocks. Compare that emulator row's request vector with the hardware row
at the original latch, requiring identical launch/calibration/sample brackets.
This does not change the real comparator or qualify an emulator fix.
"""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import experiment as e


def screen(hardware, candidate, policy, shift):
    fields = [f for f in policy['measurements'] if f['name'] in
              ('Paula_request', 'request1', 'request2', 'request3')]
    def cohort(r, delay):
        return (r['kind'], r['target'], r['variant'], r['phase'], delay,
                *(e.value(r, f) for f in policy['qualification']))
    table = {}
    for r in candidate:
        table.setdefault(cohort(r, r['delay']), set()).add(tuple(e.value(r, f) for f in fields))
    count = errors = missing = 0
    for r in hardware:
        predicted = table.get(cohort(r, r['delay'] + shift), set())
        if len(predicted) != 1:
            missing += 1
            continue
        count += 1
        errors += next(iter(predicted)) != tuple(e.value(r, f) for f in fields)
    return dict(delay_E=shift, compared=count, different_vectors=errors,
                unavailable_or_ambiguous=missing)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('run', type=Path)
    a = p.parse_args()
    spec = e.read(a.run / 'experiment.json')
    if e.read(a.run / 'build-manifest.json')['irq_stage']['kind'] != 68:
        raise ValueError('requires kind68 one-shot latch sweep')
    report = e.read(a.run / 'comparison.json')
    hardware = []
    for ref in report['references']:
        hardware.extend(e.rom_results.decode((Path(ref) / 'results.bin').read_bytes())[1])
    candidate = e.rom_results.decode((a.run / 'candidate/results.bin').read_bytes())[1]
    print(json.dumps(dict(model='Whole-E one-shot event delay, not trace alignment or fix acceptance',
                          results=[screen(hardware, candidate, spec['comparison'], n) for n in range(4)])))

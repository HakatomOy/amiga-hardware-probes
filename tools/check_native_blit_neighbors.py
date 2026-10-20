"""Preserve legacy packets, allowing only hardware-confirmed BLIT field repairs.

The historical kind50 capture lacks modern restoration provenance. It is
corroborating regression evidence; the fresh, restored kind71 captures remain
the primary evidence for accepting a native-request correction.
"""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import experiment as e
import compare_copper_busy as busy


def check_changes(hardware, baseline, candidate):
    if set(hardware) != set(baseline) or set(baseline) != set(candidate):
        raise ValueError('legacy descriptors changed or missing')
    repairs = []
    for case, new in candidate.items():
        old, hw = baseline[case], hardware[case]
        fields = {k for k in new if old[k] != new[k]}
        if not fields:
            continue
        if (not fields <= {'end_ref', 'reference_ticks'} or 'end_ref' not in fields
                or (new['end_ref'] ^ old['end_ref']) & ~64
                or new['end_ref'] != hw['end_ref']
                or any(new[k] != hw[k] for k in ('launch_beam', 'launch_ref', 'end_beam'))):
            raise ValueError('unexplained legacy field or qualification change: ' + str(case))
        repairs.append(case)
    return dict(historical_native_field_repairs=len(repairs), regressions=0,
                representatives=repairs[:3],
                evidence_class='Historical corroboration; no restoration provenance upgrade')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('before', 'after', 'binary', 'config'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    e.packets(a.before, a.after, ['bzero-edges', 'copper-busy'], a.binary, a.config)
    if e.packets(a.before, a.after, ['bzero-edges'], a.binary, a.config)['status'] != 'unchanged':
        raise ValueError('legacy BZERO packets changed')
    hw_meta, hw = busy.load(ROOT/'references/copper-busy-kind50')
    old_meta, old = busy.load(a.before/'copper-busy')
    new_meta, new = busy.load(a.after/'copper-busy')
    if len({m['source_id'] for m in (hw_meta, old_meta, new_meta)}) != 1:
        raise ValueError('legacy source identities differ')
    if any(busy.validate(r) for rows in (hw, old, new) for r in rows.values()):
        raise ValueError('invalid legacy capture')
    result = check_changes(hw, old, new)
    e.write(a.after/'native-request-gate.json', result)
    print(json.dumps(result))

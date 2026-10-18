#!/usr/bin/env python3
"""Assess held-out DMACONR sampling repairs/regressions on common launch cohorts."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import compare_copper_busy
import rom_results

REFERENCES = {"copper-busy": "copper-busy-kind50", "blitter-handoff": "blitter-handoff-kind49", "bzero-edges": "bzero-edges-kind22"}


def load(path):
    meta, rows = rom_results.decode((path / "results.bin").read_bytes())
    indexed = {tuple(row[k] for k in rom_results.FIELDS[:6]): row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError("duplicate descriptors")
    return meta, indexed


def measures(row):
    if row["kind"] == 50:
        values = compare_copper_busy.samples(row)
        return {f"sample{i}_{name}": value & mask for i, value in enumerate(values)
                for name, mask in (("busy", 0x4000), ("zero", 0x2000))}
    if row["kind"] == 49:
        return {"final_first_d": row["irq_beam"], "final_last_d": row["irq_level"],
                "early_d": row["end_beam"], "first_clear_zero": row["launch_ref"] & 0x2000,
                "postwrite_busy": row["end_ref"] & 0x4000, "postwrite_zero": row["end_ref"] & 0x2000,
                "handoff_beam": row["counter"], "postwrite_beam": row["icr"]}
    if row["kind"] == 22:
        return {"busy": row["counter"] & 0x4000, "zero": row["counter"] & 0x2000,
                "post_sample_beam": row["end_beam"]}
    raise ValueError("unsupported measurement layout")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = {"alignment": "none; common exact descriptor and recorded launch; kind50 also exact post-sample bracket",
              "units": "raw flags, destination words and packed beam words; no inferred cycle deltas", "suites": {}}
    for suite, reference in REFERENCES.items():
        hm, hw = load(ROOT / "references" / reference)
        bm, before = load(args.before / suite)
        am, after = load(args.after / suite)
        if len({m["source_id"] for m in (hm, bm, am)}) != 1:
            raise ValueError("source_id mismatch")
        if hw.keys() != before.keys() or hw.keys() != after.keys():
            raise ValueError("missing/extra descriptors")
        totals = Counter(eligible=0, different_launch=0, before_mismatch=0, after_mismatch=0, repaired=0, regressed=0, still_mismatched=0)
        fields = {}
        examples = {"repaired": [], "regressed": [], "still_mismatched": []}
        for key, h in hw.items():
            b, a = before[key], after[key]
            alignment = ("launch_beam", "launch_ref") if h["kind"] == 50 else ("launch_beam",)
            if any(h[f] != b[f] or h[f] != a[f] for f in alignment):
                totals["different_launch"] += 1
                continue
            totals["eligible"] += 1
            hv, bv, av = measures(h), measures(b), measures(a)
            bd = [f for f in hv if hv[f] != bv[f]]
            ad = [f for f in hv if hv[f] != av[f]]
            totals["before_mismatch"] += bool(bd)
            totals["after_mismatch"] += bool(ad)
            for field in hv:
                count = fields.setdefault(field, {"before": 0, "after": 0})
                count["before"] += hv[field] != bv[field]
                count["after"] += hv[field] != av[field]
            outcome = "repaired" if bd and not ad else "regressed" if ad and not bd else "still_mismatched" if ad else None
            if outcome:
                totals[outcome] += 1
                if len(examples[outcome]) < 3:
                    examples[outcome].append({"case": ":".join(map(str, key)), "before_fields": bd, "after_fields": ad})
        report["suites"][suite] = {"counts": dict(totals), "fields": fields, "examples": examples}
        print(suite + ": " + json.dumps(dict(totals), sort_keys=True))
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Report: {args.out}")


if __name__ == "__main__":
    main()

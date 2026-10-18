#!/usr/bin/env python3
"""Compare kind50 DMACONR samples at identical observed beam brackets."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import rom_results

DESCRIPTOR = tuple(rom_results.FIELDS[:6])


def key(row):
    return tuple(row[field] for field in DESCRIPTOR)


def samples(row):
    values = [row["counter"], row["icr"], row["irq_beam"], row["irq_level"],
              row["saved_pc_offset"] >> 16, row["saved_pc_offset"] & 0xffff,
              row["status"], row["aux"]]
    return values if row["variant"] & 2 else values[:1]


def load(path):
    path = Path(path)
    if path.is_dir():
        path = path / ("results.bin" if (path / "results.bin").exists() else "capture/results.bin")
    metadata, rows = rom_results.decode(path.read_bytes())
    indexed = {key(row): row for row in rows}
    if len(indexed) != len(rows) or any(row["kind"] != 50 for row in rows):
        raise ValueError("expected unique kind50 descriptors")
    return metadata, indexed


def validate(row):
    if row["target"] not in range(3) or row["variant"] not in range(8) or row["phase"] not in range(11):
        return "invalid descriptor"
    if row["delay"] != 0 or row["repeat"] not in (0, 1):
        return "invalid descriptor"
    if any(row[field] == 0xffff for field in ("launch_beam", "launch_ref", "end_beam")):
        return "gate or marker timeout sentinel"
    expected = 0xdead if row["variant"] & 4 else 0xffff
    if any(row[field] != expected for field in ("second_counter_or_beam", "second_icr_or_level")):
        return "settled destination differs"
    return None


def compare(reference, candidate, selected=None):
    counts = Counter(total=0, missing=0, invalid=0, different_brackets=0, comparable=0, match=0, mismatch=0)
    groups = defaultdict(list)
    detail = None
    for descriptor in sorted(reference.keys() | candidate.keys()):
        left, right = reference.get(descriptor), candidate.get(descriptor)
        counts["total"] += 1
        reason = None
        if left is None or right is None:
            status = "missing"
        elif (reason := validate(left) or validate(right)):
            status = "invalid"
        elif any(left[field] != right[field] for field in ("launch_beam", "launch_ref")):
            status = "different_brackets"
        else:
            counts["comparable"] += 1
            status = "match" if samples(left) == samples(right) else "mismatch"
        counts[status] += 1
        identity = ":".join(map(str, descriptor))
        if status == "mismatch":
            pattern = (descriptor[1], descriptor[2], tuple(samples(left)), tuple(samples(right)))
            groups[pattern].append(identity)
        if identity == selected:
            detail = {"case": identity, "status": status, "reason": reason, "hardware": left, "candidate": right,
                      "hardware_samples": samples(left) if left else None,
                      "candidate_samples": samples(right) if right else None}
    if selected and detail is None:
        raise ValueError("selected case absent from both captures")
    patterns = [{"width_words": (1, 8, 16)[target], "variant": variant,
                 "hardware_samples_hex": [f"{v:04x}" for v in left],
                 "candidate_samples_hex": [f"{v:04x}" for v in right],
                 "hardware_busy": "".join(str(int(bool(v & 0x4000))) for v in left),
                 "candidate_busy": "".join(str(int(bool(v & 0x4000))) for v in right),
                 "first_different_sample": next(i for i, (a, b) in enumerate(zip(left, right)) if a != b),
                 "count": len(ids), "representative_cases": ids[:3]}
                for (target, variant, left, right), ids in sorted(groups.items(), key=lambda x: (-len(x[1]), x[0]))]
    return {"counts": dict(counts), "patterns": patterns, "detail": detail}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hardware", type=Path, required=True)
    parser.add_argument("--copperline", type=Path, required=True)
    parser.add_argument("--winuae", type=Path)
    parser.add_argument("--case")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    protected = set()
    for path in (args.hardware, args.copperline, args.winuae):
        if path is None:
            continue
        if path.is_dir():
            protected.update((path / name).resolve() for name in ("results.bin", "results.json", "manifest.json", "capture/results.bin", "capture/results.json"))
        else:
            protected.add(path.resolve())
    if args.out.resolve() in protected:
        parser.error("report must not overwrite input measurements or provenance")
    hardware_meta, hardware = load(args.hardware)
    report = {"scope": "kind50; raw status/aux/PC slots are DMACONR samples, not timeout/status/PC fields",
              "alignment": "none; identical descriptor and both pre/post VHPOSR brackets required",
              "units": "raw DMACONR register words; BBUSY is bit 14; sample indices are not cycle counts",
              "limits": "Equal brackets do not prove identical internal transfer slots. No phase-adjusted rows included.",
              "source_id": hardware_meta["source_id"], "comparisons": {}}
    report["inputs"] = {name: str(path.resolve()) for name, path in
                        (("hardware", args.hardware), ("copperline", args.copperline), ("winuae", args.winuae)) if path is not None}
    for name, path in (("copperline", args.copperline), ("winuae", args.winuae)):
        if path is None:
            continue
        meta, rows = load(path)
        if meta["source_id"] != hardware_meta["source_id"]:
            raise ValueError("source_id mismatch")
        result = compare(hardware, rows, args.case)
        report["comparisons"][name] = result
        print(name + ": " + json.dumps(result["counts"], sort_keys=True))
        print(json.dumps(result["detail"] if args.case else result["patterns"][:3]))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Report: {args.out}")


if __name__ == "__main__":
    main()

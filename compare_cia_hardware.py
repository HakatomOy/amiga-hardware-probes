#!/usr/bin/env python3
"""Compact, typed analysis of kinds 52/53/54, qualified by measured underflows."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import rom_results

DESCRIPTOR = tuple(rom_results.FIELDS[:6])


def load(path):
    path = Path(path)
    if path.is_dir():
        path = path / ("results.bin" if (path / "results.bin").exists() else "capture/results.bin")
    meta, rows = rom_results.decode(path.read_bytes())
    if any(r["kind"] not in (52, 53, 54) or r["status"] for r in rows):
        raise ValueError("expected successful kind52/53/54 observations")
    if len({tuple(r[k] for k in DESCRIPTOR) for r in rows}) != len(rows):
        raise ValueError("duplicate descriptors")
    for row in rows:
        before, after, stopped = [65535 - row[f] for f in ("launch_ref", "end_ref", "second_icr_or_level")]
        if not 0 <= before <= after <= stopped < 255:
            raise ValueError("underflow brackets out of order or at 16-bit read-tear boundary")
    return meta, rows


def summarize(rows):
    serial = defaultdict(list)
    pb = defaultdict(list)
    for r in rows:
        group = (r["target"], r["variant"], r["phase"]) if r["kind"] == 52 else (r["kind"], r["target"], r["variant"], r["phase"])
        (serial if r["kind"] == 52 else pb)[group].append(r)
    serial_groups = []
    for group, members in sorted(serial.items()):
        stable = [r for r in members if r["launch_ref"] == r["end_ref"]]
        serial_groups.append({"cia": group[0], "mask_enabled": group[1], "latch": (0, 1, 3, 15, 200)[group[2]],
                              "records": len(members), "stable_bracket_records": len(stable),
                              "stable_uf_with_sp_clear": sorted({65535-r["launch_ref"] for r in stable if not r["counter"] & 8}),
                              "stable_uf_with_sp_set": sorted({65535-r["launch_ref"] for r in stable if r["counter"] & 8}),
                              "sp_set_count": sum(bool(r["counter"] & 8) for r in members)})
    pb_groups = []
    for group, members in sorted(pb.items()):
        toggle = group[2] & 1
        pb_groups.append({"kind": group[0], "cia": group[1], "mode": group[2], "latch": (0, 1, 3, 15, 200)[group[3]],
                          "records": len(members),
                          "settled_pb6_counts": dict(Counter(int(bool(r["icr"] & 0x40)) for r in members)),
                          "retained_initial_parity_failures": sum(bool(r["icr"] & 0x40) != (bool(r["aux"] & 0x40) ^ bool((65535-r["second_icr_or_level"]) & 1)) for r in members) if toggle else None,
                          "start_high_parity_failures": sum(bool(r["icr"] & 0x40) != (not bool((65535-r["second_icr_or_level"]) & 1)) for r in members) if toggle else None})
    return {"serial": serial_groups, "pb": pb_groups}


def compare(left, right):
    reference = {tuple(r[k] for k in DESCRIPTOR): r for r in left}
    candidate = {tuple(r[k] for k in DESCRIPTOR): r for r in right}
    counts = Counter(total=0, missing=0, comparable=0, different_underflow_brackets=0, match=0, mismatch=0)
    groups = defaultdict(list)
    bracket_groups = defaultdict(list)
    for key in sorted(reference.keys() | candidate.keys()):
        a, b = reference.get(key), candidate.get(key)
        counts["total"] += 1
        if a is None or b is None:
            counts["missing"] += 1
            continue
        qualification = ("launch_ref", "end_ref") if key[0] == 52 else ("second_icr_or_level",)
        if any(a[f] != b[f] for f in qualification):
            counts["different_underflow_brackets"] += 1
            delta = tuple((f, 65535-a[f], 65535-b[f]) for f in qualification if a[f] != b[f])
            bracket_groups[(key[0], key[1], key[2], delta)].append(":".join(map(str, key)))
            continue
        counts["comparable"] += 1
        if key[0] == 52:
            source_mask = 0x0008 if key[1] == 0 else 0x2000
            values_a = (a["counter"] & 0x88, a["irq_beam"] & source_mask)
            values_b = (b["counter"] & 0x88, b["irq_beam"] & source_mask)
            fields = ("SP_and_IR", "selected_INTREQ_before_ICR")
        else:
            values_a, values_b = (a["icr"] & 0x40,), (b["icr"] & 0x40,)
            fields = ("settled_PB6",)
        differences = tuple((f, x, y) for f, x, y in zip(fields, values_a, values_b) if x != y)
        counts["mismatch" if differences else "match"] += 1
        if differences:
            groups[(key[0], key[1], key[2], differences)].append(":".join(map(str, key)))
    patterns = [{"kind": key[0], "cia": key[1], "variant": key[2], "differences": key[3],
                 "count": len(ids), "representative_cases": ids[:3]}
                for key, ids in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))]
    brackets = [{"kind": key[0], "cia": key[1], "variant": key[2], "underflow_counts": key[3],
                 "count": len(ids), "representative_cases": ids[:3]}
                for key, ids in sorted(bracket_groups.items(), key=lambda item: (-len(item[1]), item[0]))]
    return {"counts": dict(counts), "patterns": patterns, "different_underflow_patterns": brackets}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hardware", type=Path, required=True)
    p.add_argument("--candidate", type=Path)
    p.add_argument("--case", help="kind:target:variant:latch_index:delay:repeat")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    protected = set()
    for path in (a.hardware, a.candidate):
        if path is not None:
            protected.add(path.resolve())
            if path.is_dir():
                protected.update((path / f).resolve() for f in ("results.bin", "results.json", "manifest.json", "capture/results.bin", "capture/results.json"))
    if a.out.resolve() in protected:
        p.error("report must not overwrite capture or provenance")
    meta, rows = load(a.hardware)
    report = {"units": "raw registers and measured TA underflow counts; no phase alignment",
              "hardware_metadata": meta, "hardware": summarize(rows)}
    report["inputs"] = {"hardware": str(a.hardware.resolve()), "candidate": str(a.candidate.resolve()) if a.candidate else None}
    if a.candidate:
        other_meta, other = load(a.candidate)
        if meta["source_id"] != other_meta["source_id"]:
            raise ValueError("source_id mismatch")
        report["candidate_metadata"] = other_meta
        report["candidate"] = summarize(other)
        report["comparison"] = compare(rows, other)
        print(json.dumps(report["comparison"]["counts"], sort_keys=True))
        if not a.case:
            print(json.dumps(report["comparison"]["patterns"][:4]))
    if a.case:
        descriptor = tuple(map(int, a.case.split(":")))
        report["detail"] = {"hardware": next((r for r in rows if tuple(r[k] for k in DESCRIPTOR) == descriptor), None)}
        if a.candidate:
            report["detail"]["candidate"] = next((r for r in other if tuple(r[k] for k in DESCRIPTOR) == descriptor), None)
        if not any(report["detail"].values()):
            p.error("case not present")
        print(json.dumps(report["detail"], indent=2))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Report: {a.out}")


if __name__ == "__main__":
    main()

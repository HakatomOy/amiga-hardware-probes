#!/usr/bin/env python3
"""Compare kind55 marker/status traces on identical recorded beam brackets."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import rom_results

DESCRIPTOR = rom_results.FIELDS[:6]


def case_id(key):
    return ":".join(map(str, key))


def samples(row):
    pc = row["saved_pc_offset"]
    return (row["counter"] & 0x14, row["icr"] & 0x6000,
            row["irq_beam"] & 0x14, row["irq_level"] & 0x6000,
            (pc >> 16) & 0x14, pc & 0x6000,
            row["status"] & 0x14, row["aux"] & 0x6000)


def load(path):
    path = Path(path)
    directory = path if path.is_dir() else path.parent
    profile = {}
    for name in ("manifest.json", "build-manifest.json"):
        manifest = directory / name
        if manifest.is_file():
            document = json.loads(manifest.read_text())
            profile = document.get("bus_marker", document.get("observation_profile", {}))
            break
    if path.is_dir():
        path = path / ("results.bin" if (path / "results.bin").exists() else "capture/results.bin")
    meta, rows = rom_results.decode(path.read_bytes())
    if len({tuple(r[k] for k in DESCRIPTOR) for r in rows}) != len(rows):
        raise ValueError("duplicate descriptors")
    for r in rows:
        if r["kind"] != 55 or r["target"] not in (0, 1) or r["variant"] not in range(16):
            raise ValueError("invalid descriptor")
        if r["launch_beam"] == 0xffff or r["launch_ref"] == 0xffff or r["end_beam"] == 0xffff:
            raise ValueError("watchdog expired")
        expected = 0xdead if r["variant"] & 8 else 0xffff
        if (r["second_counter_or_beam"], r["second_icr_or_level"]) != (expected, expected):
            raise ValueError("unsettled or incorrect destination")
        required = 0x14 if profile.get("completion_marker") else 0x10
        if r["end_ref"] & required != required:
            raise ValueError("marker missing after settling")
    return meta, rows


def compare(left, right):
    a = {tuple(r[k] for k in DESCRIPTOR): r for r in left}
    b = {tuple(r[k] for k in DESCRIPTOR): r for r in right}
    counts = Counter(total=0, comparable=0, match=0, mismatch=0, missing=0, different_brackets=0)
    groups = defaultdict(list)
    bracket_groups = defaultdict(list)
    families = Counter()
    for key in sorted(a.keys() | b.keys()):
        counts["total"] += 1
        if key not in a or key not in b:
            counts["missing"] += 1
            continue
        h, e = a[key], b[key]
        if any(h[f] != e[f] for f in ("launch_beam", "launch_ref")):
            counts["different_brackets"] += 1
            bracket_groups[(key[1], key[2])].append(case_id(key))
            continue
        counts["comparable"] += 1
        hs, es = samples(h), samples(e)
        differences = tuple((i, x, y) for i, (x, y) in enumerate(zip(hs, es)) if x != y)
        counts["mismatch" if differences else "match"] += 1
        if differences:
            groups[(key[1], key[2], differences)].append(case_id(key))
            marker = any(i % 2 == 0 for i, _, _ in differences)
            status = any(i % 2 == 1 for i, _, _ in differences)
            family = "marker_and_status" if marker and status else "marker_only" if marker else "status_only"
            families[("CPU" if key[2] & 2 else "Copper", bool(key[2] & 8), family)] += 1
    patterns = [{"width": (1, 16)[key[0]], "variant": key[1], "differences": key[2],
                 "count": len(ids), "representatives": ids[:3],
                 "first_divergent_read": key[2][0][0],
                 "detail": "--case " + ids[0]}
                for key, ids in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))]
    return {"counts": dict(counts), "patterns": patterns,
            "families": [{"owner": key[0], "no_blit": key[1], "pattern": key[2], "count": count}
                         for key, count in sorted(families.items())],
            "different_bracket_groups": [{"width": (1, 16)[key[0]], "variant": key[1],
                                           "count": len(ids), "representatives": ids[:3]}
                                          for key, ids in sorted(bracket_groups.items())]}


def compare_cohorts(hardware, candidate):
    """Match recorded phases across repeats, never adjust a timestamp/read."""
    reference = defaultdict(list)
    for row in hardware:
        key = tuple(row[f] for f in DESCRIPTOR[:-1]) + (row["launch_beam"], row["launch_ref"])
        reference[key].append(row)
    counts = Counter(candidate_cases=len(candidate), comparable=0, match=0, mismatch=0,
                     no_identical_bracket=0, unstable_reference=0)
    groups = defaultdict(list)
    for row in candidate:
        key = tuple(row[f] for f in DESCRIPTOR[:-1]) + (row["launch_beam"], row["launch_ref"])
        matches = reference.get(key, [])
        if not matches:
            counts["no_identical_bracket"] += 1
            continue
        traces = {samples(r) for r in matches}
        if len(traces) != 1:
            counts["unstable_reference"] += 1
            continue
        counts["comparable"] += 1
        expected, actual = next(iter(traces)), samples(row)
        differences = tuple((i, a, b) for i, (a, b) in enumerate(zip(expected, actual)) if a != b)
        counts["mismatch" if differences else "match"] += 1
        if differences:
            groups[(row["target"], row["variant"], differences)].append({
                "candidate": case_id(tuple(row[f] for f in DESCRIPTOR)),
                "hardware": [case_id(tuple(r[f] for f in DESCRIPTOR)) for r in matches],
                "brackets": [row["launch_beam"], row["launch_ref"]],
                "hardware_trace": expected, "candidate_trace": actual})
    return {"rule": "identical configuration excluding repeat, exact recorded pre/post beam; no shifting; counts are candidate cases, hardware observations may be reused",
            "counts": dict(counts),
            "patterns": [{"width": (1, 16)[key[0]], "variant": key[1], "differences": key[2],
                          "count": len(rows), "first_divergent_read": key[2][0][0], "representatives": rows[:3]}
                         for key, rows in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hardware", type=Path, required=True)
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--case")
    p.add_argument("--cohorts", action="store_true", help="also compare exact recorded phases across repetitions")
    args = p.parse_args()
    protected = set()
    for path in (args.hardware, args.candidate):
        protected.add(path.resolve())
        if path.is_dir():
            protected.update((path / name).resolve() for name in ("results.bin", "results.json", "manifest.json", "build-manifest.json", "capture/results.bin", "capture/results.json"))
    if args.out.resolve() in protected:
        p.error("output must not overwrite capture or provenance")
    hm, hw = load(args.hardware)
    em, emu = load(args.candidate)
    if hm["source_id"] != em["source_id"]:
        raise ValueError("source_id mismatch")
    report = {"hardware_metadata": hm, "candidate_metadata": em,
              "alignment": "none; identical pre/post beam brackets required",
              "units": "four sequential INTREQR/DMACONR pairs; read indices, not cycle offsets",
              "comparison": compare(hw, emu)}
    if args.cohorts:
        report["phase_cohorts"] = compare_cohorts(hw, emu)
        print("Phase cohorts:", json.dumps(report["phase_cohorts"]["counts"], sort_keys=True))
        print(json.dumps(report["phase_cohorts"]["patterns"][:3]))
    if args.case:
        key = tuple(map(int, args.case.split(":")))
        report["detail"] = {}
        for name, rows in (("hardware", hw), ("candidate", emu)):
            row = next((r for r in rows if tuple(r[k] for k in DESCRIPTOR) == key), None)
            report["detail"][name] = {"row": row, "trace": samples(row) if row else None}
        if not any(v["row"] for v in report["detail"].values()):
            p.error("case not found")
        print(json.dumps(report["detail"], indent=2))
    else:
        print(json.dumps(report["comparison"]["counts"], sort_keys=True))
        print(json.dumps(report["comparison"]["patterns"][:4]))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print("Report:", args.out)


if __name__ == "__main__":
    main()

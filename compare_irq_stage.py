#!/usr/bin/env python3
"""Compare kind56/57/58 exact release/read-bracket cohorts without timing alignment."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import rom_results
from build_irq_stage_rom import TARGETS, SOURCES, MASKS
from build_cpu_irq_rom import SOURCES as CPU_SOURCES, MASKS as CPU_MASKS

SOURCES = SOURCES + ("CIA_A_PRELATCHED_UNMASK", "CIA_B_PRELATCHED_UNMASK")
MASKS = MASKS + (8, 0x2000)

def source_name(row):
    return (CPU_SOURCES if row["kind"] == 58 else SOURCES)[row["variant"]]


def source_mask(row):
    return (CPU_MASKS if row["kind"] == 58 else MASKS)[row["variant"]]


DESC = tuple(rom_results.FIELDS[:6])


def key(row):
    return tuple(row[f] for f in DESC)


def beams(row):
    return (row["irq_level"], row["saved_pc_offset"] >> 16,
            row["saved_pc_offset"] & 65535, row["aux"])


def cohort(row):
    calibration = (row["end_beam"], row["second_counter_or_beam"]) if row["kind"] == 57 else ()
    return key(row)[:-1] + (row["launch_beam"], row["launch_ref"]) + calibration + (beams(row) if row["target"] == 4 else ())


def measures(row):
    if row["target"] == 4:
        mask = source_mask(row)
        settled = "end_ref" if row["kind"] == 57 else "second_counter_or_beam"
        return {name: row[f] & mask for name, f in
                (("raw0", "counter"), ("raw1", "icr"), ("raw2", "irq_beam"),
                 ("settled", settled))}
    fields = ("end_ref", "counter", "icr", "irq_beam", "irq_level", "saved_pc_offset", "aux")
    if row["kind"] != 57:
        fields += ("second_counter_or_beam", "second_icr_or_level")
    return {f: row[f] for f in fields}


def validate(row):
    valid_source = row["variant"] in ((0, 2, 5, 6) if row["kind"] == 57 else range(6) if row["kind"] == 58 else range(5))
    if row["kind"] not in (56, 57, 58) or not 0 <= row["target"] < 5 or not valid_source:
        raise ValueError("unexpected kind/target/source")
    if not 0 <= row["phase"] < 4 or not 0 <= row["delay"] < 8 or row["repeat"] not in (range(5) if row["kind"] == 57 else range(2)):
        raise ValueError("descriptor outside the experiment matrix")
    if row["status"]:
        raise ValueError(f"{key(row)}: failed/missed interrupt status={row['status']}")
    if row["target"] == 4:
        settled = row["end_ref"] if row["kind"] == 57 else row["second_counter_or_beam"]
        mask_ok = row["kind"] == 57 or row["second_icr_or_level"] == source_mask(row)
        if not mask_ok or not settled & source_mask(row):
            raise ValueError(f"{key(row)}: masked source never latched")
    elif row["aux"] != 1 or row["irq_level"] != ((2, 6, 2, 6, 3, 3) if row["kind"] == 58 else (2, 3, 6, 2, 6, 2, 6))[row["variant"]]:
        raise ValueError(f"{key(row)}: duplicate/wrong-level/watchdog event")


def load(path):
    path = Path(path)
    meta, rows = rom_results.decode((path / "results.bin" if path.is_dir() else path).read_bytes())
    if len({key(r) for r in rows}) != len(rows):
        raise ValueError("duplicate descriptor")
    for row in rows:
        validate(row)
    return meta, rows


def compare(hardware, candidate):
    ref = defaultdict(list)
    for r in hardware:
        validate(r)
        ref[cohort(r)].append(r)
    conflicts = sum(len({tuple(measures(r).items()) for r in rows}) > 1 for rows in ref.values())
    counts = Counter(total=len(candidate), matches=0, mismatches=0, missing_results=0,
                     no_identical_bracket=0, unstable_reference=0, invalid_captures=0,
                     reference_conflicting_cohorts=conflicts)
    counts["missing_results"] = len({key(r) for r in hardware} - {key(r) for r in candidate})
    groups = defaultdict(list)
    by_mode_source = defaultdict(Counter)
    for r in candidate:
        validate(r)
        matches = ref.get(cohort(r), [])
        bucket = by_mode_source[TARGETS[r["target"]] + ":" + source_name(r)]
        if not matches:
            counts["no_identical_bracket"] += 1
            bucket["excluded"] += 1
            continue
        values = {tuple(measures(h).items()) for h in matches}
        if len(values) != 1:
            counts["unstable_reference"] += 1
            continue
        expected, actual = dict(next(iter(values))), measures(r)
        diff = tuple((f, expected[f], actual[f]) for f in expected if expected[f] != actual[f])
        outcome = "mismatches" if diff else "matches"
        counts[outcome] += 1
        bucket[outcome] += 1
        if diff:
            groups[(r["target"], source_name(r), diff)].append(
                dict(candidate=key(r), hardware=[key(h) for h in matches],
                     release_brackets=[r["launch_beam"], r["launch_ref"]],
                     differences=diff, expected=expected, actual=actual))
    return dict(counts=dict(counts), by_mode_source={k: dict(v) for k, v in by_mode_source.items()},
        groups=[dict(target=TARGETS[t], source=s, count=len(rows),
                     first_divergent_field=diff[0][0], representatives=rows[:3])
                for (t, s, diff), rows in sorted(groups.items(), key=lambda x: (-len(x[1]), x[0]))])


def calibration_summary(rows):
    """Independent phase evidence, never derived from interrupt outcomes."""
    pairs = Counter((r["end_beam"], r["second_counter_or_beam"])
                    for r in rows if r["kind"] == 57)
    return [dict(pre=f"{pre:04x}", post=f"{post:04x}", cases=count)
            for (pre, post), count in sorted(pairs.items())]


def software_summary(report):
    total = sum(v.get("matches", 0) + v.get("mismatches", 0)
                for k, v in report["by_mode_source"].items() if ":COPPER_" in k or ":CPU_" in k)
    timing = diagnostic = 0
    for g in report["groups"]:
        if not g["source"].startswith(("COPPER_", "CPU_")):
            continue
        fields = {d[0] for d in g["representatives"][0]["differences"]}
        timing += g["count"] if fields - {"end_ref"} else 0
        diagnostic += g["count"] if "end_ref" in fields else 0
    return dict(comparable=total, timing_or_visibility_mismatches=timing,
                diagnostic_cia_icr_mismatches=diagnostic)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hardware", type=Path, required=True, action="append", help="repeat to pool independent runs and exclude conflicting reference cohorts")
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    captures = [(path, *load(path)) for path in a.hardware]
    cm, c = load(a.candidate)
    if any(meta["source_id"] != cm["source_id"] for _, meta, _ in captures):
        raise ValueError("source identity differs")
    h = [row for _, _, rows in captures for row in rows]
    report = compare(h, c)
    report["software_requests"] = software_summary(report)
    report["independent_calibration"] = dict(
        hardware=[dict(path=str(path), brackets=calibration_summary(rows))
                  for path, _, rows in captures], candidate=calibration_summary(c))
    report.update(hardware=[str(path) for path, _, _ in captures],
                  reference_hashes=[meta["sha256"] for _, meta, _ in captures],
                  candidate=str(a.candidate), source_id=cm["source_id"],
                  alignment="none; exact release brackets and kind57 independent calibration; masked controls also require all read brackets",
                  units="raw register words, absolute PC, encoded beam; no packed-word subtraction")
    a.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["counts"]))
    print(json.dumps(report["software_requests"]))
    print("groups:", len(report["groups"]), "detail:", a.out)

#!/usr/bin/env python3
"""Compare kind51 emulator and A500 captures on exact observed-start cohorts."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from compare_cia_cpu_irq import TARGETS, SOURCES, beam_linear, load


MEASURES = {
    "irq_beam_encoded": lambda r: r["irq_beam"],
    "irq_beam_227v_plus_h": lambda r: beam_linear(r["irq_beam"]),
    "d1_at_irq": lambda r: r["counter"],
    "a1_low_at_irq": lambda r: r["icr"],
    "cia_icr_at_irq": lambda r: r["end_ref"],
    "stacked_pc_offset": lambda r: r["saved_pc_offset"],
    "irq_level": lambda r: r["irq_level"],
}
DESC_KEYS = ("kind", "target", "variant", "phase", "delay", "repeat")


def exact_pair(left, right, descriptor):
    a, b = left.get(descriptor), right.get(descriptor)
    if a is None or b is None:
        return None
    # +12 is post-start VHPOSR; +14 is pre-start VHPOSR.
    if (a["launch_beam"], a["launch_ref"]) != (b["launch_beam"], b["launch_ref"]):
        return None
    return a, b


def label(desc):
    _, target, source, phase, offset, repeat = desc
    return {"descriptor": list(desc), "source": SOURCES[source][0],
            "operation": TARGETS[target][0], "storage": TARGETS[target][1],
            "phase": phase, "event_offset": offset, "repeat": repeat}


def compare_rows(left, right, descriptors):
    groups = defaultdict(list)
    for desc in descriptors:
        pair = exact_pair(left, right, desc)
        if pair is None:
            raise ValueError(f"non-exact row passed into common cohort: {desc}")
        a, b = pair
        _, target, source, *_ = desc
        groups[(source, target)].append((desc, a, b))
    summary, detailed = [], []
    for (source, target), rows in sorted(groups.items()):
        hist = {field: Counter() for field in MEASURES}
        mismatch = Counter()
        for desc, a, b in rows:
            values_a = {name: fn(a) for name, fn in MEASURES.items()}
            values_b = {name: fn(b) for name, fn in MEASURES.items()}
            deltas = {name: values_b[name] - values_a[name] for name in MEASURES}
            for name, delta in deltas.items():
                hist[name][delta] += 1
                if delta:
                    mismatch[name] += 1
            detailed.append({**label(desc),
                             "post_start_vhposr": a["launch_beam"],
                             "pre_start_vhposr": a["launch_ref"],
                             "left": values_a, "right": values_b, "right_minus_left": deltas})
        summary.append({"source": SOURCES[source][0], "operation": TARGETS[target][0],
                        "storage": TARGETS[target][1], "n": len(rows),
                        "mismatch_counts": dict(mismatch),
                        "right_minus_left_counts": {field: dict(sorted(counter.items()))
                                                    for field, counter in hist.items()}})
    return {"matched_row_count": len(detailed), "groups": summary, "matched_rows": detailed}


def collect(path):
    meta, rows = load(path)
    invocation_path = path.parent / "invocation.json"
    invocation = json.loads(invocation_path.read_text()) if invocation_path.exists() else None
    return {"path": str(path), "metadata": meta, "records": rows,
            "invocation": invocation}


def common_descriptors(systems, names):
    first = systems[names[0]]["records"]
    result = []
    for desc, row in first.items():
        if all(desc in systems[n]["records"] and
               (systems[n]["records"][desc]["launch_beam"], systems[n]["records"][desc]["launch_ref"])
               == (row["launch_beam"], row["launch_ref"]) for n in names[1:]):
            result.append(desc)
    return result


def exact_count(left, right):
    return sum(exact_pair(left, right, desc) is not None for desc in left.keys() & right.keys())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--winuae", type=Path, required=True)
    p.add_argument("--hardware-run1", type=Path, required=True)
    p.add_argument("--hardware-run2", type=Path, required=True)
    p.add_argument("--before", type=Path, required=True, help="original Copperline release capture")
    p.add_argument("--scoped-zero", type=Path, required=True, help="CIA-scoped zero-CCK capture")
    p.add_argument("--one-cck", type=Path, required=True, help="CIA-scoped one-CCK capture")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    inputs = {"winuae": a.winuae, "hardware_run1": a.hardware_run1,
              "hardware_run2": a.hardware_run2, "before": a.before,
              "scoped_zero": a.scoped_zero, "one_cck": a.one_cck}
    systems = {name: collect(path) for name, path in inputs.items()}
    source_ids = {data["metadata"]["source_id"] for data in systems.values()}
    if len(source_ids) != 1:
        raise ValueError("all captures must have the same immutable source_id")

    comparison_names = ("winuae", "before", "scoped_zero", "one_cck")
    comparisons = {}
    for hw_name in ("hardware_run1", "hardware_run2"):
        hw = systems[hw_name]["records"]
        comparisons[hw_name] = {}
        for other_name in comparison_names:
            other = systems[other_name]["records"]
            matched = [desc for desc in hw.keys() & other.keys()
                       if exact_pair(hw, other, desc) is not None]
            comparisons[hw_name][other_name] = compare_rows(hw, other, matched)

    pairwise_hardware_repeatability = {}
    hw1, hw2 = (systems[n]["records"] for n in ("hardware_run1", "hardware_run2"))
    repeat_desc = [desc for desc in hw1.keys() & hw2.keys() if exact_pair(hw1, hw2, desc) is not None]
    pairwise_hardware_repeatability = compare_rows(hw1, hw2, repeat_desc)

    # This intersection compares original, scoped-zero and one-CCK on identical
    # descriptors and observed starts within each physical run.
    fair_cohorts = {}
    for hw_name in ("hardware_run1", "hardware_run2"):
        names = (hw_name, "before", "scoped_zero", "one_cck")
        descriptors = common_descriptors(systems, names)
        hw = systems[hw_name]["records"]
        fair_cohorts[hw_name] = {
            "definition": "same descriptor and exact +12 post-start plus +14 pre-start VHPOSR across hardware, original, scoped-zero, and one-CCK captures",
            "count": len(descriptors),
            "original_vs_hardware": compare_rows(hw, systems["before"]["records"], descriptors),
            "scoped_zero_vs_hardware": compare_rows(hw, systems["scoped_zero"]["records"], descriptors),
            "one_cck_vs_hardware": compare_rows(hw, systems["one_cck"]["records"], descriptors),
            "one_cck_vs_original": compare_rows(systems["before"]["records"], systems["one_cck"]["records"], descriptors),
            "one_cck_vs_scoped_zero": compare_rows(systems["scoped_zero"]["records"], systems["one_cck"]["records"], descriptors),
        }

    report = {
        "scope": "kind51 hardware/emulator comparison; no averages across unmatched launch cohorts",
        "source_id": next(iter(source_ids)),
        "matching_rule": "Rows match only when the full six-word descriptor and both captured starts (+12 post-start VHPOSR, +14 pre-start VHPOSR) are exactly equal.",
        "capture_provenance": {name: {"path": data["path"], "metadata": data["metadata"],
                                      "invocation": data["invocation"]}
                               for name, data in systems.items()},
        "field_semantics": {"+12": "VHPOSR immediately after Timer-A CRA or COPJMP1 start",
                            "+14": "VHPOSR immediately before source start",
                            "+18": "selected CIA ICR at IRQ (zero for Copper)",
                            "+20": "D1 remaining at IRQ", "+22": "A1 low word at IRQ",
                            "+24": "first IRQ VHPOSR", "+26": "IRQ level",
                            "+28": "stacked PC offset normalized to loop entry"},
        "independent_route_checks": {
            name: {"record_count": data["metadata"]["record_count"],
                   "timeouts": data["metadata"]["timeouts"], "skipped": data["metadata"]["skipped"],
                   "source_counts": {SOURCES[s][0]: sum(r["variant"] == s for r in data["records"].values())
                                     for s in SOURCES},
                   "irq_level_counts": dict(Counter(r["irq_level"] for r in data["records"].values())),
                   "cia_a_icr": dict(Counter(r["end_ref"] for r in data["records"].values() if r["variant"] == 0)),
                   "coper_icr": sorted(set(r["end_ref"] for r in data["records"].values() if r["variant"] == 1)),
                   "cia_b_icr": dict(Counter(r["end_ref"] for r in data["records"].values() if r["variant"] == 2))}
            for name, data in systems.items()},
        "hardware_exact_cohorts": {hw: {other: result["matched_row_count"]
                                         for other, result in outcomes.items()}
                                   for hw, outcomes in comparisons.items()},
        "pairwise_hardware_repeatability": pairwise_hardware_repeatability,
        "strict_pairwise_comparisons": comparisons,
        "common_original_zero_one_cohorts": fair_cohorts,
        "interpretation_limits": [
            "Small exact cohorts remain small; judge source, operation, and storage groups separately.",
            "IRQ VHPOSR is retained both as raw encoding and 227*V+H; low-H samples near vertical boundaries may reflect register-read pipeline/wrap behavior, not event latency.",
            "Different CIA E-clock phase history is not proven equivalent by matching the two beam samples.",
            "A one-CCK route comparison is informative only on the common exact-start cohort; no timing average is computed across unmatched descriptors."],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"out": str(a.out), "hardware_exact_cohorts": report["hardware_exact_cohorts"],
                      "common_counts": {name: cohort["count"] for name, cohort in fair_cohorts.items()}}, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Compare A500 divider IRQ captures at matching launch beams."""
import argparse
from collections import Counter
import json
from pathlib import Path

DESCRIPTOR_FIELDS = ("kind", "target", "variant", "phase", "delay", "repeat")
METRICS = ("saved_pc_offset", "aux", "irq_beam", "final_result", "final_marker")


def load_capture(path):
    document = json.loads(Path(path).read_text())
    if not isinstance(document, dict) or not isinstance(document.get("metadata"), dict):
        raise ValueError(f"{path}: expected results.json with metadata and records")
    if not isinstance(document.get("records"), list):
        raise ValueError(f"{path}: missing records list")
    return document["metadata"], document["records"]


def _descriptor(row):
    try:
        return tuple(row[field] for field in DESCRIPTOR_FIELDS)
    except KeyError as exc:
        raise ValueError(f"Capture row is missing descriptor field {exc.args[0]}") from exc


def _result_fields(row):
    required = ("launch_beam", "status", "saved_pc_offset", "aux", "irq_beam",
                "counter", "icr", "second_icr_or_level")
    missing = [field for field in required if field not in row]
    if missing:
        raise ValueError("Capture row is missing fields: " + ", ".join(missing))
    return {
        "saved_pc_offset": row["saved_pc_offset"],
        "aux": row["aux"],
        "irq_beam": row["irq_beam"],
        "final_result": (row["counter"] << 16) | row["icr"],
        "final_marker": row["second_icr_or_level"],
    }


def _hex(value):
    return f"0x{value:08x}"


def compare(reference, candidate):
    """Compare decoded results.json documents and exclude unmatched launches/faults."""
    ref_meta, ref_rows = reference["metadata"], reference["records"]
    cand_meta, cand_rows = candidate["metadata"], candidate["records"]
    ref_source, cand_source = ref_meta.get("source_id"), cand_meta.get("source_id")
    if not isinstance(ref_source, str) or not ref_source.strip() \
            or not isinstance(cand_source, str) or not cand_source.strip():
        raise ValueError("Missing or empty source ID")
    if ref_source != cand_source:
        raise ValueError("Source ID mismatch")
    if len(ref_rows) != len(cand_rows):
        raise ValueError("Record-count mismatch")

    groups = {}
    exclusions = Counter()
    failures = []
    for index, (ref, cand) in enumerate(zip(ref_rows, cand_rows)):
        ref_desc, cand_desc = _descriptor(ref), _descriptor(cand)
        if ref_desc != cand_desc:
            raise ValueError(f"Descriptor mismatch at record {index}: {ref_desc} != {cand_desc}")
        kind, target, variant, phase, delay, repeat = ref_desc
        if kind != 20:
            continue
        key = (target, variant, phase)
        group = groups.setdefault(key, {
            "target": target, "variant": variant, "phase": phase,
            "records": 0, "matched_launch_status0": 0,
            "launch_beam_mismatches": 0, "unsuccessful": 0,
            "mismatches": Counter(), "delays": {},
        })
        group["records"] += 1
        if ref["launch_beam"] != cand["launch_beam"]:
            group["launch_beam_mismatches"] += 1
            exclusions["launch_beam_mismatch"] += 1
            continue
        if ref["status"] != 0 or cand["status"] != 0:
            group["unsuccessful"] += 1
            exclusions["nonzero_status"] += 1
            continue

        group["matched_launch_status0"] += 1
        delay_report = group["delays"].setdefault(str(delay), {
            "records": 0, "mismatches": Counter(),
            "reference_pc_distribution": Counter(),
            "candidate_pc_distribution": Counter(),
        })
        delay_report["records"] += 1
        delay_report["reference_pc_distribution"][_hex(ref["saved_pc_offset"])] += 1
        delay_report["candidate_pc_distribution"][_hex(cand["saved_pc_offset"])] += 1
        ref_values, cand_values = _result_fields(ref), _result_fields(cand)
        differences = {metric: [ref_values[metric], cand_values[metric]]
                       for metric in METRICS if ref_values[metric] != cand_values[metric]}
        for metric in differences:
            group["mismatches"][metric] += 1
            delay_report["mismatches"][metric] += 1
        if differences:
            failures.append({
                "target": target, "variant": variant, "phase": phase,
                "delay": delay, "repeat": repeat, "launch_beam": ref["launch_beam"],
                "differences": differences,
            })

    if not groups:
        raise ValueError("No kind20 divider records in capture")
    for group in groups.values():
        group["mismatches"] = dict(group["mismatches"])
        for delay in group["delays"].values():
            delay["mismatches"] = dict(delay["mismatches"])
            delay["reference_pc_distribution"] = dict(delay["reference_pc_distribution"])
            delay["candidate_pc_distribution"] = dict(delay["candidate_pc_distribution"])
    return {
        "source_id": ref_source,
        "reference_sha256": ref_meta.get("sha256"),
        "candidate_sha256": cand_meta.get("sha256"),
        "groups": list(groups.values()),
        "matched_launch_status0": sum(g["matched_launch_status0"] for g in groups.values()),
        "metric_summary": {
            metric: {
                "records": sum(g["matched_launch_status0"] for g in groups.values()),
                "mismatches": sum(g["mismatches"].get(metric, 0) for g in groups.values()),
            }
            for metric in METRICS
        },
        "excluded": dict(exclusions),
        "mismatch_records": len(failures),
        "failures": failures,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidates", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    reference = load_capture(args.reference)
    reports = []
    for path in args.candidates:
        candidate = load_capture(path)
        report = compare({"metadata": reference[0], "records": reference[1]},
                         {"metadata": candidate[0], "records": candidate[1]})
        report["candidate"] = str(path)
        reports.append(report)
    result = {"reference": str(args.reference), "comparisons": reports}
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"comparisons": len(reports),
                      "mismatch_records": [r["mismatch_records"] for r in reports]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

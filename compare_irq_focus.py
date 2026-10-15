#!/usr/bin/env python3
"""Compare focused kind43 IRQ observations at matching kernel-entry beams."""
import argparse
from collections import Counter
import json
from pathlib import Path

DESCRIPTOR_FIELDS = ("kind", "target", "variant", "phase", "delay", "repeat")
def load_capture(path):
    document = json.loads(Path(path).read_text())
    if not isinstance(document, dict) or not isinstance(document.get("metadata"), dict):
        raise ValueError(f"{path}: expected results.json with metadata and records")
    if not isinstance(document.get("records"), list):
        raise ValueError(f"{path}: missing records list")
    return document


def _descriptor(row):
    try:
        return tuple(row[field] for field in DESCRIPTOR_FIELDS)
    except KeyError as exc:
        raise ValueError(f"Capture row is missing descriptor field {exc.args[0]}") from exc


def _required(row, fields):
    missing = [field for field in fields if field not in row]
    if missing:
        raise ValueError("Capture row is missing fields: " + ", ".join(missing))


def _values(row, target, include_final_result):
    if target == 0:
        _required(row, ("counter", "launch_ref", "second_counter_or_beam"))
        return {
            "masked_intreq_bit": row["counter"] & 0x0010,
            "launch_ref": row["launch_ref"],
            "second_counter_or_beam": row["second_counter_or_beam"],
        }
    fields = ["saved_pc_offset", "irq_beam", "aux", "second_icr_or_level"]
    if include_final_result:
        fields += ["counter", "icr"]
    _required(row, fields)
    values = {
        "saved_pc_offset": row["saved_pc_offset"],
        "irq_beam": row["irq_beam"],
        "aux": row["aux"],
        "final_marker": row["second_icr_or_level"],
    }
    if include_final_result:
        values["final_result"] = (row["counter"] << 16) | row["icr"]
    return values


def _add_metrics(counter, metrics):
    for metric in metrics:
        counter.setdefault(metric, {"records": 0, "mismatches": 0})
        counter[metric]["records"] += 1


def compare(reference, candidate, include_final_result=False):
    """Compare decoded results.json documents and report per-target failures."""
    if not isinstance(reference, dict) or not isinstance(candidate, dict):
        raise ValueError("Expected decoded capture documents")
    ref_meta, ref_rows = reference.get("metadata"), reference.get("records")
    cand_meta, cand_rows = candidate.get("metadata"), candidate.get("records")
    if not isinstance(ref_meta, dict) or not isinstance(cand_meta, dict) \
            or not isinstance(ref_rows, list) or not isinstance(cand_rows, list):
        raise ValueError("Expected captures with metadata and records")
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
    metric_summary = {}
    kind43_count = 0
    for index, (ref, cand) in enumerate(zip(ref_rows, cand_rows)):
        ref_desc, cand_desc = _descriptor(ref), _descriptor(cand)
        if ref_desc != cand_desc:
            raise ValueError(f"Descriptor mismatch at record {index}: {ref_desc} != {cand_desc}")
        kind, target, variant, phase, delay, repeat = ref_desc
        if kind != 43:
            continue
        kind43_count += 1
        if target not in range(11):
            raise ValueError(f"Unsupported kind43 target {target} at record {index}")
        group = groups.setdefault(target, {
            "target": target, "records": 0, "matched_launch_status0": 0,
            "launch_beam_mismatches": 0, "unsuccessful": 0,
            "metrics": {}, "mismatch_records": 0, "failures": [],
            "excluded": Counter(),
        })
        group["records"] += 1
        _required(ref, ("launch_beam", "status"))
        _required(cand, ("launch_beam", "status"))
        if ref["launch_beam"] != cand["launch_beam"]:
            group["launch_beam_mismatches"] += 1
            group["excluded"]["launch_beam_mismatch"] += 1
            exclusions["launch_beam_mismatch"] += 1
            continue
        if ref["status"] != 0 or cand["status"] != 0:
            group["unsuccessful"] += 1
            group["excluded"]["nonzero_status"] += 1
            exclusions["nonzero_status"] += 1
            continue

        ref_values = _values(ref, target, include_final_result)
        cand_values = _values(cand, target, include_final_result)
        metrics = tuple(ref_values)
        group["matched_launch_status0"] += 1
        _add_metrics(group["metrics"], metrics)
        _add_metrics(metric_summary, metrics)
        differences = {metric: [ref_values[metric], cand_values[metric]]
                       for metric in metrics if ref_values[metric] != cand_values[metric]}
        for metric in differences:
            group["metrics"][metric]["mismatches"] += 1
            metric_summary[metric]["mismatches"] += 1
        if differences:
            failure = {
                "record": index, "target": target, "variant": variant,
                "phase": phase, "delay": delay, "repeat": repeat,
                "launch_beam": ref["launch_beam"], "differences": differences,
            }
            group["mismatch_records"] += 1
            group["failures"].append(failure)
            failures.append(failure)

    if kind43_count == 0:
        raise ValueError("No kind43 IRQ focus records in capture")
    for group in groups.values():
        group["excluded"] = dict(group["excluded"])
    return {
        "source_id": ref_source,
        "reference_sha256": ref_meta.get("sha256"),
        "candidate_sha256": cand_meta.get("sha256"),
        "kind43_records": kind43_count,
        "groups": list(groups.values()),
        "matched_launch_status0": sum(g["matched_launch_status0"] for g in groups.values()),
        "metric_summary": metric_summary,
        "excluded": dict(exclusions),
        "mismatch_records": len(failures),
        "failures": failures,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidates", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--compare-final-result", action="store_true",
                        help="also compare counter<<16|icr for ordinary CPU targets")
    args = parser.parse_args(argv)
    reference = load_capture(args.reference)
    reports = []
    for path in args.candidates:
        report = compare(reference, load_capture(path), args.compare_final_result)
        report["candidate"] = str(path)
        reports.append(report)
    result = {"reference": str(args.reference), "comparisons": reports}
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"comparisons": len(reports),
                      "mismatch_records": [report["mismatch_records"] for report in reports]},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

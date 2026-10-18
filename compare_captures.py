#!/usr/bin/env python3
"""Summarize RBCP hardware/emulator observations without phase alignment."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import rom_results

DESCRIPTOR = tuple(rom_results.FIELDS[:6])
OBSERVATIONS = tuple(k for k in rom_results.FIELDS[6:] if k not in ("pc_hi", "pc_lo")) + ("saved_pc_offset",)
UNITS = {k: "raw unsigned 16-bit observation; kind-dependent" for k in OBSERVATIONS}
UNITS.update({k: "packed VHPOSR register word, not elapsed cycles" for k in ("launch_beam", "end_beam", "irq_beam")})
UNITS.update(saved_pc_offset="unsigned byte offset", status="status code", irq_level="interrupt level", aux="kind-dependent event count/observation")


def case_id(row):
    return ":".join(str(row[k]) for k in DESCRIPTOR)


def resolve(path):
    path = Path(path)
    if path.is_dir():
        for name in ("results.json", "capture/results.json", "results.bin", "capture/results.bin"):
            if (path / name).exists():
                return path / name
        raise ValueError(f"{path}: no RBCP results")
    return path


def load_capture(path):
    path = resolve(path)
    raw = path.read_bytes()
    if path.suffix == ".bin":
        meta, rows = rom_results.decode(raw)
        doc = {"metadata": meta, "records": rows}
        integrity = "RBCP checksum verified"
    else:
        doc = json.loads(raw)
        if not isinstance(doc, dict) or not isinstance(doc.get("metadata"), dict):
            raise ValueError(f"{path}: expected metadata object and records list")
        binary = path.with_suffix(".bin")
        integrity = "JSON only; binary checksum unavailable"
        if binary.exists():
            meta, rows = rom_results.decode(binary.read_bytes())
            if doc.get("metadata") != meta or doc.get("records") != rows:
                raise ValueError(f"{path}: JSON differs from checksum-verified results.bin")
            integrity = "RBCP checksum and decoded JSON verified"
    if not isinstance(doc, dict) or not isinstance(doc.get("metadata"), dict):
        raise ValueError(f"{path}: expected metadata object and records list")
    meta, rows = doc["metadata"], doc["records"]
    if type(meta.get("record_count")) is not int or meta["record_count"] <= 0:
        raise ValueError(f"{path}: record_count must be a positive integer")
    source = meta.get("source_id")
    if not isinstance(source, str) or len(source) != 64 or any(c not in "0123456789abcdefABCDEF" for c in source):
        raise ValueError(f"{path}: invalid source_id")
    if not isinstance(rows, list):
        raise ValueError(f"{path}: records must be a list")
    if not rows:
        raise ValueError(f"{path}: no observations; declared matrix is missing")
    index, invalid = {}, {}
    for number, row in enumerate(rows):
        try:
            if any(type(row[k]) is not int or not 0 <= row[k] <= 65535 for k in DESCRIPTOR):
                raise ValueError("invalid descriptor")
            key = case_id(row)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{path}: row {number}: invalid descriptor") from exc
        if key in index:
            invalid[key] = "duplicate descriptor"
        index[key] = row
        for field in OBSERVATIONS:
            maximum = 0xffffffff if field == "saved_pc_offset" else 65535
            if type(row.get(field)) is not int or not 0 <= row[field] <= maximum:
                invalid[key] = f"missing/out-of-range {field}"
        if row.get("status") != 0:
            invalid[key] = f"unsuccessful status {row.get('status')}"
    trace_path = path.parent / "events.json"
    traces = json.loads(trace_path.read_text()) if trace_path.exists() else None
    if traces is not None:
        if not isinstance(traces, dict) or not isinstance(traces.get("unit"), str) or not traces["unit"].strip() or not isinstance(traces.get("cases"), dict):
            raise ValueError(f"{trace_path}: expected unit and cases mapping")
        for events in traces["cases"].values():
            if not isinstance(events, list) or any(not isinstance(e, dict) or type(e.get("time")) is not int or not isinstance(e.get("event"), str) for e in events):
                raise ValueError(f"{trace_path}: events require integer time and string event")
            if any(a["time"] > b["time"] for a, b in zip(events, events[1:])):
                raise ValueError(f"{trace_path}: event times must be ordered")
    return {"path": str(path.resolve()), "file_sha256": hashlib.sha256(raw).hexdigest(),
            "metadata": meta, "integrity": integrity, "records": index, "invalid": invalid,
            "declared_count_delta": meta.get("record_count", 0) - len(rows),
            "trace_path": str(trace_path.resolve()) if traces else None, "traces": traces}


def trace_detail(left, right, key, window):
    a, b = left["traces"], right["traces"]
    if a is None or b is None or key not in a["cases"] or key not in b["cases"]:
        return {"available": False, "reason": "no paired event trace for this case"}
    if a["unit"] != b["unit"]:
        return {"available": False, "reason": "trace units differ"}
    x, y = a["cases"][key], b["cases"][key]
    first = next((i for i in range(max(len(x), len(y))) if i >= len(x) or i >= len(y) or x[i] != y[i]), None)
    start = max(0, (first or 0) - window)
    end = (first or 0) + window + 1
    return {"available": True, "unit": a["unit"], "alignment": "none; exact sequence index and absolute timestamps",
            "first_divergence_index": first, "start_index": start,
            "hardware": x[start:end], "candidate": y[start:end]}


def compare(left, right, selected=None, window=3):
    if left["metadata"]["source_id"] != right["metadata"]["source_id"]:
        raise ValueError("source_id mismatch; compare the identical probe build")
    counts = Counter({k: 0 for k in ("total", "match", "mismatch", "missing", "invalid")})
    patterns = defaultdict(list)
    details = {}
    first = None
    eligibility = Counter(exact_launch=0, different_launch=0, exact_launch_matches=0, exact_launch_mismatches=0)
    keys = sorted(left["records"].keys() | right["records"].keys(), key=lambda s: tuple(map(int, s.split(":"))))
    for key in keys:
        a, b = left["records"].get(key), right["records"].get(key)
        changes = []
        reason = None
        if key in left["invalid"] or key in right["invalid"]:
            status = "invalid"
            reason = {"hardware": left["invalid"].get(key), "candidate": right["invalid"].get(key)}
        elif a is None or b is None:
            status = "missing"
            reason = "hardware" if a is None else "candidate"
        else:
            changes = [k for k in OBSERVATIONS if a[k] != b[k]]
            if a["kind"] == 51:
                eligibility["exact_launch" if all(a[k] == b[k] for k in ("launch_beam", "launch_ref")) else "different_launch"] += 1
            trace = trace_detail(left, right, key, 0)
            if trace["available"] and trace["first_divergence_index"] is not None:
                changes.append("event_trace")
            status = "mismatch" if changes else "match"
            if a["kind"] == 51 and all(a[k] == b[k] for k in ("launch_beam", "launch_ref")):
                eligibility["exact_launch_matches" if status == "match" else "exact_launch_mismatches"] += 1
        counts["total"] += 1
        counts[status] += 1
        if status != "match":
            if first is None:
                first = {"case": key, "status": status, "first_different_field": changes[0] if changes else None,
                         "trace": trace_detail(left, right, key, window)}
            deltas = tuple((field, b[field] - a[field]) for field in changes if field != "event_trace")
            pattern = (status, tuple(changes), tuple(key.split(":")[:3]), deltas)
            patterns[pattern].append(key)
        if selected == key:
            details = {"case": key, "status": status, "reason": reason, "hardware": a, "candidate": b,
                       "differences": {k: {"hardware": a[k], "candidate": b[k], "candidate_minus_hardware": b[k] - a[k], "unit": UNITS[k]} for k in changes if k != "event_trace"},
                       "trace": trace_detail(left, right, key, window)}
    if selected is not None and not details:
        raise ValueError(f"case {selected} absent from both captures")
    groups = [{"status": status, "fields": list(fields), "candidate_minus_hardware": dict(deltas), "shared_conditions": dict(zip(DESCRIPTOR[:3], map(int, condition))),
               "count": len(ids), "representative_cases": ids[:3]}
              for (status, fields, condition, deltas), ids in sorted(patterns.items(), key=lambda item: (-len(item[1]), item[0]))]
    return {"counts": dict(counts), "kind51_launch_eligibility": dict(eligibility),
            "trace_diagnostic": "paired traces available" if left["traces"] and right["traces"] and left["traces"]["unit"] == right["traces"]["unit"] else "trace unavailable or trace units differ",
            "timing_interpretation": "Different-launch rows are raw observation mismatches, not comparable timing evidence. Matching launch samples do not establish identical E-clock history.",
            "first_divergence": first, "patterns": groups,
            "kind51_exact_launch_patterns": [group for group in groups if group["status"] == "mismatch" and group["shared_conditions"]["kind"] == 51 and not {"launch_beam", "launch_ref"}.intersection(group["fields"])],
            "detail": details or None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hardware", required=True, type=Path)
    parser.add_argument("--copperline", required=True, type=Path)
    parser.add_argument("--winuae", type=Path)
    parser.add_argument("--case", help="kind:target:variant:phase:delay:repeat")
    parser.add_argument("--window", type=int, default=3, help="events before/after first trace divergence")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.window < 0:
        parser.error("--window must be nonnegative")
    try:
        paths = {"hardware": args.hardware, "copperline": args.copperline}
        if args.winuae:
            paths["winuae"] = args.winuae
        protected = set()
        for path in paths.values():
            try:
                resolved = resolve(path).resolve()
            except (ValueError, OSError):
                resolved = path.resolve()
            protected.update((resolved, resolved.with_suffix(".bin"), resolved.with_suffix(".json"), resolved.parent / "events.json"))
        if args.out.resolve() in protected:
            parser.exit(2, "output must not overwrite an input, paired binary/JSON, or event trace\n")
        captures, errors = {}, {}
        for name, path in paths.items():
            try:
                captures[name] = load_capture(path)
            except (ValueError, KeyError, TypeError, OSError) as exc:
                errors[name] = {"path": str(path.resolve()), "error": str(exc)}
        if "hardware" in captures:
            for name, capture in captures.items():
                if capture["metadata"]["source_id"] != captures["hardware"]["metadata"]["source_id"]:
                    errors[name] = {"path": capture["path"], "error": "source_id mismatch with hardware"}
        if errors:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps({"schema_version": 1, "invalid_capture_count": len(errors), "invalid_captures": errors, "comparisons": {}}, indent=2) + "\n")
            print(f"invalid_captures={len(errors)} report: {args.out}")
            return 2
        report = {"schema_version": 1, "invalid_capture_count": 0, "policy": "Exact six-word descriptor; all raw observation fields compared. No alignment, resampling, wrap correction, phase exclusion or launch filtering. Launch mismatches are mismatches, not timing-equivalent cohorts.",
                  "units": UNITS, "first_divergence_order": "numeric descriptor, then observation wire order; not chronological execution",
                  "limitations": "Software observations constrain combined behavior; matching samples do not prove identical CIA E-clock history. Raw VHPOSR subtraction is not elapsed time. Trace divergence is available only with paired events.json.",
                  "captures": {name: {k: v for k, v in capture.items() if k not in ("records", "invalid", "traces")} for name, capture in captures.items()},
                  "comparisons": {name: compare(captures["hardware"], capture, args.case, args.window) for name, capture in captures.items() if name != "hardware"}}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        incomplete = {name: capture["declared_count_delta"] for name, capture in captures.items() if capture["declared_count_delta"]}
        if incomplete:
            print("incomplete declarations (declared minus observed rows): " + json.dumps(incomplete, sort_keys=True))
        for name, result in report["comparisons"].items():
            print(name + ": " + " ".join(f"{key}={value}" for key, value in result["counts"].items()))
            if args.case:
                print(json.dumps(result["detail"], indent=2))
                continue
            print("  kind51 launch eligibility: " + json.dumps(result["kind51_launch_eligibility"], sort_keys=True))
            for pattern in result["patterns"][:3]:
                print("  pattern: " + json.dumps(pattern, sort_keys=True))
            for pattern in result["kind51_exact_launch_patterns"][:3]:
                print("  exact-launch pattern: " + json.dumps(pattern, sort_keys=True))
            if result["first_divergence"]:
                eligible = result["kind51_exact_launch_patterns"]
                detail_case = eligible[0]["representative_cases"][0] if eligible else result["first_divergence"]["case"]
                print("  detail: repeat command with --case " + detail_case + " --window 3")
        print(f"report: {args.out}")
        return 1 if incomplete or any(r["counts"]["mismatch"] or r["counts"]["missing"] or r["counts"]["invalid"] for r in report["comparisons"].values()) else 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f"invalid capture: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())

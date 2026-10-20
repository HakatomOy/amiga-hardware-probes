#!/usr/bin/env python3
"""Typed, exact-launch comparison for archived kind51 emulator captures."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

TARGETS = {
    0: ("NOP", "ROM"), 1: ("MOVE.B D0,-(A1)", "ROM"),
    2: ("NOP", "CHIP RAM"), 3: ("MOVE.B D0,-(A1)", "CHIP RAM"),
}
SOURCES = {0: ("CIA-A Timer A / PORTS", 2), 1: ("Copper COPER", 3),
           2: ("CIA-B Timer A / EXTER", 6)}
FIELDS = {"irq_beam": "irq_beam", "counter": "d1_at_irq", "icr": "a1_low_at_irq",
          "saved_pc_offset": "saved_pc_offset", "end_ref": "cia_icr_at_irq"}


def beam_linear(value):
    """Map packed VHPOSR vpos:hpos to 227*V + H, preserving the original value elsewhere."""
    return 227 * ((value >> 8) & 0xff) + (value & 0xff)


def load(path):
    doc = json.loads(path.read_text())
    meta, records = doc["metadata"], doc["records"]
    if meta["record_count"] != 1536:
        raise ValueError(f"{path}: unexpected kind51 source/count")
    if len(records) != 1536 or meta["timeouts"] or meta["skipped"]:
        raise ValueError(f"{path}: incomplete capture")
    seen = set()
    for r in records:
        key = tuple(r[k] for k in ("kind", "target", "variant", "phase", "delay", "repeat"))
        if key in seen or r["kind"] != 51 or r["status"] != 0 or r["aux"] != 1:
            raise ValueError(f"{path}: duplicate descriptor or invalid event/status: {key}")
        seen.add(key)
        source, expected_level = SOURCES[r["variant"]]
        if r["irq_level"] != expected_level or r["second_counter_or_beam"] != 0xffff:
            raise ValueError(f"{path}: unexpected IRQ level or final loop counter: {key}")
        if r["second_icr_or_level"] != (0x8100 if TARGETS[r["target"]][0] == "NOP" else 0x8080):
            raise ValueError(f"{path}: final A1 does not match loop operation: {key}")
        if r["variant"] in (0, 2) and (r["end_ref"] & 0x81) != 0x81:
            raise ValueError(f"{path}: CIA ICR lacks FLAG/IRQ bits: {key}")
        if r["variant"] == 1 and r["end_ref"] != 0:
            raise ValueError(f"{path}: COPER row has unexpected CIA ICR: {key}")
    if len(seen) != 1536:
        raise ValueError(f"{path}: descriptor matrix is not complete")
    return meta, {tuple(r[k] for k in ("kind", "target", "variant", "phase", "delay", "repeat")): r
                  for r in records}


def compare(ref, other):
    cohorts = defaultdict(list)
    matched = 0
    for desc, a in ref.items():
        b = other.get(desc)
        if (b is None or a["launch_ref"] != b["launch_ref"]
                or a["launch_beam"] != b["launch_beam"]):
            continue
        matched += 1
        _, target, source, phase, delay, repeat = desc
        key = (source, target, phase)
        cohorts[key].append({"descriptor": list(desc), "launch_ref": a["launch_ref"],
                             "reference": {label: a[field] for field, label in FIELDS.items()},
                             "comparison": {label: b[field] for field, label in FIELDS.items()},
                             "mismatches": [label for field, label in FIELDS.items() if a[field] != b[field]]})
    groups = []
    for (source, target, phase), rows in sorted(cohorts.items()):
        raw_beam_delta = Counter((x["comparison"]["irq_beam"] - x["reference"]["irq_beam"]) for x in rows)
        linear_beam_delta = Counter((beam_linear(x["comparison"]["irq_beam"])
                                     - beam_linear(x["reference"]["irq_beam"])) for x in rows)
        groups.append({"source": SOURCES[source][0], "operation": TARGETS[target][0],
                       "storage": TARGETS[target][1], "phase": phase,
                       "exact_launch_matches": len(rows),
                       "irq_beam_raw_delta_counts": dict(sorted(raw_beam_delta.items())),
                       "irq_beam_linear_delta_227v_plus_h_counts": dict(sorted(linear_beam_delta.items())),
                       "mismatch_counts": {label: sum(x["reference"][label] != x["comparison"][label] for x in rows)
                                           for label in FIELDS.values()},
                       "rows": rows})
    return {"exact_launch_match_count": matched, "groups": groups}


def cross_phase_matches(rows):
    """Pairs within one capture with same target/source/offset and both beam samples equal."""
    buckets = defaultdict(list)
    for desc, row in rows.items():
        _, target, source, phase, event_offset, repeat = desc
        buckets[(target, source, event_offset, row["launch_beam"], row["launch_ref"])].append((desc, row))
    result = []
    for (target, source, offset, post, pre), members in sorted(buckets.items()):
        for i, (left_desc, left) in enumerate(members):
            for right_desc, right in members[i + 1:]:
                if left_desc[3] == right_desc[3] and left_desc[5] == right_desc[5]:
                    continue
                result.append({"target": target, "source": source, "event_offset": offset,
                               "left_descriptor": list(left_desc), "right_descriptor": list(right_desc),
                               "post_start_vhposr": post, "pre_start_vhposr": pre,
                               "irq_beam_raw_delta_right_minus_left": right["irq_beam"] - left["irq_beam"],
                             "irq_beam_linear_delta_right_minus_left": beam_linear(right["irq_beam"]) - beam_linear(left["irq_beam"]),
                               "d1_at_irq_delta_right_minus_left": right["counter"] - left["counter"]})
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--winuae", type=Path, required=True)
    p.add_argument("--current", type=Path)
    p.add_argument("--before", type=Path)
    p.add_argument("--parent", type=Path)
    p.add_argument("--fixed", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    capture_paths = [("winuae", a.winuae)]
    capture_paths += [("copperline_current", a.current)] if a.current else []
    capture_paths += [("copperline_before", a.before)] if a.before else []
    capture_paths += [("copperline_parent", a.parent)] if a.parent else []
    capture_paths += [("copperline_fixed", a.fixed)] if a.fixed else []
    if len(capture_paths) < 3:
        p.error("supply WinUAE and at least two Copperline captures")
    captures = {name: load(path) for name, path in capture_paths}
    if len({meta["source_id"] for meta, _ in captures.values()}) != 1:
        raise ValueError("captures have different source IDs")
    for name, (meta, rows) in captures.items():
        if set(rows) != set(captures["winuae"][1]):
            raise ValueError(f"{name}: descriptor matrix differs")
    reference = captures["winuae"][1]
    report = {
        "scope": "kind51 emulator-capture comparison; not a hardware result",
        "primary_rule": "Compare only identical descriptors whose captured +12 post-start VHPOSR (launch_beam) and +14 pre-start VHPOSR (launch_ref) are both exactly equal. No phase-adjusted or near-beam matching is treated as equivalent.",
        "record_fields": {"VHPOSR conversion": "linear beam coordinate = 227 * (value >> 8) + (value & 0xff); raw encoded word is retained in every row",
                          "+12": "launch_beam: VHPOSR immediately after CIA CRA start or Copper COPJMP1",
                          "+14": "launch_ref: VHPOSR immediately before source start",
                          "+16": "end_beam: loop-end VHPOSR", "+18": "end_ref: selected CIA ICR at IRQ (zero for COPER rows)",
                          "+20": "counter: D1 at IRQ", "+22": "icr: A1 low word at IRQ", "+24": "irq_beam: first IRQ VHPOSR",
                          "+26": "irq_level", "+28": "saved_pc_offset normalized to loop entry", "+32": "status",
                          "+34": "event count", "+36": "final D1", "+38": "final A1 low word"},
        "captures": {name: {"source_id": meta["source_id"], "results_sha256": meta["sha256"],
                            "record_count": meta["record_count"], "timeouts": meta["timeouts"],
                            "skipped": meta["skipped"], "agnus_vposr": meta["agnus_vposr"]}
                     for name, (meta, _) in captures.items()},
        "invariants": {"all_rows_status_zero_and_one_irq": True,
                       "expected_irq_levels": {"CIA-A PORTS": 2, "COPER": 3, "CIA-B EXTER": 6},
                       "source_row_counts": {name: {SOURCES[s][0]: sum(r["variant"] == s for r in rows.values())
                                                     for s in SOURCES}
                                             for name, (_, rows) in captures.items()},
                       "cia_a_icr_values": {name: dict(Counter(r["end_ref"] for r in rows.values() if r["variant"] == 0))
                                            for name, (_, rows) in captures.items()},
                       "coper_icr_values": {name: sorted(set(r["end_ref"] for r in rows.values() if r["variant"] == 1))
                                            for name, (_, rows) in captures.items()},
                       "cia_b_icr_values": {name: dict(Counter(r["end_ref"] for r in rows.values() if r["variant"] == 2))
                                            for name, (_, rows) in captures.items()}},
        "comparisons_to_winuae": {name: compare(reference, rows)
                                  for name, (_, rows) in captures.items() if name != "winuae"},
        "cross_phase_pairs_within_capture": {name: cross_phase_matches(rows)
                                               for name, (_, rows) in captures.items()},
        "interpretation_limit": "Equality of both captured VHPOSR samples is a stricter observed-phase match, not proof of identical internal CIA E-clock history or hardware behavior. Cross-phase pairs are exploratory. IRQ deltas include both raw encoded VHPOSR and 227*V+H coordinates, but samples near a vertical/horizontal boundary can reflect register-read pipeline or wrap behavior; neither coordinate is treated as a direct event-latency measurement.",
        "hardware_captured_today": False,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {a.out}; exact matches: " + ", ".join(
        f"{k}={v['exact_launch_match_count']}" for k, v in report["comparisons_to_winuae"].items()))


if __name__ == "__main__":
    main()

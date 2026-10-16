#!/usr/bin/env python3
"""Decode sampled A500 CPU custom-bus cycles from an RG03 LA capture."""
from __future__ import annotations

import argparse
import json
import math
import statistics
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from rg03_capture import parse_capture  # noqa: E402

# RG03 packed sample bit -> signal. D13/D14 below are data lines; A7/A8 are
# separate LA inputs whose captured channel indexes happen to be 13/14.
AS_N, RW, UDS_N, DTACK_N = 1, 2, 3, 4
D14, D13, REGEN_N = 5, 8, 15
ADDRESS_BITS = {1: 6, 2: 7, 3: 9, 4: 10, 5: 11, 6: 12, 7: 13, 8: 14}


def rising_edges(words: tuple[int, ...] | list[int], bit: int) -> list[int]:
    mask = 1 << bit
    return [i for i in range(1, len(words)) if not words[i - 1] & mask and words[i] & mask]


def infer_cpu_period(words: tuple[int, ...] | list[int], *, max_jitter_fraction: float = 0.05) -> dict:
    """Infer D0 rising-to-rising spacing in samples and reject irregular clocks."""
    if not math.isfinite(max_jitter_fraction) or max_jitter_fraction < 0:
        raise ValueError("max_jitter_fraction must be finite and nonnegative")
    edges = rising_edges(words, 0)
    periods = [b - a for a, b in zip(edges, edges[1:])]
    if len(periods) < 2:
        raise ValueError(f"need at least three D0 rising edges to check CPU-clock jitter; found {len(edges)}")
    median = statistics.median(periods)
    mean = statistics.fmean(periods)
    if median <= 0 or mean <= 0:
        raise ValueError("D0 rising-edge period must be positive")
    deviations = [abs(p - median) / median for p in periods]
    worst = max(deviations)
    if worst > max_jitter_fraction:
        raise ValueError(
            f"D0 period jitter {worst:.6g} exceeds limit {max_jitter_fraction:.6g} "
            f"(period samples {periods})"
        )
    return {"rising_edges": len(edges), "period_count": len(periods),
            "period_samples": mean, "period_samples_mean": mean,
            "period_samples_median": median, "period_samples_stdev": statistics.pstdev(periods),
            "period_samples_min": min(periods),
            "period_samples_max": max(periods), "max_relative_deviation": worst,
            "max_jitter_fraction": max_jitter_fraction}


def address_low9(word: int) -> int:
    address = sum(((word >> channel) & 1) << bit for bit, channel in ADDRESS_BITS.items())
    # A0 is not wired in this capture. UDS selects the high byte and implies
    # an even byte address for the word register value reported here.
    return address


def _bit_window(words: list[int] | tuple[int, ...], start: int, end: int,
                channel: int, first_clock_sample: int, period_samples: float) -> dict:
    levels = [(word >> channel) & 1 for word in words[start:end + 1]]
    transitions = [{"sample_offset": offset, "cpu_cycle_offset": (start + offset - first_clock_sample) / period_samples,
                    "from": levels[offset - 1], "to": levels[offset]}
                   for offset in range(1, len(levels)) if levels[offset] != levels[offset - 1]]
    stable = not transitions
    return {"level": levels[0] if stable else None,
            "first_level": levels[0], "last_level": levels[-1],
            "stable": stable, "transitions": transitions}


def decode_words(words: tuple[int, ...] | list[int], *, sample_interval_s: float | None = None,
                 nominal_cpu_reference_hz: float | None = None,
                 max_jitter_fraction: float = 0.05, min_window_samples: int = 2) -> dict:
    if (sample_interval_s is None) == (nominal_cpu_reference_hz is None):
        raise ValueError("supply exactly one of sample_interval_s or nominal_cpu_reference_hz")
    if sample_interval_s is not None and (not math.isfinite(sample_interval_s) or sample_interval_s <= 0):
        raise ValueError("sample_interval_s must be finite and positive")
    if nominal_cpu_reference_hz is not None and (
        not math.isfinite(nominal_cpu_reference_hz) or nominal_cpu_reference_hz <= 0
    ):
        raise ValueError("nominal_cpu_reference_hz must be finite and positive")
    if min_window_samples < 2:
        raise ValueError("min_window_samples must be at least 2")
    clock = infer_cpu_period(words, max_jitter_fraction=max_jitter_fraction)
    first_clock_sample = rising_edges(words, 0)[0]
    if sample_interval_s is not None:
        interval = sample_interval_s
        scale_source = "caller sample interval; relative D0 period is independently measured in samples"
    else:
        interval = 1.0 / (clock["period_samples"] * nominal_cpu_reference_hz)
        scale_source = ("estimated from caller-supplied nominal CPU reference; not an independent "
                        "absolute timebase calibration")
    clock.update({"sample_interval_s": interval,
                  "period_s": clock["period_samples"] * interval,
                  "estimated_cpu_hz": 1.0 / (clock["period_samples"] * interval),
                  "scale_source": scale_source})

    # A custom bus window is valid only while the address strobe, Gary custom
    # register select, upper data strobe, and DTACK are simultaneously active.
    # Keeping D0/RW out of the qualifier avoids mistaking a CPU edge for a bus
    # edge; RW and address must remain stable across the complete window.
    selected = []
    for i, word in enumerate(words):
        valid = not (word >> AS_N & 1) and not (word >> REGEN_N & 1) and not (word >> UDS_N & 1) and not (word >> DTACK_N & 1)
        selected.append(valid)
    windows = []
    i = 0
    while i < len(selected):
        if not selected[i]:
            i += 1
            continue
        start = i
        while i + 1 < len(selected) and selected[i + 1]:
            i += 1
        end = i
        i += 1
        if end - start + 1 < min_window_samples:
            continue
        address_samples = {address_low9(words[j]) for j in range(start, end + 1)}
        rw_samples = {(words[j] >> RW) & 1 for j in range(start, end + 1)}
        address_stable = len(address_samples) == 1
        rw_stable = len(rw_samples) == 1
        address = next(iter(address_samples)) if address_stable else None
        is_read = next(iter(rw_samples)) == 1 if rw_stable else None
        item = {"start_sample": start, "end_sample": end,
                "sample_count": end - start + 1,
                "start_cpu_cycle": (start - first_clock_sample) / clock["period_samples"],
                "end_cpu_cycle": (end - first_clock_sample) / clock["period_samples"],
                "address_low9": address,
                "address_stable": address_stable,
                "read": is_read,
                "rw_stable": rw_stable,
                "custom_select_qualified": True}
        if address_stable and rw_stable and address == 0x002 and is_read:
            item["register"] = "DMACONR"
            item["data_bits"] = {
                "BBUSY_D14": _bit_window(words, start, end, D14, first_clock_sample,
                                          clock["period_samples"]),
                "BZERO_D13": _bit_window(words, start, end, D13, first_clock_sample,
                                         clock["period_samples"]),
            }
        windows.append(item)

    return {"sample_count": len(words), "cpu_clock": clock,
            "address_scope": "low 9 bits only; full custom address is unavailable without A0 and upper address probes",
            "signal_map": {"AS_N": AS_N, "RW": RW, "UDS_N": UDS_N, "DTACK_N": DTACK_N,
                           "D14": D14, "D13": D13, "REGEN_N": REGEN_N,
                           **{f"A{bit}": channel for bit, channel in ADDRESS_BITS.items()}},
            "qualification": "AS_N=0, Gary REGEN_N=0, UDS_N=0, DTACK_N=0; RW/address stable across window",
            "custom_windows": windows}


def analyze(path: Path, *, sample_interval_s: float | None,
            nominal_cpu_reference_hz: float | None, max_jitter_fraction: float) -> dict:
    parsed = parse_capture(path)
    la = parsed["la"]
    if len(la["payload"]) != la["points"] * 4:
        raise ValueError(f"LA payload is {len(la['payload'])} bytes for {la['points']} uint32 samples")
    words = struct.unpack(f"<{la['points']}I", la["payload"])
    decoded = decode_words(words, sample_interval_s=sample_interval_s,
                           nominal_cpu_reference_hz=nominal_cpu_reference_hz,
                           max_jitter_fraction=max_jitter_fraction)
    decoded.update({"file": str(path), "format": "RG03 LA uint32", "la_label": la["label"],
                    "la_points": la["points"], "la_x_increment_header_untrusted_s": la["x_increment_header_s"],
                    "la_x_origin_s": la["x_origin_s"],
                    "la_payload_bytes": la["actual_payload_bytes"],
                    "la_declared_payload_bytes": la["declared_payload_bytes"],
                    "la_declared_minus_actual_payload_bytes": la["declared_payload_bytes"] - la["actual_payload_bytes"],
                    "analog_record_count": len(parsed["analogs"]),
                    "declared_file_bytes": parsed["declared_file_bytes"],
                    "actual_file_bytes": parsed["actual_file_bytes"],
                    "header_sample_info": {"wave_count": parsed["wave_count"],
                                           "wave_header_bytes": la["wave_header_bytes"],
                                           "data_header_bytes": la["data_header_bytes"],
                                           "buffer_count": la["buffer_count"],
                                           "data_format": la["format"],
                                           "bytes_per_point": la["bytes_per_point_header"],
                                           "x_increment_header_untrusted_s": la["x_increment_header_s"],
                                           "x_origin_s": la["x_origin_s"],
                                           "payload_offset": la["payload_offset"]},
                    "words_uint32": list(words)})
    return decoded


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("captures", nargs="+", type=Path, help="RG03 capture binaries")
    scale = ap.add_mutually_exclusive_group(required=True)
    scale.add_argument("--sample-interval-s", type=float,
                       help="explicit LA sample interval in seconds")
    scale.add_argument("--nominal-cpu-reference-hz", type=float,
                       help="nominal D0 CPU reference frequency; absolute timing remains estimated")
    ap.add_argument("--max-jitter-fraction", type=float, default=0.05)
    ap.add_argument("--output", type=Path, help="write JSON here (default: stdout)")
    args = ap.parse_args()
    results, failures = [], []
    for path in args.captures:
        try:
            results.append(analyze(path, sample_interval_s=args.sample_interval_s,
                                   nominal_cpu_reference_hz=args.nominal_cpu_reference_hz,
                                   max_jitter_fraction=args.max_jitter_fraction))
        except (OSError, ValueError, struct.error) as exc:
            failures.append({"file": str(path), "error": str(exc)})
    report = {"analysis": "A500 digital custom-bus / DMACONR", "captures": results, "failures": failures}
    rendered = json.dumps(report, indent=2, allow_nan=False)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

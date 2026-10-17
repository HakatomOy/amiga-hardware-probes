#!/usr/bin/env python3
"""Compare kind-48 BLTBDAT history captures without hardware access."""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

MAGIC = b"A5RBCP01"
HEADER_BYTES = 64
RECORD_BYTES = 40
FIELD_NAMES = (
    "kind", "target", "variant", "phase", "delay", "repeat",
    "launch_beam", "launch_ref", "end_beam", "end_ref",
    "counter", "icr", "irq_beam", "irq_level", "pc_hi", "pc_lo",
    "status", "aux", "second_counter_or_beam", "second_icr_or_level",
)
BEAM_WORDS = (6, 8, 18, 19)  # byte offsets +12, +16, +36, +38
FIRST_D_WORD = 7             # byte offset +14
SECOND_D_WORD = 9            # byte offset +18
DMACONR_WORDS = tuple(range(10, 18))  # byte offsets +20 through +34
REPEAT_VALUES = set(range(8))


def _row_from_json(record: dict | list) -> tuple[int, ...]:
    if isinstance(record, list):
        if len(record) != 20:
            raise ValueError("JSON capture rows must contain exactly 20 words")
        row = tuple(int(value) for value in record)
    elif isinstance(record, dict):
        if all(name in record for name in FIELD_NAMES):
            row = tuple(int(record[name]) for name in FIELD_NAMES)
        else:
            # rom_results JSON combines the two raw PC words into one field;
            # that field occupies the same two words in the kind-48 record.
            required = [name for index, name in enumerate(FIELD_NAMES)
                        if index not in (14, 15)]
            missing = [name for name in required if name not in record]
            if missing or "saved_pc_offset" not in record:
                raise ValueError(f"JSON result row is missing raw fields: {missing}")
            saved_pc = int(record["saved_pc_offset"])
            values = []
            for index, name in enumerate(FIELD_NAMES):
                if index == 14:
                    values.append((saved_pc >> 16) & 0xFFFF)
                elif index == 15:
                    values.append(saved_pc & 0xFFFF)
                else:
                    values.append(int(record[name]))
            row = tuple(values)
    else:
        raise ValueError("JSON capture record must be an object or 20-word list")
    if any(value < 0 or value > 0xFFFF for value in row):
        raise ValueError("Capture record contains a value outside the 16-bit range")
    return row


def _locate(path: Path) -> tuple[Path, Path | None]:
    path = path.resolve()
    if path.is_file():
        result = path
        roots = (path.parent, path.parent.parent)
    else:
        candidates = (
            path / "results.bin", path / "results.json", path / "capture.json",
            path / "capture" / "results.bin", path / "capture" / "results.json",
            path / "capture" / "capture.json",
        )
        result = next((candidate for candidate in candidates if candidate.is_file()), None)
        if result is None:
            raise FileNotFoundError(f"No results.bin, results.json, or capture.json in {path}")
        roots = (result.parent, result.parent.parent, path)
    manifest = next((root / "build-manifest.json" for root in roots
                     if (root / "build-manifest.json").is_file()), None)
    return result, manifest


def _load_capture(path: Path) -> dict:
    result_path, manifest_path = _locate(path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path else None
    if result_path.suffix.lower() == ".bin":
        data = result_path.read_bytes()
        if len(data) < HEADER_BYTES or data[:8] != MAGIC:
            raise ValueError(f"Invalid result header in {result_path}")
        version, record_size, count, byte_length, checksum = struct.unpack_from(">HHIII", data, 8)
        if version != 1 or record_size != RECORD_BYTES or byte_length != len(data):
            raise ValueError(f"Invalid result layout in {result_path}")
        if byte_length != HEADER_BYTES + count * RECORD_BYTES:
            raise ValueError(f"Record count/length mismatch in {result_path}")
        words = struct.unpack(">" + "I" * (len(data) // 4), data)
        if sum(words) & 0xFFFFFFFF:
            raise ValueError(f"Checksum mismatch in {result_path}")
        source_id = data[24:56].hex()
        rows = [tuple(struct.unpack_from(">20H", data, offset))
                for offset in range(HEADER_BYTES, len(data), RECORD_BYTES)]
        if struct.unpack_from(">H", data, 62)[0] != 1:
            raise ValueError(f"Incomplete result collection in {result_path}")
        validation_level = "raw_checksum_and_completion"
    else:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        metadata = payload.get("metadata", payload)
        rows_value = payload.get("records", payload.get("rows"))
        if rows_value is None:
            raise ValueError(f"No records array in {result_path}")
        source_id = metadata.get("source_id") or (manifest or {}).get("source_id")
        if not source_id:
            raise ValueError(f"No source_id in {result_path}")
        rows = [_row_from_json(record) for record in rows_value]
        validation_level = "json_only"
        expected_count = metadata.get("record_count", metadata.get("trial_count"))
        if expected_count is not None and int(expected_count) != len(rows):
            raise ValueError(f"JSON record count mismatch in {result_path}")
    if manifest:
        if manifest.get("source_id") != source_id:
            raise ValueError(f"Manifest/source_id mismatch in {result_path}")
        trials = manifest.get("trials")
        if int(manifest.get("trial_count", -1)) != len(rows) or not isinstance(trials, list):
            raise ValueError(f"Manifest record count mismatch in {result_path}")
        if len(trials) != len(rows) or any(
            [row[i] for i in range(6)] != [int(value) for value in trial]
            for row, trial in zip(rows, trials)
        ):
            raise ValueError(f"Manifest descriptors do not match {result_path}")
        if result_path.suffix.lower() != ".bin":
            validation_level = "json_and_manifest"
    elif result_path.suffix.lower() == ".bin":
        raise ValueError(f"Missing build-manifest.json for {result_path}")
    return {"path": str(result_path), "source_id": source_id,
            "validation_level": validation_level,
            "rows": rows, "manifest": manifest}


def _validate_kind48(capture: dict) -> None:
    rows = capture["rows"]
    if not rows:
        raise ValueError(f"No records in {capture['path']}")
    if any(row[0] != 48 for row in rows):
        raise ValueError(f"Capture is not entirely kind 48: {capture['path']}")
    groups: dict[tuple[int, ...], list[int]] = {}
    group_rows: dict[tuple[int, ...], list[tuple[int, ...]]] = {}
    for row in rows:
        key = row[:5]
        groups.setdefault(key, []).append(row[5])
        group_rows.setdefault(key, []).append(row)
    for key, repeats in groups.items():
        if len(repeats) != 8 or set(repeats) != REPEAT_VALUES:
            raise ValueError(f"Expected repeat indices 0..7 for descriptor {key} in {capture['path']}")
    varying_words: dict[int, int] = {index: 0 for index in range(6, 20)}
    unstable_groups = 0
    for repeat_rows in group_rows.values():
        if any(row[6:] != repeat_rows[0][6:] for row in repeat_rows[1:]):
            unstable_groups += 1
        for index in range(6, 20):
            if len({row[index] for row in repeat_rows}) > 1:
                varying_words[index] += 1
    capture["repeat_stability"] = {
        "group_count": len(group_rows),
        "unstable_group_count": unstable_groups,
        "groups_with_word_variation_by_byte_offset": {
            f"+{index * 2}": count for index, count in varying_words.items() if count
        },
    }


def _flag_counts(hw_value: int, emu_value: int) -> dict:
    changed = hw_value ^ emu_value
    return {
        "bbusy_mismatch": bool(changed & (1 << 14)),
        "bzero_mismatch": bool(changed & (1 << 13)),
        "other_bit_mismatch": bool(changed & ~((1 << 14) | (1 << 13)) & 0xFFFF),
    }


def compare(hardware_path: Path, emulator_paths: list[Path]) -> dict:
    hardware = _load_capture(hardware_path)
    _validate_kind48(hardware)
    emulators = [_load_capture(path) for path in emulator_paths]
    for emulator in emulators:
        _validate_kind48(emulator)
        if emulator["source_id"] != hardware["source_id"]:
            raise ValueError(f"source_id mismatch: {hardware['path']} vs {emulator['path']}")
        hw_descriptors = [row[:6] for row in hardware["rows"]]
        emu_descriptors = [row[:6] for row in emulator["rows"]]
        if hw_descriptors != emu_descriptors:
            raise ValueError(f"Descriptor/count mismatch: {hardware['path']} vs {emulator['path']}")

    reports = []
    for emulator in emulators:
        field_indices = {
            "first_d": (FIRST_D_WORD,),
            "second_d": (SECOND_D_WORD,),
            "beams": BEAM_WORDS,
            "dmaconr": DMACONR_WORDS,
        }
        mismatch_rows = {name: 0 for name in field_indices}
        dmaconr_read_mismatches = [0] * len(DMACONR_WORDS)
        flag_counts = {"bbusy": 0, "bzero": 0, "other_bits": 0}
        exact_mismatches = 0
        group_rows: dict[tuple[int, ...], dict] = {}
        for hw_row, emu_row in zip(hardware["rows"], emulator["rows"]):
            differing = [index for index in range(6, 20) if hw_row[index] != emu_row[index]]
            exact_mismatches += bool(differing)
            for name, indices in field_indices.items():
                mismatch_rows[name] += any(hw_row[index] != emu_row[index] for index in indices)
            for read_index, word_index in enumerate(DMACONR_WORDS):
                hv, ev = hw_row[word_index], emu_row[word_index]
                if hv != ev:
                    dmaconr_read_mismatches[read_index] += 1
                flags = _flag_counts(hv, ev)
                flag_counts["bbusy"] += flags["bbusy_mismatch"]
                flag_counts["bzero"] += flags["bzero_mismatch"]
                flag_counts["other_bits"] += flags["other_bit_mismatch"]
            group_key = tuple(hw_row[:5])
            group = group_rows.setdefault(group_key, {
                "rows": 0, "mismatch_repeats": [], "words": {}
            })
            group["rows"] += 1
            if differing:
                group["mismatch_repeats"].append(hw_row[5])
                for index in differing:
                    group["words"].setdefault(index, []).append({
                        "repeat": hw_row[5], "hardware": hw_row[index],
                        "emulator": emu_row[index],
                    })
        grouped_mismatches = [
            {
                "descriptor_without_repeat": list(key),
                "mismatching_repeats": value["mismatch_repeats"],
                "differing_words_by_byte_offset": {
                    f"+{index * 2}": changes
                    for index, changes in sorted(value["words"].items())
                },
            }
            for key, value in group_rows.items() if value["mismatch_repeats"]
        ]
        reports.append({
            "emulator": emulator["path"],
            "validation_level": emulator["validation_level"],
            "repeat_stability": emulator["repeat_stability"],
            "record_count": len(emulator["rows"]),
            "exact_mismatch_rows": exact_mismatches,
            "mismatch_rows_by_category": mismatch_rows,
            "dmaconr_read_mismatch_rows": {
                f"+{20 + 2 * index}": count
                for index, count in enumerate(dmaconr_read_mismatches)
            },
            "dmaconr_flag_mismatch_counts": flag_counts,
            "dmaconr_flag_mismatch_count_unit": "each record multiplied by each of the 8 reads",
            "stable_repeat_groups": {
                "group_count": len(group_rows),
                "groups_with_mismatches": len(grouped_mismatches),
                "mismatch_rows": sum(len(group["mismatching_repeats"]) for group in grouped_mismatches),
            },
            "mismatches_by_stable_group": grouped_mismatches,
        })
    return {
        "comparison": "read-only kind-48 raw-record comparison",
        "hardware": hardware["path"],
        "hardware_validation_level": hardware["validation_level"],
        "hardware_repeat_stability": hardware["repeat_stability"],
        "source_id": hardware["source_id"],
        "record_count": len(hardware["rows"]),
        "repeat_group_key": "descriptor words 0..4; repeat word 5 excluded; each group must contain repeats 0..7",
        "record_layout": {
            "first_d_byte_offset": 14,
            "second_d_byte_offset": 18,
            "dmaconr_byte_offsets": list(range(20, 36, 2)),
            "beam_byte_offsets": [12, 16, 36, 38],
        },
        "emulators": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hardware", type=Path, help="hardware capture directory/file")
    parser.add_argument("emulators", nargs="+", type=Path, help="one or more emulator capture directories/files")
    args = parser.parse_args()
    try:
        report = compare(args.hardware, args.emulators)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

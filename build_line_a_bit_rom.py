#!/usr/bin/env python3
"""Build and archive the controlled kind48 line-mode A-bit / BZERO probe."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import build_rom

ROOT = Path(__file__).resolve().parent
MAX_PAYLOAD_ROWS = 2560
ASHIFTS = (0, 2, 4)
VARIANTS = tuple(ashift | (b_full << 2) | (two_pixels << 3)
                   for two_pixels in range(2) for b_full in range(2) for ashift in range(3))
REPEATS = range(8)
TRUTH_A_PATTERNS = (0x8000, 0x4000, 0x2000, 0x1000,
                    0x0800, 0x0400, 0x2800, 0x2801)
TRUTH_MINTERMS = (0x00, 0xff, 0xf0, 0xcc, 0x33, 0xaa, 0x40, 0xca)
HISTORY_A_INDICES = (0, 6, 7)
HISTORY_MINTERM_INDICES = (2, 3, 6, 7)
HISTORY_PRIMES = (
    "none", "cpu_bdat_2800", "cpu_bdat_d7ff",
    "normal_b_dma_2800_d7ff", "normal_b_dma_d7ff_2800",
    "line_b_dma_2800_d7ff", "line_b_dma_d7ff_2800",
)
HISTORY_BDAT_ORDERS = ("before_con1", "after_con1", "skip")
LINE_HOLD_B_PATTERNS = (0x0001, 0x8000, 0xa55a, 0x1248)
LINE_HOLD_BSHIFTS = (0, 1, 7, 15)


def line_a_bit_rows():
    """Return kind48: 16 A-bit positions x 12 variants x 8 repeats."""
    rows = [(48, target, variant, 0, 0, repeat)
            for target in range(16)
            for variant in VARIANTS
            for repeat in REPEATS]
    expected = 16 * len(VARIANTS) * len(REPEATS)
    if len(rows) != expected:
        raise ValueError(f"kind48 matrix has {len(rows)} rows, expected {expected}")
    if len(rows) > MAX_PAYLOAD_ROWS:
        raise ValueError(f"row count {len(rows)} exceeds boot payload limit {MAX_PAYLOAD_ROWS}")
    if len(rows) != len(set(rows)):
        raise ValueError("kind48 descriptor matrix contains duplicate rows")
    if any(row[0] != 48 or row[3] != 0 or row[4] != 0 for row in rows):
        raise ValueError("kind48 descriptors must use kind 48 and fixed phase/delay zero")
    return rows


def line_a_truth_control_rows():
    """Kind48 marker-bit matrix for minterm/BZERO reduction controls."""
    rows = [(48, a_index, 0x10 | minterm | (b_full << 3), b_shift, 0, repeat)
            for a_index in range(len(TRUTH_A_PATTERNS))
            for minterm in range(len(TRUTH_MINTERMS))
            for b_full in range(2)
            for b_shift in range(2)
            for repeat in REPEATS]
    if len(rows) != 2048:
        raise ValueError(f"kind48 truth-control matrix has {len(rows)} rows, expected 2048")
    if len(rows) > MAX_PAYLOAD_ROWS:
        raise ValueError(f"row count {len(rows)} exceeds boot payload limit {MAX_PAYLOAD_ROWS}")
    if len(rows) != len(set(rows)):
        raise ValueError("kind48 truth-control descriptors contain duplicates")
    if any(row[0] != 48 or row[2] & 0x10 == 0 or row[3] not in (0, 1) or row[4] != 0
           for row in rows):
        raise ValueError("kind48 truth-control descriptor outside its encoding")
    return rows


def line_a_history_control_rows():
    """Return the bounded kind48 retained-B history discrimination matrix."""
    rows = [
        (48, a_index, 0x30 | (order_index << 2) | minterm_index,
         prime_index, 0, repeat)
        for a_index in HISTORY_A_INDICES
        for minterm_index in range(len(HISTORY_MINTERM_INDICES))
        for prime_index in range(len(HISTORY_PRIMES))
        for order_index in range(len(HISTORY_BDAT_ORDERS))
        for repeat in REPEATS
    ]
    expected = (len(HISTORY_A_INDICES) * len(HISTORY_MINTERM_INDICES)
                * len(HISTORY_PRIMES) * len(HISTORY_BDAT_ORDERS) * len(REPEATS))
    if len(rows) != expected or len(rows) != 2016:
        raise ValueError(f"kind48 history-control matrix has {len(rows)} rows, expected 2016")
    if len(rows) > MAX_PAYLOAD_ROWS:
        raise ValueError(f"row count {len(rows)} exceeds boot payload limit {MAX_PAYLOAD_ROWS}")
    if len(rows) != len(set(rows)):
        raise ValueError("kind48 history-control descriptors contain duplicates")
    if any(row[0] != 48 or row[1] not in HISTORY_A_INDICES
           or row[2] & 0x30 != 0x30 or row[2] & 3 not in range(4)
           or (row[2] >> 2) & 3 not in range(3)
           or row[3] not in range(len(HISTORY_PRIMES))
           or row[4] != 0 for row in rows):
        raise ValueError("kind48 history-control descriptor outside its encoding")
    return rows


def line_a_normal_history_control_rows():
    """Control line-mode B history with a normal-mode, one-word D target."""
    rows = [
        (48, 0, 0x70 | (order_index << 2) | 1, prime_index, 0, repeat)
        for prime_index in range(len(HISTORY_PRIMES))
        for order_index in range(len(HISTORY_BDAT_ORDERS))
        for repeat in REPEATS
    ]
    if len(rows) != 168 or len(rows) != len(set(rows)):
        raise ValueError(f"kind48 normal-history matrix has {len(rows)} rows, expected 168")
    if len(rows) > MAX_PAYLOAD_ROWS:
        raise ValueError(f"row count {len(rows)} exceeds boot payload limit {MAX_PAYLOAD_ROWS}")
    if any(row[0] != 48 or row[1] != 0 or row[2] & 0x70 != 0x70
           or row[2] & 3 != 1 or (row[2] >> 2) & 3 not in range(3)
           or row[3] not in range(len(HISTORY_PRIMES))
           or row[4] != 0 for row in rows):
        raise ValueError("kind48 normal-history descriptor outside its encoding")
    return rows


def line_a_normal_history_no_dma_control_rows():
    """Control held B state after a line-mode launch with all DMA channels off."""
    rows = [
        (48, 0, 0x70 | (order_index << 2) | 1, phase, 0, repeat)
        for phase in (7, 8)
        for order_index in range(len(HISTORY_BDAT_ORDERS))
        for repeat in REPEATS
    ]
    if len(rows) != 48 or len(rows) != len(set(rows)):
        raise ValueError(f"kind48 no-DMA history matrix has {len(rows)} rows, expected 48")
    if any(row[0] != 48 or row[1] != 0 or row[2] not in (0x71, 0x75, 0x79)
           or row[3] not in (7, 8) or row[4] != 0 for row in rows):
        raise ValueError("kind48 no-DMA history descriptor outside its encoding")
    return rows


def line_a_line_hold_matrix_rows():
    """Cross held B shifter state over line lengths, shifts, patterns and write order."""
    rows = [
        (48, pattern_index, 0xf0 | (order_index << 2) | bshift_index,
         pixels, 0, repeat)
        for pattern_index in range(len(LINE_HOLD_B_PATTERNS))
        for order_index in range(len(HISTORY_BDAT_ORDERS))
        for bshift_index in range(len(LINE_HOLD_BSHIFTS))
        for pixels in (1, 2, 3)
        for repeat in REPEATS
    ]
    if len(rows) != 1152 or len(rows) != len(set(rows)):
        raise ValueError(f"kind48 line-hold matrix has {len(rows)} rows, expected 1152")
    if any(row[0] != 48 or row[1] not in range(4)
           or row[2] & 0xf0 != 0xf0 or row[2] & 3 not in range(4)
           or (row[2] >> 2) & 3 not in range(3)
           or row[3] not in (1, 2, 3) or row[4] != 0
           for row in rows):
        raise ValueError("kind48 line-hold descriptor outside its encoding")
    return rows


def line_a_line_hold_c_dma_matrix_rows():
    """Repeat the held-B matrix with C DMA active during the line prime."""
    rows = [
        (48, pattern_index, 0xe0 | (order_index << 2) | bshift_index,
         pixels, 0, repeat)
        for pattern_index in range(len(LINE_HOLD_B_PATTERNS))
        for order_index in range(len(HISTORY_BDAT_ORDERS))
        for bshift_index in range(len(LINE_HOLD_BSHIFTS))
        for pixels in (1, 2, 3)
        for repeat in REPEATS
    ]
    if len(rows) != 1152 or len(rows) != len(set(rows)):
        raise ValueError(f"kind48 C-DMA line-hold matrix has {len(rows)} rows, expected 1152")
    if any(row[0] != 48 or row[1] not in range(4)
           or row[2] & 0xf0 != 0xe0 or row[2] & 3 not in range(4)
           or (row[2] >> 2) & 3 not in range(3)
           or row[3] not in (1, 2, 3) or row[4] != 0
           for row in rows):
        raise ValueError("kind48 C-DMA line-hold descriptor outside its encoding")
    return rows


def variant_metadata():
    """Document variant bits and the literal register values they select."""
    return dict(
        encoding={
            "bits_1_0": "ASHIFT index into [0, 2, 4]; value 3 is unused",
            "bit_2": "BLTBDAT is 0xffff when set, 0x0000 when clear",
            "bit_3": "two-pixel BLTSIZE when set, one-pixel BLTSIZE when clear",
        },
        variants=[
            dict(variant=variant, ashift=ASHIFTS[variant & 3],
                 b_data=0xffff if variant & 4 else 0,
                 pixels=2 if variant & 8 else 1,
                 bltsize=0x0082 if variant & 8 else 0x0042)
            for variant in VARIANTS
        ],
        unused_variant_values=[3, 7, 11, 15],
    )


def truth_control_metadata():
    return dict(
        descriptor_fields={
            "kind": "48",
            "target": "index into a_pattern_values",
            "variant_bits_2_0": "index into minterms",
            "variant_bit_3": "BLTBDAT is 0xffff when set, 0x0000 when clear",
            "variant_bit_4": "truth-control mode marker; legacy kind48 variants remain 0..14",
            "phase": "BSHIFT 0/1; cleared during beam synchronization and restored after the observer",
            "delay": "fixed zero",
            "repeat": "0..7",
        },
        variant_encoding=dict(minterm_index="bits 2..0",
                              b_data="bit 3: $ffff if set, otherwise $0000",
                              truth_control_marker="bit 4"),
        row_count=2048,
        a_pattern_values=[f"0x{value:04x}" for value in TRUTH_A_PATTERNS],
        minterms=[
            dict(index=i, value=f"0x{value:02x}", function=fn)
            for i, (value, fn) in enumerate(zip(
                TRUTH_MINTERMS,
                ("0", "1", "A", "B", "not B", "C", "A and B and not C",
                 "cookie-cut control 0xca")))
        ],
        controls=dict(ashift=0, bshift_values=[0, 1], b_data_values=[0, 0xffff],
                      b_dma=False, c_data=0, c_dma=True, pixels=2,
                      bltsize="0x0082", bshift0="wraps across the two-pixel line",
                      bshift1="no-wrap comparison",
                      custom_register_write_order=[
                          "BLTADAT=$8000 seed", "BLTADAT=selected pattern",
                          "BLTCON0=0x0b00|minterm", "BLTBDAT=selected B data",
                          "BLTCON1=0x0001 or 0x1001 from saved BSHIFT phase"],
                      ca_bshift0_reproduction=dict(
                          minterm="0xca", bshift=0, b_data_values=[0, 0xffff],
                          a_patterns=["0x2000", "0x0800", "0x2800", "0x2801"],
                          c_data=0, pixels=2)),
        rationale=("Crosses effective A patterns near bits 13/11 with minterm basis and "
                   "BSHIFT/B-data controls to distinguish BZERO reduction inputs from "
                   "stored D words."),
    )


def history_control_metadata():
    return dict(
        descriptor_fields={
            "kind": "48",
            "target": "index into selected existing a_pattern_values [0, 6, 7]",
            "variant_bit_5": "history-control marker; bit 4 remains truth-control marker",
            "variant_bits_1_0": "index into LF values [0xf0, 0xcc, 0x40, 0xca]",
            "variant_bits_3_2": "target BLTBDAT order: before CON1, after CON1, or skipped",
            "phase": "B-history precondition profile index 0..6; temporarily cleared for beam alignment",
            "delay": "fixed zero",
            "repeat": "0..7",
        },
        row_count=2016,
        a_pattern_indices=list(HISTORY_A_INDICES),
        a_pattern_values=[f"0x{TRUTH_A_PATTERNS[i]:04x}" for i in HISTORY_A_INDICES],
        minterm_indices=list(HISTORY_MINTERM_INDICES),
        minterms=[f"0x{TRUTH_MINTERMS[i]:02x}" for i in HISTORY_MINTERM_INDICES],
        prime_profiles=[
            {"index": i, "name": name, "bdat_value": value}
            for i, (name, value) in enumerate(zip(
                HISTORY_PRIMES, (None, "0x2800", "0xd7ff", None, None, None, None)))
        ],
        bdat_orders=[
            {"index": i, "name": name,
             "target_write": ("BLTBDAT=0 before target BLTCON1" if i == 0 else
                              "BLTBDAT=0 after target BLTCON1" if i == 1 else
                              "skip target BLTBDAT write; retain prime state")}
            for i, name in enumerate(HISTORY_BDAT_ORDERS)
        ],
        prime_operations={
            "initial_common_bdat": "BLTBDAT=0 before selecting the prime profile",
            "none": "no additional B-state priming",
            "cpu_register_profiles": ["BLTBDAT=$2800", "BLTBDAT=$d7ff"],
            "normal_b_dma_profiles": {
                "bltcon0": "0x04cc (B enabled; A/C/D disabled)",
                "bltcon1": "0x0000",
                "bltsize": "0x0042 (two words)",
                "b_mod": 0,
                "b_pointer": "0x18000",
                "source_words": ["0x2800", "0xd7ff"],
                "reverse_profile": "0x18000=$d7ff, 0x18002=$2800",
            },
            "line_b_dma_profiles": {
                "bltcon0": "0x04cc (B enabled; A/C/D disabled)",
                "bltcon1": "0x0001",
                "bltsize": "0x0082 (two pixels)",
                "b_mod": 2,
                "b_pointer": "0x18000",
                "source_words": ["0x2800", "0xd7ff"],
                "reverse_profile": "0x18000=$d7ff, 0x18002=$2800",
                "line_setup": {"apt": "-80", "amod": "-280", "cmod": 80, "dmod": 80},
            },
            "settle": "wait until BBUSY clears, then 16 NOPs before target setup",
        },
        target={
            "line_mode": True, "bshift": 0, "pixels": 2, "bltsize": "0x0082",
            "c_data": 0, "useb": False, "usec": True,
            "bltcon0": "0x0b00 | selected LF", "bltcon1": "0x0001",
            "bdat_initial_write": "omitted after priming; order index decides whether target writes zero",
            "observer": "unchanged FF7800; eight adjacent DMACONR reads",
        },
        rationale=("Separates CPU BLTBDAT register history, normal B-channel DMA history, "
                   "and line-mode B-channel DMA history against the $2800 A-mask witness."),
    )


def normal_history_control_metadata():
    return dict(
        descriptor_fields={
            "kind": "48",
            "target": "0 (A pattern index retained for shared descriptor layout)",
            "variant_marker_bits": {"normal_history_control": 6,
                                    "history_control": 5, "truth_control": 4},
            "variant_bits_3_2": "target BLTBDAT order: before CON1, after CON1, or skipped",
            "variant_bits_1_0": "fixed local LF index 1 (0xcc; descriptor compatibility)",
            "phase": "B-history precondition profile index 0..6",
            "delay": "fixed zero",
            "repeat": "0..7",
        },
        row_count=168,
        prime_profiles=[
            {"index": i, "name": name, "bdat_value": value}
            for i, (name, value) in enumerate(zip(
                HISTORY_PRIMES, (None, "0x2800", "0xd7ff", None, None, None, None)))
        ],
        prime_operations=history_control_metadata()["prime_operations"],
        target=dict(
            mode="normal area/copy mode",
            bltcon0="0x01cc (D enabled; A/B/C DMA disabled; LF=CC) for B-to-D copy",
            bltcon1="0x0000",
            bltsize="0x0041 (one D word)",
            bdat_write_order="before CON1, after CON1, or skipped according to variant bits 3..2",
            b_dma=False, dmod=0, d_destination="0x10000",
            second_observed_destination="0x11050 remains zero because the target writes one word",
            observer="unchanged FF7800; eight adjacent DMACONR reads",
        ),
        rationale=("Controls whether the post-B-DMA BLTBDAT value remains available to a "
                   "normal-mode one-word B-to-D operation when B DMA is disabled."),
    )


def normal_history_no_dma_control_metadata():
    return dict(
        descriptor_fields={
            "kind": "48",
            "target": "0 (shared normal-mode B-to-D target)",
            "variant_marker_bits": {"normal_history_control": 6,
                                    "history_control": 5, "truth_control": 4},
            "variant_bits_3_2": "target BLTBDAT order: before CON1, after CON1, or skipped",
            "variant_bits_1_0": "fixed local LF index 1 (0xcc)",
            "phase": "no-DMA line-prime profile: 7 loads $2800; 8 loads $d7ff",
            "delay": "fixed zero",
            "repeat": "0..7",
        },
        row_count=48,
        prime_profiles=[
            {"index": 7, "name": "line_mode_no_dma_bdat_2800", "bltcon1_initial": "0x0000",
             "bdat_cpu_write": "0x2800", "bltcon1_line": "0x0001",
             "bltcon0": "0x00cc (all DMA channels disabled)", "bltsize": "0x0082",
             "source_memory_required": False},
            {"index": 8, "name": "line_mode_no_dma_bdat_d7ff", "bltcon1_initial": "0x0000",
             "bdat_cpu_write": "0xd7ff", "bltcon1_line": "0x0001",
             "bltcon0": "0x00cc (all DMA channels disabled)", "bltsize": "0x0082",
             "source_memory_required": False},
        ],
        target=normal_history_control_metadata()["target"],
        rationale=("Tests whether line-mode activation alone rotates/retains CPU-loaded "
                   "BLTBDAT when no blitter DMA channel is enabled."),
    )


def line_hold_matrix_metadata():
    return dict(
        descriptor_fields={
            "kind": "48",
            "target": "index into b_patterns",
            "variant_marker_bits": {"line_hold": 7, "normal_history_control": 6,
                                    "history_control": 5, "C_DMA_control": 4},
            "C_DMA_control": "bit 4 set disables C DMA; clear enables it",
            "variant_bits_1_0": "BSHIFT index into [0, 1, 7, 15]",
            "variant_bits_3_2": "target BLTBDAT order: before CON1, after CON1, or skipped",
            "phase": "line-prime pixel count 1..3",
            "delay": "fixed zero",
            "repeat": "0..7",
        },
        row_count=1152,
        b_patterns=[f"0x{value:04x}" for value in LINE_HOLD_B_PATTERNS],
        bshifts=list(LINE_HOLD_BSHIFTS),
        line_prime=dict(
            bltcon1="(BSHIFT << 12) | 0x0001",
            bltcon0="0x00cc (all DMA channels disabled)",
            bltsize="(pixels << 6) | 2",
            apt="-80", amod=-280, bmod=0, cmod=80, dmod=80,
            bdat_cpu_write="selected raw B pattern while CON1=0",
            memory_fetches=False,
            settle="wait until BBUSY clears, then 16 NOPs",
        ),
        target=dict(
            mode="normal one-word B-to-D copy",
            bltcon0="0x01cc (D enabled; A/B/C DMA disabled)",
            bltcon1="0x0000",
            bltsize="0x0041",
            d_destination="0x10000",
            dmod=0,
            bdat_orders=["write zero before CON1", "write zero after CON1", "skip write"],
            observer="unchanged FF7800; eight adjacent DMACONR reads",
            second_observed_destination="0x11050 remains zero",
        ),
        predicted_model=dict(
            status="A500 measurement rule; emulator candidate results remain provisional",
            skip=("pixels == 1: shift_combine(0, raw_BDAT, BSHIFT, false); "
                  "pixels in 2..3: rotate_right(raw_BDAT, (BSHIFT - (pixels - 1)) & 15)"),
            before_con1="shift_combine(raw_BDAT, 0, end_BSHIFT, false)",
            after_con1="zero after CON1=0 resets the normal-mode held B result",
            end_BSHIFT="(BSHIFT - pixels) & 15",
            source_id="f721cceba127d7b3f226ab1ac3ae8ae6ee458e5e33ae5ddada142c94204949d2",
            hardware_packet_sha256="64d4776bafe96e924c5dae365917ff24b712daaef3ab5bed7eac7fe1950181db",
        ),
        rationale=("Tests line-mode shifter retention without B DMA across unseen raw words, "
                   "BSHIFT values, and one-to-three-pixel lengths."),
    )


def line_hold_c_dma_matrix_metadata():
    metadata = line_hold_matrix_metadata()
    metadata["descriptor_fields"]["variant_marker_bits"] = {
        "line_hold": 7, "normal_history_control": 6,
        "history_control": 5, "C_DMA_control": 4,
    }
    metadata["descriptor_fields"]["C_DMA_control"] = "variant bit 4 clear enables C DMA"
    metadata["line_prime"].update(
        bltcon0="0x02cc (C DMA enabled; A/B/D DMA disabled)",
        c_pointer="0x14000",
        c_data="zero-filled 128-word buffer (256 bytes)",
        d_pointer=("0x15000 for the first line-prime D write; later D writes track C "
                   "to 0x14050/0x140a0"),
        d_sink_span=("first word at 0x15000; subsequent line D writes land in the "
                     "zeroed C buffer at 0x14050/0x140a0"),
        cmod=80,
        memory_fetches=("C channel only; line D writes track the C pointer after the "
                        "first pixel; buffers cover three-pixel stepping"),
    )
    metadata["predicted_model"]["status"] = (
        "C-DMA generalization hypothesis; not yet validated by A500 results"
    )
    metadata["rationale"] = (
        "Repeats the held-B validation matrix with C DMA enabled during the line prime, "
        "using a zero C source to test whether the measured B hold rule generalizes."
    )
    return metadata


def snapshot_sources(out):
    """Archive this wrapper and every source file used to assemble the ROM."""
    sources = [ROOT / "build_line_a_bit_rom.py", ROOT / "build_rom.py", ROOT / "run_rom.py"]
    sources += sorted(path for folder in (ROOT / "src/rom", ROOT / "vendor/rbcp")
                      for path in folder.rglob("*") if path.is_file())
    snapshot = out / "source_snapshot"
    entries = []
    for source in sources:
        relative = source.relative_to(ROOT)
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        destination.write_bytes(data)
        entries.append(dict(path=relative.as_posix(), sha256=hashlib.sha256(data).hexdigest()))
    (snapshot / "manifest.json").write_text(json.dumps(entries, indent=2) + "\n")
    return entries


def build(assembler, wsl, out, truth_control=False, history_control=False,
          normal_history_control=False, normal_history_no_dma_control=False,
          line_hold_matrix=False, line_hold_c_dma_matrix=False):
    out = Path(out).resolve()
    if out.exists():
        raise FileExistsError(f"output archive already exists: {out}")
    if sum((truth_control, history_control, normal_history_control,
            normal_history_no_dma_control, line_hold_matrix,
            line_hold_c_dma_matrix)) > 1:
        raise ValueError("kind48 control modes are mutually exclusive")
    rows = (line_a_line_hold_c_dma_matrix_rows() if line_hold_c_dma_matrix else
            line_a_line_hold_matrix_rows() if line_hold_matrix else
            line_a_normal_history_no_dma_control_rows() if normal_history_no_dma_control else
            line_a_normal_history_control_rows() if normal_history_control else
            line_a_history_control_rows() if history_control else
            line_a_truth_control_rows() if truth_control else line_a_bit_rows())
    original_trials = build_rom.trials
    try:
        build_rom.trials = lambda *args, **kwargs: rows
        manifest = build_rom.build(assembler, wsl=wsl, edges=True)
    finally:
        build_rom.trials = original_trials

    shutil.copytree(ROOT / "build/rom", out)
    snapshot = snapshot_sources(out)
    manifest["line_a_bit"] = dict(
        suite="line_a_bit",
        row_count=len(rows),
        descriptor_fields=["kind", "target", "variant", "phase", "delay", "repeat"],
        target_values=list(range(16)),
        target_meaning="BLTADAT one-hot bit index; bit 0 is 0x8000, bit 15 is 0x0001",
        variants=variant_metadata(),
        phase=0,
        delay=0,
        repeats=8,
        line=dict(a_data="0x8000 >> target", b_data="variant bit 2 ? 0xffff : 0x0000",
                  c_data=0, useb=False, bltcon0_base="0x0bca", bltcon1="0x0001",
                  ashift="variant bits 1..0 select [0,2,4]", bltapt=-80,
                  bltsize="0x0042 for one pixel; 0x0082 for two pixels",
                  c_source="0x11000", d_destination="0x10000"),
        observer_address=0xff7800,
        observer_write=dict(instruction="MOVE.W D3,(A3)", address=0x18000, value=0,
                            sequence=["BLTSIZE write", "MOVE.W D3,(A3) to $18000",
                                      "8 adjacent DMACONR reads"]),
        observations=dict(dmaconr_reads=8, postbusy_destination_words={
            "first_D_word": "0x10000", "second_line_mode_D_word": "0x11050"}),
        source_addresses=dict(a="0x12000", b="0x16000", c="0x11000"),
        source_lengths_words=dict(a=16, b=16, c=82),
        initialization=dict(all_source_words=0, second_c_word_address="0x11050",
                           destination_length_words=1024, destination_words=0),
        runtime_memory_check=dict(expected_source_value=0,
                                  source_lengths_words=dict(a=16, b=16, c=82),
                                  scratch_address="0x18000", expected_final_scratch_word=0),
        source_snapshot=snapshot,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
    )
    if truth_control:
        truth = truth_control_metadata()
        manifest["line_a_bit"].update(
            row_count=len(rows),
            target_values=list(range(len(TRUTH_A_PATTERNS))),
            target_meaning="index into the literal ADAT patterns in truth_control.a_pattern_values",
            variants=truth["variant_encoding"],
            phase="BSHIFT 0/1, saved and cleared for timing alignment",
            delay=0,
            repeats=len(REPEATS),
            line=dict(a_data="truth_control.a_pattern_values[target]",
                      b_data="variant bit 3 ? 0xffff : 0x0000", c_data=0,
                      useb=False, usec=True, bltcon0="0x0b00 | selected minterm",
                      bltcon1="0x0001 | (BSHIFT << 12)", ashift=0,
                      bltapt=-80, bltsize="0x0082 (two pixels)",
                      c_source="0x11000", d_destination="0x10000"),
            truth_control=truth,
        )
    if history_control:
        history = history_control_metadata()
        manifest["line_a_bit"].update(
            row_count=len(rows),
            target_values=list(HISTORY_A_INDICES),
            target_meaning="index into history_control.a_pattern_values",
            variants=dict(marker_bits={"history_control": 5, "truth_control": 4},
                          lf_index="variant bits 1..0",
                          bdat_order_index="variant bits 3..2"),
            phase="history_control.prime_profiles[phase]; cleared for beam alignment",
            delay=0,
            repeats=len(REPEATS),
            line=dict(a_data="history_control.a_pattern_values[target]",
                      b_data="primed history preserved unless selected order writes zero",
                      c_data=0, useb=False, usec=True,
                      bltcon0="0x0b00 | selected history_control minterm",
                      bltcon1="0x0001", bshift=0, ashift=0,
                      bltapt=-80, bltsize="0x0082 (two pixels)",
                      c_source="0x11000", d_destination="0x10000"),
            history_control=history,
        )
    if normal_history_control:
        normal_history = normal_history_control_metadata()
        manifest["line_a_bit"].update(
            row_count=len(rows),
            target_values=[0],
            target_meaning="normal-mode B-to-D copy target; shared pattern index fixed at zero",
            variants=dict(marker_bits={"normal_history_control": 6,
                                       "history_control": 5, "truth_control": 4},
                          lf_index="variant bits 1..0, fixed to one ($cc)",
                          bdat_order_index="variant bits 3..2"),
            phase="normal_history_control.prime_profiles[phase]",
            delay=0,
            repeats=len(REPEATS),
            line=dict(b_data="primed BLTBDAT retained or overwritten by selected order",
                      useb=False, bltcon0="0x01cc", bltcon1="0x0000",
                      bltsize="0x0041 (one D word)", d_destination="0x10000",
                      dmod=0, second_observed_destination="0x11050 remains zero"),
            normal_history_control=normal_history,
        )
    if normal_history_no_dma_control:
        no_dma = normal_history_no_dma_control_metadata()
        manifest["line_a_bit"].update(
            row_count=len(rows),
            target_values=[0],
            target_meaning="shared normal-mode B-to-D copy target",
            variants=dict(marker_bits={"normal_history_control": 6,
                                       "history_control": 5, "truth_control": 4},
                          lf_index="variant bits 1..0, fixed to one ($cc)",
                          bdat_order_index="variant bits 3..2"),
            phase="normal_history_no_dma_control.prime_profiles[phase]",
            delay=0,
            repeats=len(REPEATS),
            line=dict(bltcon0="0x01cc", bltcon1="0x0000",
                      bltsize="0x0041 (one D word)", d_destination="0x10000",
                      dmod=0, second_observed_destination="0x11050 remains zero"),
            normal_history_no_dma_control=no_dma,
        )
    if line_hold_matrix or line_hold_c_dma_matrix:
        hold = (line_hold_c_dma_matrix_metadata() if line_hold_c_dma_matrix else
                line_hold_matrix_metadata())
        line_hold_marker = 0xe0 if line_hold_c_dma_matrix else 0xf0
        hold_marker_bits = {"line_hold": 7, "normal_history_control": 6,
                            "history_control": 5, "C_DMA_control": 4}
        manifest["line_a_bit"].update(
            row_count=len(rows),
            target_values=list(range(len(LINE_HOLD_B_PATTERNS))),
            target_meaning="index into line_hold_matrix.b_patterns; initial raw BLTBDAT",
            variants=dict(marker_bits=hold_marker_bits,
                          bshift_index="variant bits 1..0",
                          bdat_order_index="variant bits 3..2",
                          fixed_marker_nibble=f"0x{line_hold_marker:02x}"),
            phase="line-prime pixel count 1..3",
            delay=0,
            repeats=len(REPEATS),
            line=dict(bltcon0="0x01cc", bltcon1="0x0000",
                      bltsize="0x0041 (one D word)", d_destination="0x10000", dmod=0),
            line_hold_matrix=hold,
        )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vasm", default="vasmm68k_mot")
    parser.add_argument("--wsl", action="store_true")
    parser.add_argument("--out", type=Path, required=True,
                        help="new directory receiving the immutable ROM build archive")
    controls = parser.add_mutually_exclusive_group()
    controls.add_argument("--truth-control", action="store_true",
                          help="build the bounded 2,048-row minterm/BZERO line control matrix")
    controls.add_argument("--history-control", action="store_true",
                          help="build the bounded 2,016-row retained-B history matrix")
    controls.add_argument("--normal-history-control", action="store_true",
                          help="build the 168-row normal-mode held-B target control")
    controls.add_argument("--normal-history-no-dma-control", action="store_true",
                          help="build the 48-row all-DMA-off line-prime held-B control")
    controls.add_argument("--line-hold-matrix", action="store_true",
                          help="build the 1,152-row held-B shifter validation matrix")
    controls.add_argument("--line-hold-c-dma-matrix", action="store_true",
                          help="build the 1,152-row held-B matrix with C DMA during line prime")
    args = parser.parse_args(argv)
    build(args.vasm, args.wsl, args.out, truth_control=args.truth_control,
          history_control=args.history_control,
          normal_history_control=args.normal_history_control,
          normal_history_no_dma_control=args.normal_history_no_dma_control,
          line_hold_matrix=args.line_hold_matrix,
          line_hold_c_dma_matrix=args.line_hold_c_dma_matrix)
    return 0


if __name__ == "__main__":
    sys.exit(main())





#!/usr/bin/env python3
"""Build and archive the focused kind47 Copper/blitter wait experiment."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import build_rom

ROOT = Path(__file__).resolve().parent
MAX_PAYLOAD_ROWS = 2560
REPEATS = range(2)
CPU_LAUNCH_STUB_SIZE = 0x3A  # FFC000..FFC039; last opcode is the final absolute JMP.
CPU_FINISH_SWEEP_STUB_SIZE = 0x100  # FFC100..FFC1FF is an explicitly padded code slot.


def copper_wait_rows(unrolled=False, no_blit=False, cpu_launch=False, finish_sweep=False):
    """Kind47 descriptors: target, variant, phase, WAIT h-position, repeat."""
    if (cpu_launch or finish_sweep) and not unrolled:
        raise ValueError("CPU-launch controls require --unrolled")
    if (cpu_launch or finish_sweep) and no_blit:
        raise ValueError("CPU-launch controls cannot be combined with --no-blit")
    if cpu_launch and finish_sweep:
        raise ValueError("select either --cpu-launch or --finish-sweep")
    variant_base = ((104 if finish_sweep else 32 if cpu_launch else 0)
                    + (8 if unrolled and not finish_sweep else 0)
                    + (16 if no_blit else 0))
    variants = range(variant_base, variant_base + (4 if finish_sweep else 8))
    rows = [(47, target, variant, phase, delay, repeat)
            for target in range(16 if finish_sweep else 4)
            for variant in variants      # BLTPRI, chip reads, 4-plane DMA, unrolled mode
            for phase in range(2)
            for delay in range(8)
            for repeat in REPEATS]
    expected = 2048 if finish_sweep else 1024
    if len(rows) != expected:
        raise ValueError(f"kind47 matrix has {len(rows)} rows, expected {expected}")
    if len(rows) > MAX_PAYLOAD_ROWS:
        raise ValueError(f"row count {len(rows)} exceeds payload limit {MAX_PAYLOAD_ROWS}")
    if len(rows) != len(set(rows)):
        raise ValueError("kind47 descriptor matrix contains duplicate rows")
    if any(row[0] != 47 or not variant_base <= row[2] <= variant_base + 7
           or row[4] > 7 for row in rows):
        raise ValueError("kind47 descriptor field outside its encoding")
    return rows


def snapshot_sources(out):
    sources = [ROOT / "build_copper_wait_rom.py", ROOT / "build_rom.py",
               ROOT / "run_rom.py", ROOT / "run_winuae_rom.py"]
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


def build(assembler, wsl, out, unrolled=False, no_blit=False, cpu_launch=False,
          finish_sweep=False):
    out = Path(out).resolve()
    if out.exists():
        raise FileExistsError(f"output archive already exists: {out}")
    rows = copper_wait_rows(unrolled, no_blit, cpu_launch, finish_sweep)
    original_trials = build_rom.trials
    try:
        build_rom.trials = lambda *args, **kwargs: rows
        manifest = build_rom.build(assembler, wsl=wsl, edges=True)
    finally:
        build_rom.trials = original_trials

    shutil.copytree(ROOT / "build/rom", out)
    snapshot = snapshot_sources(out)
    cpu_owned = cpu_launch or finish_sweep
    manifest["copper_wait"] = dict(
        suite="copper_wait",
        row_count=len(rows),
        descriptor_fields=["kind", "target", "variant", "phase",
                           ("launch_pad_nops" if finish_sweep else "wait_hpos_index"), "repeat"],
        targets=([
            dict(index=target, width_index=target >> 2,
                 width_words=(1, 4, 8, 16)[target >> 2],
                 legacy_target=target & 3,
                 blit=("D-only minterm 0xff" if target & 1 == 0 else "A-to-D copy"),
                 wait_count=(2 if target & 2 else 1))
            for target in range(16)
        ] if finish_sweep else [
            dict(index=0, blit=("not launched; destination remains 0xdead" if no_blit else "D-only minterm 0xff; 16 destination words become 0xffff")),
            dict(index=1, blit=("not launched; destination remains 0xdead" if no_blit else "A-to-D copy")),
            dict(index=2, blit=("not launched; destination remains 0xdead" if no_blit else "D-only minterm 0xff; 16 destination words become 0xffff")),
            dict(index=3, blit=("not launched; destination remains 0xdead" if no_blit else "A-to-D copy")),
        ]),
        target_encoding=(dict(bits_3_2="width index into [1,4,8,16] words",
                              bits_1_0="legacy target: blit mode in bit0, one/two WAITs in bit1")
                         if finish_sweep else None),
        waits=dict(
            initial_beam_wait=dict(
                position=(("line 66 hpos 0x04; finish-sweep-only early entry before CPU launch"
                           if finish_sweep else "line 66 hpos 0x20; fixed early entry before CPU launch") if cpu_owned
                          else "line 66 at selected hpos"),
                value=((0x4205 if finish_sweep else 0x4221) if cpu_owned else "0x4261 + 2*delay"),
                mask=0xfffe, bfd=1),
            blitter_wait_count=dict(target_bit=1, values={0: 1, 1: 1, 2: 2, 3: 2},
                                    encoding="same already-eligible WAIT repeated",
                                    mask=0x7ffe, bfd=0,
                                    position=("fixed line66 hpos 0x60" if finish_sweep
                                              else "selected hpos 0x60+2*delay")),
        ),
        variants=dict(
            bit0="BLTPRI off/on via DMACON",
            bit1=("unrolled quiet NOPs vs unrolled chip operand reads" if unrolled else
                  "quiet ROM NOP/DBRA vs chip operand read/DBRA loop"),
            bit2=("fixed off in finish-sweep rows" if finish_sweep else
                  "bitplane DMA off/on; four pointers read the same initialized chip area"),
            bit3=dict(value=int(unrolled), mode="unrolled finite ROM sequence" if unrolled else "512-iteration DBRA loop"),
            bit4=dict(value=int(no_blit), mode="replace Copper BLTSIZE MOVE with NOOP $01fe,$0000; same two-word slot" if no_blit else "Copper BLTSIZE launches blit"),
            bit5=dict(value=int(cpu_owned), mode=("CPU preloads CON0/CON1; Copper BLTSIZE slot is NOOP; fixed ROM beam-polls line 66 h>=0x10 for finish-sweep or h>=0x30 for CPU-launch, records actual CPU launch at +14, and writes BLTSIZE" if cpu_owned else "Copper launches BLTSIZE")),
            bit6=dict(value=int(finish_sweep), mode=("CPU finish-width sweep; bit5 CPU launch plus width control in target; fixed BFD WAIT at hpos 0x60 and delay is a 0..7 NOP launch pad" if finish_sweep else "unused")),
        ),
        phase=dict(values={0: "conditional branch plus NOP", 1: "conditional branch plus EXG D0,D1 and BRA"},
                   sync_beam_delay=("phase paths execute after the h>=0x10 poll and before the NOP launch pad; timestamp is sampled afterward" if finish_sweep else "phase 0 executes zero delay NOPs; phase 1 executes one delay NOP"),
                   placement=("FFC100 CPU launch stub after line66/h>=0x10 poll" if finish_sweep else "after sync_beam and immediately before fixed ROM traffic loop"),
                   interpretation=("unequal NOP/EXG/BRA phase paths are reported separately; the actual +14 VHPOSR sample follows phase and launch pad" if finish_sweep else "phase selects unequal instruction paths: after TST/BEQ, phase 0 executes NOP; phase 1 executes EXG then BRA")),
        wait=dict(line=66, hpos_base=(0x60 if finish_sweep else 0x60),
                  hpos_step=(0 if finish_sweep else 2),
                  delays=(list(range(8)) if not finish_sweep else None),
                  launch_pad_nops=(list(range(8)) if finish_sweep else None)),
        repeats=len(REPEATS),
        blit=dict(launched=not no_blit, launch_owner=("CPU" if cpu_owned else ("none" if no_blit else "Copper")), copper_slot=("NOOP $01fe,$0000" if no_blit or cpu_owned else "MOVE BLTSIZE,$0050"), size=(dict(values=[0x0041, 0x0044, 0x0048, 0x0050], selected_by="target bits 3..2") if finish_sweep else 0x0050), width_words=([1, 4, 8, 16] if finish_sweep else 16), height=1, destination=0x10000,
                  initial_destination=0xdead, bltmod_a=0, bltmod_b=0,
                  bltmod_c=0, bltmod_d=0,
                  d_only=dict(bltcon0=0x01ff, minterm=0xff, result=0xffff),
                  a_to_d=dict(bltcon0=0x09f0, source=0x12000, source_word=0xaaaa)),
        observer=dict(cpu_loop=0xff7900, copper_list=0x6000, copper_marker="INTREQ COPER",
                      cpu_launch_stub=(0xffc100 if finish_sweep else 0xffc000 if cpu_launch else None),
                      critical_interval=("CPU beam-polls line 66 to h>=0x10, runs the phase path and selected 0..7 NOP pad, samples VHPOSR into D2 immediately before BLTSIZE, then runs fixed unrolled traffic without DMACONR reads; D2 is stored at +14 after SR is masked" if finish_sweep else "CPU beam-polls line 66 until h>=0x30, stores the actual pre-write VHPOSR at byte +14 and writes BLTSIZE; then fixed unrolled ROM traffic, without DMACONR reads" if cpu_launch else "no DMACONR reads; fixed ROM traffic sequence"),
                      traffic_paths=(dict(
                          mode="unrolled",
                          quiet=dict(address=0xff7a00, opcode="NOP", count=512, dbra_count=0),
                          chip_read=dict(address=0xff7e10, opcode="MOVE.W $18000,D0", count=256, dbra_count=0))
                          if unrolled else dict(
                          mode="DBRA",
                          quiet=dict(address=0xff7900, opcodes=["NOP", "DBRA"], iterations=512),
                          chip_read=dict(address=0xff7900, opcodes=["MOVE.W $18000,D0", "DBRA"], iterations=512))),
                      record_offsets={"launch_beam_after_sync": 12,
                                      "cpu_launch_beam_prewrite": (14 if cpu_owned else None),
                                      "launch_ref_unused": (None if cpu_owned else 14),
                                      "end_beam_after_settle": 16, "end_ref_unused": 18,
                                      "DMACONR_at_irq_counter_field": 20,
                                      "first_destination_at_irq_icr_field": 22,
                                      "irq_beam": 24, "irq_level": 26, "saved_pc": 28,
                                      "status": dict(offset=32, success=0, watchdog_timeout=1),
                                      "marker_count_aux": 34,
                                      "final_first_destination": 36,
                                      "final_last_destination": 38}),
        dmaconr=dict(sample="COPER IRQ handler", bbusy_bit=14,
                     dma_enable_bits=dict(blitter=6, copper=7, bitplane=8),
                     bltpri_enable_bit=10),
        limitations=["Software observation only; A500/68000 capture required."] + ([] if no_blit else ["The 16-word blit may complete before the COPER marker; both IRQ-time and settled destination words are retained."]),
        source_snapshot=snapshot,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
    )
    rom = (out / "a500-timing-rom.bin").read_bytes()
    kernel = (out / "rom_kernel.bin").read_bytes()
    rom_offset = 0x10000 + (0xff7900 - 0xf90000)
    kernel_offset = 0x20000 + (0xff7900 - 0xfb0000)
    loop_bytes = len(kernel[kernel_offset:kernel_offset + 0x40])
    if not loop_bytes or rom[rom_offset:rom_offset + loop_bytes] != kernel[kernel_offset:kernel_offset + loop_bytes]:
        raise ValueError("Raw ROM FF7900 CPU loop does not match rom_kernel.bin")
    if unrolled:
        for address, size, label in ((0xff7a00, 512 * 2 + 2, "quiet"),
                                     (0xff7e10, 256 * 6 + 2, "chip-read")):
            raw_offset = 0x10000 + (address - 0xf90000)
            kernel_offset = 0x20000 + (address - 0xfb0000)
            if rom[raw_offset:raw_offset + size] != kernel[kernel_offset:kernel_offset + size]:
                raise ValueError(f"Raw ROM {address:#x} unrolled {label} block does not match rom_kernel.bin")
    if cpu_launch:
        address, size = 0xffc000, CPU_LAUNCH_STUB_SIZE
        manifest["copper_wait"]["observer"]["cpu_launch_stub_size_bytes"] = size
        raw_offset = 0x10000 + (address - 0xf90000)
        kernel_offset = 0x20000 + (address - 0xfb0000)
        if rom[raw_offset:raw_offset + size] != kernel[kernel_offset:kernel_offset + size]:
            raise ValueError("Raw ROM FFC000 CPU-launch block does not match rom_kernel.bin")
    if finish_sweep:
        address, size = 0xffc100, CPU_FINISH_SWEEP_STUB_SIZE
        manifest["copper_wait"]["observer"]["cpu_launch_stub_slot_bytes"] = size
        raw_offset = 0x10000 + (address - 0xf90000)
        kernel_offset = 0x20000 + (address - 0xfb0000)
        if rom[raw_offset:raw_offset + size] != kernel[kernel_offset:kernel_offset + size]:
            raise ValueError("Raw ROM FFC100 CPU finish-sweep block does not match rom_kernel.bin")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vasm", default="vasmm68k_mot")
    parser.add_argument("--wsl", action="store_true")
    parser.add_argument("--out", type=Path, required=True,
                        help="new directory receiving the immutable ROM build archive")
    parser.add_argument("--unrolled", action="store_true",
                        help="set variant bit 3 and use fixed NOP/read sequences without DBRA")
    parser.add_argument("--no-blit", action="store_true",
                        help="set variant bit 4; replace Copper BLTSIZE with a two-word NOOP")
    parser.add_argument("--cpu-launch", action="store_true",
                        help="require --unrolled; CPU launches the blit while Copper waits BFD-clear")
    parser.add_argument("--finish-sweep", action="store_true",
                        help="require --unrolled; sweep 1/4/8/16-word CPU-launch blits and 0..7 NOP pads")
    args = parser.parse_args(argv)
    build(args.vasm, args.wsl, args.out, unrolled=args.unrolled, no_blit=args.no_blit,
          cpu_launch=args.cpu_launch, finish_sweep=args.finish_sweep)
    return 0


if __name__ == "__main__":
    sys.exit(main())

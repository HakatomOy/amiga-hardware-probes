#!/usr/bin/env python3
"""Build an immutable 512 KiB continuous custom-register address probe ROM."""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src/rom/scope_address.asm"
BOOT = ROOT / "src/rom/boot.asm"
EXPECTED_OFFSETS = (0x002, 0x004, 0x008, 0x010, 0x020, 0x040, 0x080, 0x100)
ROM_BYTES = 512 * 1024


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def wsl_path(path):
    path = Path(path).resolve()
    if path.drive:
        return "/mnt/" + path.drive[0].lower() + path.as_posix()[2:]
    return path.as_posix()


def windows_path(value):
    """Resolve a /mnt/<drive>/... vasm path for hashing on Windows."""
    text = str(value)
    if len(text) > 6 and text.startswith("/mnt/") and text[5].isalpha() and text[6] == "/":
        return Path(text[5].upper() + ":/" + text[7:])
    return Path(text).resolve()


def build(vasm, out):
    out = Path(out).resolve()
    if out.exists():
        raise FileExistsError(f"output archive already exists: {out}")
    if not out.parent.is_dir():
        raise FileNotFoundError(f"output parent does not exist: {out.parent}")

    assembler = str(vasm)
    assembler_file = windows_path(assembler)
    if not assembler_file.is_file():
        raise FileNotFoundError(f"vasm executable not found for hash: {assembler_file}")

    with tempfile.TemporaryDirectory(prefix="scope-address-", dir=out.parent) as temp:
        stage = Path(temp)
        payload_path = stage / "experiment.bin"
        layout_path = stage / "rom_layout.i"
        raw_path = stage / "scope-address-rom.bin"
        payload_path.write_bytes(SOURCE.read_bytes())
        (stage / "payload.asm").write_bytes(SOURCE.read_bytes())

        command = ["wsl", "-d", "Ubuntu-24.04", "--exec", assembler,
                   "-m68000", "-no-opt", "-Fbin", "-DCONFIG_ROM_KB=512",
                   "-I", wsl_path(stage), "-I", wsl_path(ROOT / "src/rom"),
                   wsl_path(SOURCE), "-o", wsl_path(payload_path)]
        subprocess.run(command, cwd=ROOT, check=True)
        payload = payload_path.read_bytes()
        payload += b"\0" * (-len(payload) % 4)
        payload_path.write_bytes(payload)
        if not payload or len(payload) >= 0x20000:
            raise ValueError("payload must fit below $20000 and contain at least one instruction")

        layout_path.write_text(f"TRIAL_COUNT equ 0\nPAYLOAD_BYTES equ {len(payload)}\n",
                               encoding="ascii")
        command = ["wsl", "-d", "Ubuntu-24.04", "--exec", assembler,
                   "-m68000", "-no-opt", "-Fbin", "-DCONFIG_ROM_KB=512",
                   "-I", wsl_path(stage), "-I", wsl_path(ROOT / "src/rom"),
                   wsl_path(BOOT), "-o", wsl_path(raw_path)]
        subprocess.run(command, cwd=ROOT, check=True)
        rom = raw_path.read_bytes()
        if len(rom) != ROM_BYTES:
            raise ValueError(f"boot ROM is {len(rom)} bytes, expected {ROM_BYTES}")
        if rom[-16:] != bytes.fromhex("00180019001a001b001c001d001e001f"):
            raise ValueError("boot ROM interrupt acknowledge vector tail is invalid")
        if payload not in rom:
            raise ValueError("assembled payload was not embedded in boot ROM")

        out.mkdir()
        (out / "scope-address-rom.bin").write_bytes(rom)
        swapped = bytearray(rom)
        swapped[0::2], swapped[1::2] = rom[1::2], rom[0::2]
        (out / "scope-address-rom-onerom.bin").write_bytes(swapped)
        source_snapshot = out / "source_snapshot"
        source_snapshot.mkdir()
        # rom_layout.i is generated from this build's padded payload length and
        # is consumed by boot.asm when embedding it. Snapshot it alongside the
        # authored inputs so the archive is self-contained.
        sources = ((Path(__file__).resolve(), "tools/build_bus_address_rom.py"),
                   (SOURCE, "src/rom/scope_address.asm"),
                   (BOOT, "src/rom/boot.asm"),
                   (layout_path, "generated/rom_layout.i"))
        input_hashes = {}
        for source, relative_name in sources:
            relative = Path(relative_name)
            destination = source_snapshot / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            destination.write_bytes(data)
            input_hashes[relative.as_posix()] = sha256(data)
        manifest = {
            "suite": "scope_address",
            "mode": "continuous_diagnostic",
            "trial_count": 0,
            "payload_bytes": len(payload),
            "expected_order": [f"0x{offset:03x}" for offset in EXPECTED_OFFSETS],
            "reads_per_loop": len(EXPECTED_OFFSETS),
            "nop_padding_after_each_read": 3,
            "dma_disabled": True,
            "interrupts_masked": True,
            "bplcon0_zero": True,
            "rom_bytes": ROM_BYTES,
            "rom_sha256": sha256(rom),
            "onerom_sha256": sha256(swapped),
            "vasm_path": str(assembler_file),
            "vasm_sha256": sha256(assembler_file.read_bytes()),
            "inputs": input_hashes,
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                            encoding="utf-8")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vasm", default="/mnt/c/Users/seppo/amiga/amiga-hardware-probes/.tools/vasm/vasmm68k_mot")
    parser.add_argument("--out", type=Path, required=True,
                        help="new directory receiving the immutable ROM archive")
    args = parser.parse_args(argv)
    manifest = build(args.vasm, args.out)
    print(f"Built {manifest['rom_bytes']} byte continuous address probe ROM")
    print(f"Archive: {Path(args.out).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


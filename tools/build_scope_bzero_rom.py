#!/usr/bin/env python3
"""Build an immutable 512 KiB continuous line-mode BZERO diagnostic ROM."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src/rom/scope_bzero.asm"
BOOT = ROOT / "src/rom/boot.asm"
ROM_BYTES = 512 * 1024
C_PATTERNS = {"zero": 0x0000, "ones": 0xffff, "cold_bit0": 0xfffe,
              "cold_bit14": 0xbfff, "cold_bit8": 0xfeff}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def wsl_path(path):
    path = Path(path).resolve()
    if path.drive:
        return "/mnt/" + path.drive[0].lower() + path.as_posix()[2:]
    return path.as_posix()


def windows_path(value):
    text = str(value)
    if len(text) > 6 and text.startswith("/mnt/") and text[5].isalpha() and text[6] == "/":
        return Path(text[5].upper() + ":/" + text[7:])
    return Path(text).resolve()


def parse_hex_word(value):
    try:
        word = int(value[2:] if value.lower().startswith("0x") else value, 16)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use a hexadecimal word from 0x0000 to 0xffff") from exc
    if not 0 <= word <= 0xffff:
        raise argparse.ArgumentTypeError("hex word must be from 0x0000 to 0xffff")
    return word


def parse_hex_byte(value):
    try:
        byte = int(value[2:] if value.lower().startswith("0x") else value, 16)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use a hexadecimal byte from 0x00 to 0xff") from exc
    if not 0 <= byte <= 0xff:
        raise argparse.ArgumentTypeError("hex byte must be from 0x00 to 0xff")
    return byte


def build(vasm, out, c_pattern="zero", b_data=0, a_data=0x8000,
          ashift=0, bshift=0, minterm=0xca, useb=False, pixels=2):
    out = Path(out).resolve()
    if out.exists():
        raise FileExistsError(f"output archive already exists: {out}")
    if not out.parent.is_dir():
        raise FileNotFoundError(f"output parent does not exist: {out.parent}")
    if c_pattern not in C_PATTERNS:
        raise ValueError(f"c_pattern must be one of: {', '.join(C_PATTERNS)}")
    if not isinstance(b_data, int) or not 0 <= b_data <= 0xffff:
        raise ValueError("b_data must be an integer in 0..65535")
    if not isinstance(a_data, int) or not 0 <= a_data <= 0xffff:
        raise ValueError("a_data must be an integer in 0..65535")
    if not isinstance(ashift, int) or not 0 <= ashift <= 15:
        raise ValueError("ashift must be in 0..15")
    if not isinstance(bshift, int) or not 0 <= bshift <= 15:
        raise ValueError("bshift must be in 0..15")
    if not isinstance(minterm, int) or not 0 <= minterm <= 0xff:
        raise ValueError("minterm must be in 0..255")
    if pixels not in (1, 2):
        raise ValueError("pixels must be 1 or 2")
    assembler = str(vasm)
    assembler_file = windows_path(assembler)
    if not assembler_file.is_file():
        raise FileNotFoundError(f"vasm executable not found for hash: {assembler_file}")

    c_first = C_PATTERNS[c_pattern]
    bltcon0 = (ashift << 12) | 0x0b00 | (0x0400 if useb else 0) | minterm
    bltcon1 = (bshift << 12) | 1
    bltsize = (pixels << 6) | 2
    with tempfile.TemporaryDirectory(prefix="scope-bzero-", dir=out.parent) as temp:
        stage = Path(temp)
        payload_path = stage / "experiment.bin"
        layout_path = stage / "rom_layout.i"
        config_path = stage / "bzero_config.i"
        raw_path = stage / "scope-bzero-rom.bin"
        config_path.write_text(
            f"BZERO_C_FIRST equ ${c_first:04x}\n"
            f"BZERO_B_DATA equ ${b_data:04x}\n"
            f"BZERO_A_DATA equ ${a_data:04x}\n"
            f"BZERO_BLTCON0 equ ${bltcon0:04x}\n"
            f"BZERO_BLTCON1 equ ${bltcon1:04x}\n"
            f"BZERO_BLTSIZE equ ${bltsize:04x}\n",
            encoding="ascii")

        common = ["wsl", "-d", "Ubuntu-24.04", "--exec", assembler,
                  "-m68000", "-no-opt", "-Fbin", "-DCONFIG_ROM_KB=512",
                  "-I", wsl_path(stage), "-I", wsl_path(ROOT / "src/rom")]
        subprocess.run(common + [wsl_path(SOURCE), "-o", wsl_path(payload_path)],
                       cwd=ROOT, check=True)
        payload = payload_path.read_bytes()
        payload += b"\0" * (-len(payload) % 4)
        payload_path.write_bytes(payload)
        if not payload or len(payload) >= 0x20000:
            raise ValueError("payload must fit below $20000 and contain instructions")
        layout_path.write_text(f"TRIAL_COUNT equ 0\nPAYLOAD_BYTES equ {len(payload)}\n",
                               encoding="ascii")
        subprocess.run(common + [wsl_path(BOOT), "-o", wsl_path(raw_path)],
                       cwd=ROOT, check=True)
        rom = raw_path.read_bytes()
        if len(rom) != ROM_BYTES:
            raise ValueError(f"boot ROM is {len(rom)} bytes, expected {ROM_BYTES}")
        if rom[-16:] != bytes.fromhex("00180019001a001b001c001d001e001f"):
            raise ValueError("boot ROM interrupt acknowledge vector tail is invalid")
        if payload not in rom:
            raise ValueError("assembled payload was not embedded in boot ROM")

        out.mkdir()
        (out / "scope-bzero-rom.bin").write_bytes(rom)
        swapped = bytearray(rom)
        swapped[0::2], swapped[1::2] = rom[1::2], rom[0::2]
        (out / "scope-bzero-rom-onerom.bin").write_bytes(swapped)
        snapshot = out / "source_snapshot"
        snapshot.mkdir()
        sources = ((Path(__file__).resolve(), "tools/build_scope_bzero_rom.py"),
                   (SOURCE, "src/rom/scope_bzero.asm"),
                   (BOOT, "src/rom/boot.asm"),
                   (layout_path, "generated/rom_layout.i"),
                   (config_path, "generated/bzero_config.i"))
        input_hashes = {}
        for source, relative_name in sources:
            destination = snapshot / relative_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            destination.write_bytes(data)
            input_hashes[relative_name] = sha256(data)
        manifest = {
            "suite": "scope_bzero",
            "mode": "continuous_diagnostic",
            "trial_count": 0,
            "payload_bytes": len(payload),
            "c_pattern": c_pattern,
            "c_first_word": f"0x{c_first:04x}",
            "b_data_word": f"0x{b_data:04x}",
            "a_data_word": f"0x{a_data:04x}",
            "b_channel_enabled": False,
            "ashift": ashift,
            "bshift": bshift,
            "minterm": f"0x{minterm:02x}",
            "useb": useb,
            "pixels": pixels,
            "bltcon0": f"0x{bltcon0:04x}",
            "bltcon1": f"0x{bltcon1:04x}",
            "bltsize": f"0x{bltsize:04x}",
            "dma_control_before_each_launch": "0x8240",
            "status_reads": ["DMACONR->$D%d" % i for i in range(8)],
            "status_reads_are_adjacent": True,
            "revision": 5,
            "supersedes_archives": [
                "scope_bzero_c0000_b0000_v4_20261016",
                "scope_bzero_c0000_bffff_v4_20261016",
                "scope_bzero_cffff_b0000_v4_20261016"],
            "post_sample_busy_wait": ["wait BBUSY clear"],
            "busy_set_wait_omitted_because_samples_may_outlast_blit": True,
            "line_setup": {
                "a_data": f"0x{a_data:04x}", "b_data": f"0x{b_data:04x}", "c_data": "0x0000",
                "c_words": [f"0x{c_first:04x}", "0x0000"],
                "a_mod": -280, "b_mod": 0, "c_mod": 80, "d_mod": 80,
                "a_pointer": -80, "b_pointer": "0x16000",
                "c_pointer": "0x11000", "d_pointer": "0x10000",
                "destination_words_cleared_each_iteration": 2,
            },
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
    parser.add_argument("--c-pattern", choices=tuple(C_PATTERNS), default="zero",
                        help="first C source word used to control BZERO")
    parser.add_argument("--b-data", type=parse_hex_word, default=0,
                        metavar="HEX", help="literal BLTBDAT word in hex; USEB remains separately selectable")
    parser.add_argument("--a-data", type=parse_hex_word, default=0x8000,
                        metavar="HEX", help="literal BLTADAT word in hex")
    parser.add_argument("--ashift", type=int, choices=range(16), default=0)
    parser.add_argument("--bshift", type=int, choices=range(16), default=0)
    parser.add_argument("--minterm", type=parse_hex_byte, default=0xca,
                        metavar="HEX", help="literal LF byte in hex")
    parser.add_argument("--useb", action="store_true", help="enable USEB in BLTCON0")
    parser.add_argument("--pixels", type=int, choices=(1, 2), default=2)
    args = parser.parse_args(argv)
    manifest = build(args.vasm, args.out, args.c_pattern, args.b_data, args.a_data,
                     args.ashift, args.bshift, args.minterm, args.useb, args.pixels)
    print(f"Built {manifest['rom_bytes']} byte continuous BZERO probe ROM")
    print(f"C first word: {manifest['c_first_word']}; A data: {manifest['a_data_word']}; "
          f"B data: {manifest['b_data_word']}; controls: "
          f"BLTCON0={manifest['bltcon0']} BLTCON1={manifest['bltcon1']} "
          f"BLTSIZE={manifest['bltsize']}; archive: {Path(args.out).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

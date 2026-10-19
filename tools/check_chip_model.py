#!/usr/bin/env python3
"""Run Copperline's real chip module tests without rebuilding the full emulator."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module", choices=("cia", "blitter", "copper"))
    parser.add_argument("filter", nargs="?", default="")
    parser.add_argument("--copperline", type=Path, default=ROOT.parent / "Copperline")
    parser.add_argument("--out", type=Path, required=True, help="artifact root; each run gets a unique directory")
    args = parser.parse_args()
    copperline = args.copperline.resolve()
    spec = importlib.util.spec_from_file_location("cargo_report", copperline / "tools/cargo_report.py")
    wrapper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wrapper)
    args.out.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix=args.module + "-model-", dir=args.out.resolve()))
    source = folder / "src"
    source.mkdir()
    (folder / "Cargo.toml").write_text('''[package]
name = "copperline-chip-model-check"
version = "0.0.0"
edition = "2021"
[workspace]
[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
bincode = "1.3"
''')
    module_path = json.dumps(str(copperline / f"src/chipset/{args.module}.rs"))
    agnus = (copperline / "src/chipset/agnus.rs").read_text()
    pal_lines = re.search(r"pub const PAL_LINES: u32 = (\d+);", agnus).group(1)
    line_clocks = re.search(r"pub const COLORCLOCKS_PER_LINE: u32 = (\d+);", agnus).group(1)
    support = ""
    if args.module in ("cia", "copper"):
        support = f"pub mod agnus {{ pub const PAL_LINES: u32 = {pal_lines}; pub const COLORCLOCKS_PER_LINE: u32 = {line_clocks}; }}\n"
        support += "pub mod chipset { pub use crate::agnus; }\n"
    if args.module == "cia":
        support += "pub mod uss { pub fn be16(b: &[u8], at: usize) -> u16 { u16::from_be_bytes([b[at], b[at+1]]) } }\n"
    (source / "lib.rs").write_text('#![allow(dead_code)]\n' + support
        + f"#[path = {module_path}]\npub mod {args.module};\n")
    target = ROOT / ".tools/cia-model-target"
    command = wrapper.cargo_command(["test", "--offline", "--manifest-path", str(folder / "Cargo.toml"),
                                     "--target-dir", str(target), args.filter])
    status, report, logs = wrapper.execute(command, folder / "logs")
    print(report)
    print(f"Model-only evidence: {folder}; bus/CPU integration is not covered")
    return status


if __name__ == "__main__":
    raise SystemExit(main())

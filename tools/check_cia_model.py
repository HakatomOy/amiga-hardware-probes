#!/usr/bin/env python3
"""Run Copperline's real CIA module tests without rebuilding the full emulator."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filter", nargs="?", default="")
    parser.add_argument("--copperline", type=Path, default=ROOT.parent / "Copperline")
    parser.add_argument("--out", type=Path, required=True, help="artifact root; each run gets a unique directory")
    args = parser.parse_args()
    copperline = args.copperline.resolve()
    spec = importlib.util.spec_from_file_location("cargo_report", copperline / "tools/cargo_report.py")
    wrapper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wrapper)
    args.out.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="cia-model-", dir=args.out.resolve()))
    source = folder / "src"
    source.mkdir()
    (folder / "Cargo.toml").write_text('''[package]
name = "copperline-cia-model-check"
version = "0.0.0"
edition = "2021"
[workspace]
[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
''')
    # The module only refers outside itself to USS's big-endian word decoder
    # and PAL_LINES in a TOD test. These stubs deliberately exclude bus/CPU
    # integration; the full Copperline suite remains required for acceptance.
    cia_path = json.dumps(str(copperline / "src/chipset/cia.rs"))
    pal_lines = re.search(r"pub const PAL_LINES: u32 = (\d+);", (copperline / "src/chipset/agnus.rs").read_text()).group(1)
    (source / "lib.rs").write_text('''#![allow(dead_code)]
pub mod uss {
    pub fn be16(bytes: &[u8], at: usize) -> u16 {
        u16::from_be_bytes([bytes[at], bytes[at + 1]])
    }
}
''' + f"pub mod chipset {{ pub mod agnus {{ pub const PAL_LINES: u32 = {pal_lines}; }} }}\n"
        + f"#[path = {cia_path}]\npub mod cia;\n")
    target = ROOT / ".tools/cia-model-target"
    command = wrapper.cargo_command(["test", "--offline", "--manifest-path", str(folder / "Cargo.toml"),
                                     "--target-dir", str(target), args.filter])
    status, report, logs = wrapper.execute(command, folder / "logs")
    print(report)
    print(f"Model-only evidence: {folder}; bus/CPU integration is not covered")
    return status


if __name__ == "__main__":
    raise SystemExit(main())

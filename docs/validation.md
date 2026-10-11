# Local validation — 2026-10-11

This is emulator/tooling validation. No real A500 or FlashFloppy capture has yet
been run. The disk is ready for that first hardware run; these emulator results
must not be used as hardware reference values.

## Build and host tools

- Python 3.11 on Windows, Ubuntu-24.04 WSL GCC/make.
- vasm mirror revision `a13e7e728a3dd5a9ba468bf479119e0bc23e70fd`
  (vasm 2.0f, Motorola syntax, `-m68000 -no-opt`).
- `python tools/setup_vasm.py --wsl`: passed with the existing pinned checkout.
- `python -m unittest discover -s tests -v`: 9 tests passed.
- Python byte compilation of all build/extraction/runner/setup/test tools: passed.
- Two consecutive builds: byte-identical ADFs, no assembler warnings.
- Program: 14866 bytes, within the 32768-byte loader reservation.
- Fresh ADF SHA-256:
  `5f07bf93b2245c89df14d39fc4215f070278f51c9f2fad7589f2465d2aaec95a`.
- Test source fingerprint:
  `727b85d10a82340679d2570985f587193a9439c4500f676300afcb721c719df1`.

## Copperline execution

Used the existing release executable at `../Copperline/target/release/copperline.exe`;
it was not rebuilt or modified for this project. Executable SHA-256:
`b0db4e0cefe692d69911ae26ab36abdbd12f07ee85e9042ce071e1ee81ad9363`.
Booted the user's byte-swapped Kickstart 1.3 rev 34.5 ROM, recognized by Copperline.
The guest's Exec library reported version 34, revision 2; the library revision
is distinct from the ROM release revision.

Each run used `run_copperline.py`, a new image copy, an explicit writable DF0,
68000 interpreter (`--no-jit`), OCS, no fast RAM, and 45 emulated seconds.
Only result sectors were modified in all successful writable runs.

| Run | Outcome |
| --- | --- |
| PAL, 512 KB chip + 512 KB slow, default IRQ delay | 768 records, zero timeouts; saved and readback verified |
| Same configuration, second run | Same outcome; **entire captured ADF byte-identical** |
| PAL, 512 KB chip, no slow RAM | 768 records, zero timeouts; saved and readback verified |
| NTSC, 512 KB chip + 512 KB slow | 768 records, zero timeouts; saved and readback verified |
| PAL with diagnostic `--irq-latency 2` | 768 records, zero timeouts; **637/768 records differ** from default |
| PAL with write-protected image | Original ADF unchanged; red error screenshot visually verified |

The default green success screen was visually inspected. CLI extraction produced
both JSON and CSV; repeated-run and diagnostic-delay comparisons produced JSON
reports. Source fingerprints matched the build manifest. Diagnostic sensitivity
includes changes in exception PCs, SR/D0, entry beam positions and some subsequent
launch phases; it does not establish which emulator delay is physically correct.

Raw captures, screenshots, logs, ROMs and assembler build products are local,
ignored artifacts, not tracked in Git. To reproduce these checks, use the README's
runner command with distinct `--out` directories and respectively `--slow 0`,
`--video NTSC`, `--irq-latency 2`, or `--write-protected`. Compare two default runs
with `results.py compare`, then compare their complete ADF bytes.

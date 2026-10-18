# Reusable capture comparison

Run `compare_captures.py` before reading full captures into an agent context.
It accepts checksum-protected RBCP `results.bin`, extracted `results.json`, or
capture directories (including hardware directories with a `capture/` child).
It compares the six-word descriptor and every raw observation, starting with
CIA/interrupt kind51 and supporting the common RBCP record layout across kinds.
It does not infer that a field means CIA ticks for kinds that reuse that field.

```powershell
python compare_captures.py --hardware captures/rom-amiga500-cia-cpu-irq-kind51-review3-run1 --copperline captures/rom-copperline-cia-cpu-irq-kind51-before-review3 --winuae captures/rom-winuae-cia-cpu-irq-kind51-review3 --out captures/comparison-summary.json
python compare_captures.py --hardware captures/rom-amiga500-cia-cpu-irq-kind51-review3-run1 --copperline captures/rom-copperline-cia-cpu-irq-kind51-before-review3 --case 51:0:0:0:0:0 --window 3 --out captures/comparison-case.json
```

The first command prints total/match/mismatch/missing/invalid counts, launch
eligibility, at most three leading raw and three exact-launch patterns, a detail retrieval hint and the
report path. Read `counts`, `first_divergence`, and relevant `patterns` from
the JSON, then request a representative case with the second command. Pattern
groups share status, differing fields and their deltas, kind, target and variant; at most three
representative IDs are stored per group. No full record arrays are copied into
the report. `--case` adds just the selected pair and its differing observations.
Use a separate output path to retain the summary. Repeat with the second hardware
run before attributing a difference to an emulator. No hardware is flashed by
this tool and it does not start an emulator.

Case IDs are `kind:target:variant:phase:delay:repeat`. The union of IDs defines
total; each ID has exactly one outcome. Duplicate IDs and unsuccessful/malformed
observations are invalid; IDs missing from either side are missing. These take
precedence over ordinary mismatches. Extra candidate IDs are visible too.
The capture's declared-count delta is reported separately so JSON record removal
cannot look complete. Nonzero declared-count deltas force exit 1 even when the
remaining rows match. Union counts cannot identify a descriptor absent from
every input without an external expected matrix/manifest. Invalid capture containers, source disagreement, damaged
binary checksums, and disagreement between JSON and sibling binary fail with
exit 2. Exit 1 means observed mismatches/missing/invalid cases; exit 0 means all
compared observations match. JSON-only inputs are explicitly marked unverified;
their metadata hash cannot authenticate edited observations. Source IDs identify
the probe build, not hardware equivalence. Reports include resolved input paths,
file SHA-256, original metadata, and trace paths.

All fields retain their wire values. VHPOSR fields are packed register words;
their subtraction is **not elapsed CCK**. PC offsets are bytes. Other raw words
are explicitly kind-dependent, including overloaded `launch_ref`, `counter`,
`icr` and `aux`. For kind51, `counter` is D1 at IRQ, `icr` is A1 low at IRQ,
`end_ref` is selected CIA ICR, and `aux` is event count. Both launch samples
are compared and mismatches remain visible. There is no shifted alignment,
phase filtering, wrap correction, interpolation, or conversion into inferred
latency. First observation divergence uses numeric descriptor order and wire
field order; it is not a chronological event claim. Identical starts still do
not prove identical internal CIA E-clock history.

For future event-trace adapters, place `events.json` next to the input file:

```json
{"unit":"CCK","cases":{"51:0:0:0:0:0":[{"time":120,"event":"cia_irq","level":2},{"time":122,"event":"cpu_sample","level":2}]}}
```

Timestamps must be ordered integers in an explicit common unit. Each event is
compared exactly, including extra keys. `--case --window N` returns the first
different event index and N events before/after from each side, with no alignment.
Missing paired traces or different units are reported as unavailable. These
trace differences also count as mismatches even if raw samples match. Current archived kind51 captures contain software samples,
not event traces, so their trace result is explicitly unavailable. Adapters for
other record containers should preserve source identity, exact descriptor keys,
raw observations and explicit units; do not silently synthesize phase matches.

To collect a fresh WinUAE reference, use the existing `run_winuae_rom.py` runner
with `--binary "C:/Program Files/WinUAE/winuae64_603.exe"` (the option names the
executable), an identical probe ROM and a fresh output directory; consult
`python run_winuae_rom.py --help` for its required ROM/configuration arguments.
Hardware capture and experiment build procedures remain in `rom-measurement.md`.

## Focused accuracy workflow

Start from `accuracy-investigation-2026-10-18.md` for confirmed findings and the
next unresolved question. Checksum-protected original measurement packets are
versioned under `../references/`; their manifests identify the ROM, hardware,
capture method and repeatability. Private logs and generated ROMs remain local.

```powershell
python tools/check_cia_model.py --out captures/NEW_RUN/model
python tools/replay_accuracy.py --binary ../Copperline/target/ci/copperline.exe --config MACHINE.toml --out captures/NEW_RUN/replay --suite cia-irq --suite irq-focus --suite divider-irq
```

The model harness compiles the production CIA source with minimal external
support definitions; it does not replace the full emulator regression suite.
The replay batch snapshots executable/configuration, saves hashes and full logs,
and emits bounded summaries. Each destination must be new. Omit `--suite` to
include the bus neighbors too; their immutable ROM archives must exist locally.

`compare_copper_busy.py` handles the kind50 layout explicitly. The ordinary
RBCP `status` and PC slots contain DMACONR samples in that experiment, so generic
status validation is inappropriate. It compares only identical descriptors and
both observed beam brackets; gate and settled-data guards remain mandatory.
`tools/compare_custom_sampling.py --before BEFORE_BATCH --after AFTER_BATCH
--out REPORT` assesses common cohorts across the Copper pilot, CPU handoff and
normal/fill BZERO references. Inspect repaired and regressed cases separately;
a lower aggregate mismatch count alone is insufficient evidence for a fix.

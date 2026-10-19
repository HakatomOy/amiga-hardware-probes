# Compact hardware investigation workflow

`tools/experiment.py` executes mechanical work and returns a bounded report.
Sol designs the experiment, interprets evidence and chooses the emulator change.
No agent needs to read thousands of matching records. All paths below are
relative to this repository, including when invoked from another directory;
command `cwd` defaults to the repository root. Python requires3.9+.

## One batch, explicit contract

Start from `experiments/workflows/serial-buffer.json`. It is a runnable replay
of existing measurements, not a request to repeat hardware experiments:

```powershell
python tools/experiment.py run experiments/workflows/serial-buffer.json --out captures/serial-review-01
```

The example uses local immutable ROM archives, the current Copperline CI binary
and the explicit A500 configuration. Adjust local paths when necessary. Missing
assets fail clearly; the tool never downloads ROMs or rebuilds an old pinned ROM
from potentially changed sources. `--through comparison`, `focused` or `neighbor`
stops at that boundary for investigation; partial runs cannot be accepted.

Every manifest declares:

- `hypothesis`, `competitor`, `test`, at least two `outcomes` and their implications,
  `next_question`, and the current `investigation` JSON record.
- `binary`, `romdir`, `config`, optional pinned `rom_sha256`; optional `build`
  argument-array commands execute before the ROM and executable are snapshotted.
- `capture.minimum_seconds`, `expected_cases`, allowed statuses, optional
  `seconds` and wall `timeout_seconds`. The runner selects the larger duration.
  `validator` optionally reuses the existing `serial`, `irq` or `handoff` validator.
- Saved `references` and optional pre-fix `baseline` capture. Each reference must
  match ROM/source/result hashes and contain hardware, method, repeatability and
  verified restoration metadata. Packets must pass checksum, completion, exact
  descriptor order/count, uniqueness and status checks before comparison.
- `comparison.measurements` and `qualification`: each field has a `field`, `unit`
  and `meaning`, optionally `name`, `mask` and `shift`. `alignment` must be `exact`.
  Qualify on all timing brackets needed for a valid comparison. Descriptor repeat
  is pooled only when descriptors and qualification values otherwise agree.

The first six RBCP fields identify a case. Field masks are applied after right
shift; default mask is32 bits. Measurement `pattern: "delta"` groups equal numeric
differences; the default `values` groups exact expected/actual pairs. Neither
operation shifts timestamps or changes qualification. Choose a dedicated existing
comparator when a probe requires additional domain rules; generic field extraction
does not prove that a measurement isolates an electrical event.
Declare measurements in observation order for a meaningful first divergent
field. Use numeric deltas only for linear quantities in their declared units;
packed raster words and wrapping counters are not automatically converted to CCK.

`max_excluded` and `max_unstable` default to zero. Declare justified budgets before
running, never raise them merely to obtain a pass. Conflicting qualified hardware
observations are excluded, not averaged. Malformed captures fail the batch rather
than entering match counts. For new probes, calibrate a conservative minimum
duration once and record it; a complete header/case check is still mandatory.

## Read changes, retrieve evidence selectively

The final response includes counts, repairs, regressions, changed/unchanged
differences, exclusions, and up to three new mismatch patterns with representative
IDs and shared conditions. Full `comparison.json` and `cases.json` remain under
the run directory. Qualification changes cannot be credited as automatic repairs.
Regressions, missing cases and lost qualification stop the validation ladder.

```powershell
python tools/experiment.py detail captures/serial-review-01 --case 63,0,1,0,31,0 --window 6
```

Optional `traces` declares `hardware`, `candidate` JSONL paths and a time `unit`.
Each event is an object with `case: [six integers]`, an absolute `time`, an `event`
name and optional details. Detail reads only the requested case, identifies the
first unequal event (including unequal time or a missing event), and returns a
bounded surrounding window. No trace alignment, scaling or event dropping occurs.
Without event traces, full snapshot fields remain available; they are not
misrepresented as pin-level traces. `--window` is bounded to32 events each side.

For unchanged neighboring suites, use a strict packet gate after replay:

```powershell
python tools/experiment.py packets --before captures/ACCEPTED --after captures/CANDIDATE --suite cia-output --suite irq-stages
```

It reports changed cases and representative fields, returns nonzero on changed
or missing suites, and rejects source mismatches. This checks preservation, not
hardware accuracy. Decoded records are compared exactly; volatile header values
are not credited as measurement changes. Favorable changes still require explicit hardware comparison
and review; a replay command exiting successfully does not establish no regression.

## Validation ladder and artifact reuse

`validation` commands declare `tier: focused`, `neighbor` or `broad`, in that
order. A failed command stops subsequent tiers. The example runs mutation tests,
replays CIA/IRQ neighbors, checks packet preservation, then runs core tests,
strict Clippy and formatting. Keep known ignored/window-test exclusions explicit.
Run broader validation once after a candidate passes the earlier tiers; do not
recompile Copperline because only instructions or comparison scripts changed.

Optional command caching requires `cache: true`, explicit nonempty `inputs`
glob patterns and generated `outputs` file paths. For example:

```json
{
  "name": "rom-build",
  "argv": ["{python}", "build_serial_buffer_rom.py", "--wsl", "--vasm", "/mnt/c/PATH/vasmm68k_mot", "--out", "build/NEW-ROM"],
  "cache": true,
  "inputs": ["build*.py", "src/rom/**/*.asm", "src/rom/**/*.i", ".tools/vasm/vasmm68k_mot"],
  "outputs": ["build/NEW-ROM/manifest.json", "build/NEW-ROM/a500-timing-rom.bin"]
}
```

Use this for a **new** ROM, not the example's pinned historical capture. Declare
every dependency affecting a build, including generated includes, embedded assets,
build scripts, locks, toolchain/configuration and assembler/compiler identities.
An incomplete cache declaration is unsafe; leave caching off when uncertain.
The command, environment hash, launcher/script hashes, input hashes and output
hashes must all agree before reuse. Modified/missing outputs invalidate reuse;
inputs changing during a command cannot seed its cache. Exclude documentation
from executable fingerprints unless it actually affects generated code.

The opt-in `reuse_preflight` caches deterministic emulator packets by binary,
ROM, source, configuration, duration, capture/decoder tools and `replay_inputs`
hashes. Declare external assets read through configuration in `replay_inputs`;
disable reuse if a run depends on uncontrolled external state. Cached packets
are revalidated and link their original provenance. Hardware is never implicitly
recaptured or replaced by an emulator cache. Build cache files live in ignored
`captures/.experiment-cache/`; deleting that cache only forces fresh work.

## Logs and completion events

Commands run without a shell. Each command's complete stdout and stderr, actual
exit status, duration and provenance are written before any output reaches the
model. Failures expose a bounded excerpt anchored at the first error, with full
log paths; arbitrary log tails are not the default. Cargo commands must invoke
Copperline's compact Cargo wrapper to retain structured compiler/test diagnostics.

Default output is one final summary. `--events` emits bounded stage-completion
events; `events.jsonl` and `status.json` also retain them. Submit the entire batch
once, then work independently or wait for completion. Do not poll every few seconds
or resend a full suite summary merely because a command is still running.
`status RUN` retrieves just the latest milestone when a status check is needed.
Unique run directories are required; old captures and logs are never overwritten.

## Hardware only when it resolves uncertainty

```powershell
python tools/experiment.py run experiments/workflows/NEW.json --out captures/NEW --hardware --events
python tools/experiment.py archive captures/NEW --out references/NEW
```

`--hardware` explicitly selects new runs instead of saved references, after a
valid emulator preflight. `hardware` supplies `onerom`, `limitations`, a timeout
and at least two independent `repeats`. The existing OneROM live runner owns
reset, substitution, restoration and readback verification. No flash operation
is introduced. Repeats are pooled by exact qualification; repeatability metadata
reports packet identity and conflicting observations honestly.

`archive` copies only verified result packets and provenance manifests into a
new directory. It refuses overwrite and never copies ROM images, live backups,
control tokens or historical logs. Review and commit these references explicitly.
Do not repeat trustworthy unchanged hardware baselines on every patch. WinUAE
remains corroboration; agreement between emulators cannot overrule valid hardware.

## Decide, record, restart

After comparison, select `patch`, `narrow`, `measure`, `preserve` or `accept`:

```powershell
python tools/experiment.py decide captures/serial-review-01 --action preserve --reason "Buffering repairs hold; pin/flag boundary remains unresolved" --evidence captures/serial-review-01/comparison.json
python tools/experiment.py restart investigations/serial-buffer.json --out captures/serial-restart.json
```

Every decision requires a reason and existing evidence paths. Acceptance also
requires baseline comparison and successful neighboring and broad validation.
Failed, incomplete and stale runs cannot be accepted. Command success is a
mechanical requirement; Sol must still assess timing inference and generalization.

The runner counts repeated identical evidence patterns. After two successive
runs add no evidence, another run requires a revised hypothesis/test or a changed
`smaller_reproducer` identifier. Repeating an unchanged repaired candidate against
the same old baseline does not count as new progress. Failure loops are tracked too.

Maintain `confirmed_facts`, `accepted_commits`, `rejected_hypotheses` with evidence,
`references`, `source_files`, `next_question` and history links in the investigation
JSON. Automatic updates preserve these human findings. Keep chronology and detailed
traces in linked files. Restart packets include the current decision, identities,
validation and bounded knowledge lists; records over8000 characters must be
shortened before export. Start a fresh context at a natural boundary from this
packet and repository instructions, then retrieve only evidence needed next.

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
from potentially changed sources. `--through preflight`, `comparison`, `focused` or `neighbor`
stops at that boundary for investigation; partial runs cannot be accepted.
Preflight-only mode needs no hardware references and does not advance the
investigation decision; use it to establish useful transition coverage first.

Every manifest declares:

- `hypothesis`, `competitor`, `test`, at least two `outcomes` and their implications,
  `next_question`, and the current `investigation` JSON record.
- `binary`, `romdir`, `config`, optional pinned `rom_sha256`; optional `build`
  argument-array commands execute before the ROM and executable are snapshotted.
- `capture.minimum_seconds`, `expected_cases`, allowed statuses, optional
  `seconds` and wall `timeout_seconds`. The runner selects the larger duration.
  `validator` optionally reuses the existing `serial`, `irq`, `handoff` or `bus` validator.
  Kind55 stores an INTREQ observation in the layout's `status` word; its contracts
  declare `status_is_measurement: true` and must use the bus domain validator for
  watchdog, settled-marker, destination and ROM-substitution integrity instead.
  Never infer field meanings or error codes solely from their shared layout names.
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
For edge-discrimination probes, also declare `capture.coverage` extraction rules
with `field`, `unit`, `meaning`, optional mask/shift/descriptor `where`, and
`require_values` (for example `[0, 1]`). Preflight must observe both sides of the
intended transition before hardware starts. A valid packet containing only
uninformative clear samples must not trigger two expensive physical captures.

## Read changes, retrieve evidence selectively

The final response includes counts, repairs, regressions, changed/unchanged
differences, exclusions, and up to three new mismatch patterns with representative
IDs and shared conditions. Full `comparison.json` and `cases.json` remain under
the run directory. Qualification changes cannot be credited as automatic repairs.
Regressions, missing cases and lost qualification stop the validation ladder.
Field-level regressions also stop it: repairing one field while breaking a
previously correct field in an already-mismatching case is not harmless progress.
Reports list both full-case and per-field repairs/regressions.
Nested regression contracts can use `run --binary PATH --config PATH` to bind
their captures to the parent batch's frozen artifacts rather than a mutable
build-output executable. Effective overrides are saved with the run contract.

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

Before opening raw cases, aggregate the selected family mechanically:

```powershell
python tools/experiment.py aggregate captures/RUN --status mismatches --group-by target,variant,phase --fields FIELD_NAME --limit 8
```

Field names refer to declared measurements/qualification names, including their
mask/shift and unit. The report returns counts, bounded value distributions and
representative IDs. It does not infer cycle differences from packed beam words.
This avoids writing a new one-off parser or printing repeated full records when
testing whether differences share an operand, phase or source condition.

For unchanged neighboring suites, use a strict packet gate after replay:

```powershell
python tools/experiment.py packets --before captures/ACCEPTED --after captures/CANDIDATE --suite cia-output --suite irq-stages
```

It reports changed cases and representative fields, returns nonzero on changed
or missing suites, and rejects source mismatches. This checks preservation, not
hardware accuracy. Decoded records are compared exactly; volatile header values
are not credited as measurement changes. Favorable changes still require explicit hardware comparison
and review; a replay command exiting successfully does not establish no regression.
When the same immutable candidate already produced a neighbor batch, add
`--binary PATH --config PATH` to bind reuse to that batch's recorded hashes,
actual executable/configuration snapshots and each suite's invocation identity.
This lets a later broad-validation plan reuse proven neighbors without rerunning
the emulator. Changed identities require fresh replays; do not reuse checks whose
other inputs or interpretation rules changed.

## Validation ladder and artifact reuse

`validation` commands declare `tier: focused`, `neighbor` or `broad`, in that
order. A failed command stops subsequent tiers. The example runs mutation tests,
replays CIA/IRQ neighbors, checks packet preservation, then runs core tests,
strict Clippy and formatting. Keep known ignored/window-test exclusions explicit.
Run broader validation once after a candidate passes the earlier tiers; do not
recompile Copperline because only instructions or comparison scripts changed.

If a nonfunctional cleanup fixes a late check, retry validation without repeating
hardware, emulator replay or already-passing stages:

```powershell
python tools/experiment.py resume captures/RUN --repeat probe-tests
```

Resume verifies frozen binary/ROM/configuration and capture/reference identities,
then runs failed and remaining declared checks. Use `--repeat NAME` for successful
checks whose tool/test inputs changed. Previous failures and logs remain in
`validation_attempts` and distinct retry directories. A regressed comparison,
stale run or changed artifact cannot resume; functional emulator changes require
a new binary and a new run. Do not use resume to reuse checks whose other inputs
changed. Predeclare the full validation ladder even when initially stopping at
`--through neighbor`; resume can then complete broader checks without new captures.

`tools/make_accuracy_regressions.py` generates bus/handoff contracts from the
existing immutable archives, domain field meanings and accepted baseline captures.
It records baseline qualification/exclusion budgets before testing the candidate;
new lost cohorts or field regressions still fail. Generated contracts refuse
overwrite. Use the versioned `regression-*.json` plans for repeated validation.

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
It also counts exact phase cohorts shared by independent hardware runs and the
candidate cases they cover. Zero conflicts in disjoint phase cohorts is not
independent confirmation of those cohorts; within-run descriptor repetitions
remain useful but must be described separately. Do not equate stable measured
values with byte-identical captures when their qualification brackets differ.
Report distinct descriptor combinations covered after qualification as well as
raw row counts. Freeze exclusion budgets from the baseline before candidate
replay. If fewer repetitions qualify but every planned control combination has
independent evidence, retain that bounded scope explicitly instead of recapturing
the whole matrix just to increase the row count. Never count exclusions as fixes.
For a new event-boundary observer, declare automated preflight coverage for both
active and inactive states before requesting hardware. A single read that is
already clear in every preflight case can test grant timing, but cannot locate
the event edge. State that narrower purpose explicitly; move the observer
earlier or use a longer operation before claiming source-event timing.

When a strict packet gate flags changed diagnostic snapshots, retrieve their
field meanings before drawing a timing conclusion. Legacy live snapshots may
have coarser qualification than settled measurements. Keep the strict gate for
unrelated fields, retain the established qualified checks, and require a new
calibrated control experiment for the changed path. Document this scope change
and its evidence; never silently drop a regressed field or relax a candidate's
budget to make it pass.

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
Failed, incomplete and stale runs cannot be accepted. A completed failed batch
can still record `narrow`, `measure` or `preserve` with evidence, so a rejected
candidate does not require manual record repair. Command success is a
mechanical requirement; Sol must still assess timing inference and generalization.

The runner counts repeated identical evidence patterns. After two successive
runs add no evidence, another run requires a revised hypothesis/test or a changed
`smaller_reproducer` identifier. Repeating an unchanged repaired candidate against
the same old baseline does not count as new progress. Failure loops are tracked too.
Rejected comparisons are fingerprinted with their observed deltas/patterns, not
just the generic failure message; a new counterexample is useful evidence even
when the validation gate correctly rejects another candidate.

Maintain `confirmed_facts`, `accepted_commits`, `rejected_hypotheses` with evidence,
`references`, `source_files`, `next_question` and history links in the investigation
JSON. Automatic updates preserve these human findings. Keep chronology and detailed
traces in linked files. Restart packets include the current decision, identities,
validation and bounded knowledge lists; records over8000 characters must be
shortened before export. Start a fresh context at a natural boundary from this
packet and repository instructions, then retrieve only evidence needed next.

Start subsequent sessions from that restart packet; reread only the relevant
workflow sections when changing a contract. Do not repeatedly load this whole
guide, historical records, or successful suite logs into the investigation context.

## Replay reuse and failed-batch recovery

Replay cache keys bind the frozen binary/config/ROM/source identity, duration,
capture adapter version, capture/decoder code and declared replay inputs.
Comparison or reporting edits do not invalidate an unchanged capture. Cache
entries retain build metadata as well as packet hashes, so domain validation
runs identically on fresh and cached packets. Coverage is checked again on
reuse; a previously rejected preflight is evidence, not permission for hardware.

Old cache entries can be imported with `tools/migrate_replay_cache.py
--runner-sha256 OLD_SHA` only when their original runner fingerprint and all
frozen artifacts still verify. Never guess missing provenance. Migration keeps
original entries and records the verified old fingerprint.

`resume` preserves failed child output directories and assigns retried `--out`
commands a new directory under `validation-retries/`. Later consumers follow
recorded redirects. Successful unchanged checks are reused; failed evidence
remains available. Output paths outside the parent experiment require explicit
handling rather than automatic replacement.

For swept variants, coverage selectors can use
`"variant": {"mask": 3, "equals": 2}` to test control bits independently of
sweep bits. `allowed_values` enforces constant controls; merely requiring one
correct value would allow a mixture of correct and broken controls to pass.

Coverage controls are checked on every reference packet as well as emulator
preflight. Passing emulator controls cannot establish that the physical witness
worked. Declare scratch memory ranges outside probe code, result buffers and
stack; exercise the complete ROM in preflight before any live substitution.
A buffer overlapping the growing RAM code image can otherwise mimic an emulator
hang and waste a hardware cycle.

Saved-reference neighbor suites declare `"purpose": "regression"`, with a
frozen baseline. Their intended success is unchanged evidence, so the repeated
no-new-evidence investigation guard does not block them. They retain every
comparison/regression check and cannot request live hardware. Investigations
still require a revised hypothesis or smaller reproducer after stalled attempts.

Failure excerpts list distinct failed test names before the first diagnostic
window, with total/listed counts and a fixed output bound. Always inspect that
list before editing: the first assertion alone may hide another fixture with
the same invalid assumption and cause an unnecessary rebuild. Retrieve further
assertion details selectively from the compact Cargo wrapper log.

For CPU/blitter traces, filter custom addresses to the actual witnesses, e.g.
`--addresses 0xdff002,0xdff058`. Tracing every beam synchronization poll can
dominate the file and capture time. Preserve failed traces, but use a trace for
inference only after its result packet is byte-identical to the qualified
untraced replay. Bind START events to descriptors and retain the preceding
BLTSIZE grant separately; never assign the next case's launch to the previous
case. `tools/summarize_handoff_trace.py` writes this index and returns bounded
case detail with explicit PAL beam units and no event alignment.

Gate a startup/arbitration candidate first on independent source masks and
fixed-DMA patterns, including six-plane neighbors. A candidate can repair every
four-plane handoff case and preserve legacy/core tests while worsening fields
in already-mismatching six-plane cases. Require zero new field regressions,
not merely a lower mismatch total. Finish these inexpensive held-out comparisons
before starting a broad test rebuild; preserve rejected binaries and summaries
for reuse rather than recompiling them to rediscover the same counterexamples.

For fixed-window status probes, prefer an active-first/clear-second coverage
check on the same descriptors when both samples already exist. Requiring both
values in only the first sample may reject a useful capture precisely because
hardware retains busy longer than the model. Preserve the failed contract and
original captures, explain any revised witness contract, then revalidate every
control and reference without changing qualification/regression budgets. If no
existing sample brackets the transition, widen the actual observer before
requesting hardware again. Post-read beam witnesses also include contention in
the following beam read; do not present them as the preceding bus grant time.

# CIA hardware verification, 19 October 2026

## Objective and evidence rules

Physically verify Copperline `f2d0a523`, then investigate CIA/IRQ differences
using this A500 as the reference. WinUAE is corroborating evidence only.
Use underflow-count brackets, never align traces or infer E-clock phase from
requested NOP delays. Original artifacts: `captures/cia-hw-20261019/`.

## Probe and competing explanations

`build_cia_hardware_verify.py` builds an isolated source snapshot without
changing existing in-progress probes. Kind52 observes serial SP completion;
kind53 observes Timer-A PB6 pulse/toggle output. Timer B counts actual Timer-A
underflows. Target selects CIA-A/B, delays are requested DBRA loops, repeats
are explicit. The manifest defines overloaded record fields and units.

Initial hypothesis: f2d's single-edge PB/serial behavior matches hardware;
alternative: batching consistency preserved an incorrect physical model.
Measured underflows distinguish serial transfer clocks from software timing;
settled PB polarity and toggle parity distinguish output state from pin phase.

Pilot `build/cia-hw-verify-v2` / `a500-v2-run1` completed and original OneROM
contents/reset release were verified restored. The settled pulse output is
low on both CIAs, while f2d returns high. Do not accept f2d as fully HW-verified.
The pilot also exposed setup limitations: stopped one-shot high-byte writes
auto-start, and serial engine history can cross trials. Serial pilot flags
are not evidence for a specific transfer length.

The controlled v3 ROM drains serial activity before each measured byte,
acknowledges setup flags, and selects one-shot only after latch writes.
PB cases cross DDRB=00/FF with pulse/toggle and continuous/one-shot modes.
This tests pulse polarity against a DDR/mux explanation. Both captures preserve
complete source snapshots and hashes. A fresh repeat is required before the
new results become a trusted baseline.

## Relevant code and tools

- `src/rom/cia_hardware_verify.i`: finite measurement kernel, CPU IRQs masked.
- `compare_cia_hardware.py`: count-qualified groups, hypothesis summaries and
  `--case` detail. Does not call raw beam fields IRQ timings.
- `../Copperline/src/chipset/cia.rs`: PB output state, START, serial shifter.
- `tools/run_onerom_live.py`: fresh backup, verified live replacement, capture,
  restoration readback and reset release; do not bypass its restoration path.

## Confirmed controlled measurements

V3 ran twice on the physical A500. Both restore reports verify the original
ROM and final reset release with no errors. Of 2,128 cases, 1,917 repeat pairs
share underflow qualifications and all compared outputs agree; 211 different
brackets remain explicitly excluded. Packets and provenance are versioned as
`references/cia-output-serial-v3-run1` and `run2`.

- All 800 settled pulse cases drive PB6 low, across both CIAs, DDRs, latches,
  and continuous/one-shot modes. F2d drives them high.
- Positive-latch toggle cases follow START-high parity. Preserving the old
  toggle state across START is wrong. The PB1 candidate matches 630/630
  qualified nonzero-latch toggles and 764/764 qualified pulse cases.
- All 80 continuous zero-latch toggle live samples and all 80 settled samples
  are low on hardware. This rules out a STOP-only explanation. A continuously
  asserted underflow pulse has only one rising edge; a candidate now preserves
  that edge rule instead of toggling on every E-clock.
- With a clean serial engine and latch 15, hardware SP remains clear at
  measured underflow brackets 8..9, 10..11, 12..13 and 14..15; it is set at
  16..17 and 20..21, on both CIAs. F2d already sets SP at 8..9. V2 serial
  history-dependent flags are discarded as transfer-length evidence.

V4 adds 144 high-byte auto-start neighbors; no new timing constants are being
fit. PB and serial families are corrected and replayed separately. Selected
PORTS/EXTER bits from the existing pre-ICR INTREQR snapshot are also compared,
with unrelated interrupt bits masked out. This constrains software-visible
route behavior, not electrical pin latency or CPU IPL sampling.

## Auto-start control and stability

V4 adds 144 high-byte auto-start cases. Two independent physical captures
agree on all 2,225 count-qualified pairs; 47 different brackets are excluded.
Both live-ROM restores and final reset releases were verified without errors.
Versioned packets: `references/cia-output-serial-v4-run1` and `run2`.
Zero-latch auto-start produces two adjacent TA underflows, while positive
latch 1 produces one. Long latch 200 remains unexpired at these delays. Both
adjacent zero carries merge into one PB toggle edge; raw carry parity alone
is therefore an invalid pin predictor at latch zero. The model preserves the
first carry until the following edge instead of stopping the one-shot early.
This correction is limited to TA: TB zero auto-start still needs hardware data.

## Reproduction and selective detail

Build a new immutable probe directory:

```powershell
python build_cia_hardware_verify.py --wsl --vasm /mnt/c/Users/seppo/amiga/amiga-hardware-probes/.tools/vasm/vasmm68k_mot --out build/cia-hw-verify-NEW
python compare_cia_hardware.py --hardware references/cia-output-serial-v4-run1 --candidate captures/NEW --out captures/report.json
```

Use `--case 52:0:1:3:128:0` for one descriptor. Actual compatible replay ROMs
and source snapshots are locally archived in `build/cia-hw-verify-v3` and `v4`;
commercial images are never committed. Rebuilding from a changed surrounding
probe source changes source ID and must not bypass the comparison guard.
Typed reports group output mismatches and separately group different measured
underflow brackets, with representative case IDs. No trace alignment is done.
Probe snapshots contain registers rather than an event trace; these reports
make no claim to identify a sub-E-clock first divergent event.

The comparator tests deliberately change SP/PB/INTREQ values, remove a row,
and shift an observation bracket. The general comparison suite separately
checks malformed captures. Invalid typed packets fail decoding/validation
rather than being silently included in matched totals.

## Next unresolved questions

No selected PORTS/EXTER differences remain in qualified final observations.
These masked-CPU measurements constrain observed INTREQ state, not electrical
propagation or 68000 polling; no global IRQ-delay patch is justified. Serial buffering and SDR
writes during an active transfer remain unverified. Investigate those with a
clean-drain control and explicit queued-byte cases, rather than inferring a
queue from the discarded history-dependent v2 pilot.

The bus/BZERO sampling question and its rejected global sampling patch remain
in `accuracy-investigation-2026-10-18.md`. Use its marker experiment before
another bus change; unchanged divider cases provide no new CPU-fix evidence.

## Final integrated comparison

The same v3 ROM and reference distinguish f2d0a523 from the correction:
1,946 qualified observations, f2d 765 matches / 1,181 mismatches, corrected
1,946 matches / zero mismatches. Both have 182 different brackets, zero missing
results and valid checksum-protected packets. Counts include selected INTREQ
bits; earlier provisional totals without that field were 1,178 mismatches.

V4 correction versus run1: 2,272 total, 2,063 qualified matches, zero
mismatches/missing, 209 different brackets. By family: serial 386/386,
explicit-start PB6 1,533/1,533, auto-start 144/144. Every auto-start carry count
matches; none of the former 48 zero-latch carry differences is excluded.
Versus independent run2: 2,069 qualified matches, zero mismatches, 203 different
brackets. These are functional comparisons conditional on measured counts;
excluded observations are not proof of cycle-level timing agreement.

Machine/config and candidate executable hashes, counts and qualification rules:
`references/cia-output-serial-validation.json`. Local complete reports:
`captures/cia-hw-20261019/a500-v3-vs-f2d-final-comparator.json`,
`a500-v3-vs-final.json`, `a500-v4-vs-final.json`, and
`a500-v4-run2-vs-final.json`.

The reusable runner now includes `--suite cia-output` with the immutable v4
ROM and reference, plus executable/config snapshots and the same typed
comparison. It returned the identical 2,063/2,063 qualified result in a
separate acceptance replay. It rejects a source-ID mismatch.

## Regression validation

Headless core: 3,020 passed, zero failed, five ignored. Strict all-target /
all-feature Clippy and formatting pass. Probe tools: 175 passed, including
intentional comparator mutations. CIA-only model tests additionally cover
PB polarity on both timers/DDRs, START reset, merged pulses and gap rearming,
auto-start carries, serial completion/pin ordering, and save/restore of the
half-bit phase. Full Cargo logs stay in `captures/cia-hw-20261019/cargo`.
The default GUI suite was not repeated; its two previously recorded Windows
numpad/scaler failures remain documented in the prior handoff.

Archived hardware neighbors: kind51 67/67 exact-launch matches, focused IRQ
2,212/2,212, divider/IRQ 2,560/2,560 with identical packets. Kind51's 1,469
unmatched launches remain excluded. IRQ replay is evidence for those cases,
not a general claim that all electrical/CPU IRQ timing has been measured.

Copperline accuracy correction committed as `3b43225c` (parent `f2d0a523`).

Bus neighbors remain unchanged on common launch cohorts: Copper busy 41/449
mismatches, handoff 1,238/2,304, BZERO 0/4,608. Zero repaired or regressed cases
in all three; `captures/cia-hw-20261019/bus-regression-comparison.json` retains
per-field evidence. These existing bus differences remain unresolved.

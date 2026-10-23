# Versioned hardware measurement references

These binary files contain only this project's checksum-protected RBCP
measurement records, not test ROMs, commercial ROMs, firmware, or disk images.
Each immutable reference has a manifest identifying its original capture,
test ROM hash, source fingerprint, result hash, hardware configuration,
capture method and repeatability evidence. Never replace an existing baseline;
add a new reference ID when measurements change.

The owner's reported current CIA markings and replacement history are recorded
in [measurement hardware](../docs/a500-measurement-hardware.md). Link that record
from future captures; historical applicability is not yet established.

`cia-irq-kind51-review3-run1` and `run2` preserve independent A500 runs. Only 99
descriptor pairs share both recorded start samples; all 99 observations match.
Other start phases differ and must not be treated as equivalent timing evidence.
The focused IRQ and divider references retain the previously verified v3 runs.
Their detailed interpretation is in `../docs/irq-focus-measurements-2026-10-15.md`
and `../docs/divider-irq-verification-2026-10-15.md`.

The bus neighbors are `copper-busy-kind50`, `blitter-handoff-kind49` and
`bzero-edges-kind22`. Kind50 reuses the ordinary status/PC slots as raw DMACONR
samples: use its explicit profile and `compare_copper_busy.py`, not a generic
status-zero rule. These captures retain within-run repeats without claiming
independent repetition. See `../docs/accuracy-investigation-2026-10-18.md` for
accepted/rejected changes and links to detailed evidence.

Original transcripts, restore verification, full source/build archives and
private machine logs remain under ignored `captures/` and `build/`. Reference
manifests identify them without publishing private device serials. Raw floating
chip ID reads do not establish a silicon revision.

`tools/replay_accuracy.py` reads these references and source-matched local ROM
archives, snapshots an emulator executable/configuration, and prints compact
comparison summaries. `python -m unittest tests.test_hardware_references -q`
checks the versioned hashes, packet checksums and descriptor integrity.

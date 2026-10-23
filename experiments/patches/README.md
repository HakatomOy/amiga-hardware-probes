# Timing counterfactuals

These patches preserve rejected or unfinished models for investigation. They
are not accepted emulator fixes. Use an isolated Copperline checkout; do not
apply them on top of one another or merge their environment selectors.

| Patch | Source base | Selector |
| --- | --- | --- |
| `init-request-mechanisms-v1.patch` | `b40122d4` plus uncommitted application of `02318e9e` | `COPPERLINE_EXP_STARTUP_REQUEST` |
| `init-cpu-clock-phase-v1.patch` | `6c06be2a` | `COPPERLINE_EXP_CLASSIC_BUS_PHASE` |
| `init-shared-cpu-phase-v1.patch` | `6c06be2a` | `COPPERLINE_EXP_CLASSIC_BUS_PHASE` |
| `init-cpu-grant-phase-v1.patch` | `6c06be2a` | `COPPERLINE_EXP_CPU_GRANT_PHASE` |

Matching recipes are in `experiments/screens/`. Build with Copperline's compact
Cargo wrapper, then run `tools/screen_capture_variants.py RECIPE --out
captures/UNIQUE --binary PATH --workers 3`. The tool freezes the executable,
verifies the declared baseline packet exactly, and saves bounded comparisons.
Its output is a counterfactual screen, never full acceptance.

Historical baseline packets and executable snapshots live in ignored
`captures/init-after-bmapen-20261022/`. On another checkout, regenerate baseline
packets from the stated source base and exact ROM/configuration before editing
a recipe's baseline path. Versioned A500 measurements live in `references/`;
never substitute an emulator packet for hardware evidence.

Read `investigations/init-after-bmapen.json` and the linked focused records for
decisions and limitations. In particular, an equal integer input beam does not
prove identical CPU sub-CCK phase across different ROMs. Preserve separate ROM
hashes, unstable cohorts and original qualification budgets.

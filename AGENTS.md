# Repository Guidelines

## Commands and project knowledge

Python tools are in the root and `tools/`, probe assembly in `src/rom/`, tests
in `tests/`, versioned hardware data in `references/`. Workspace instructions
apply; consult relevant sections of the [workflow guide](docs/experiment-workflow.md)
for manifest details. Current findings
and next questions live in `investigations/*.json`; detailed histories live in
`docs/` and ignored `captures/`. Do not overwrite unrelated working changes.

Run `python -m unittest discover -s tests -q` for tool regression tests.
Use `python tools/experiment.py run MANIFEST --out captures/UNIQUE` for an
experiment batch. The manifest declares build steps, capture requirements,
comparison rules and focused/neighbor/broad validation. See
`experiments/workflows/serial-buffer.json`. Commands are argument arrays;
Cargo commands must use Copperline's `tools/cargo_report.py` wrapper.

## Evidence and validation

Before a hardware run or patch, state the leading hypothesis, competitor,
distinguishing test and implications of each outcome in the manifest. Investigate
one mismatch family. Reuse saved measurements by default; `--hardware` explicitly
requests new live runs and verified restoration. Version reviewed captures with
the `archive` command; never commit ROM images, live backups or control tokens.

Keep units, field meanings and qualification rules explicit. Never align away
timing differences. Inspect compact deltas and new patterns before retrieving
specific cases with `detail --case ID --window N`. Emulator agreement does not
override valid hardware evidence. Exclusions and unstable repeats are not matches.
Read `evidence RUN` first: bounded family/case deltas, with unchanged families
as counts. Use `--baseline PRIOR_RUN` for older runs; retrieve detail only for a
stated uncertainty. Family IDs identify signatures, not proven shared causes.

Validate focused cases, neighbors, then the broader suite before acceptance.
Rebuild only for changed executable inputs; use immutable binary snapshots.
Do not repeatedly poll or print full logs: consume completion events or the final
summary. After repeated runs add no evidence, revise the hypothesis or narrow
the reproducer. Record an evidence-backed decision with `decide`.

## Context boundaries

Keep confirmed facts, rejected hypotheses with evidence, accepted commits,
capture IDs, source paths and the next question in the short investigation
record. Move chronology and traces to linked files. Generate a bounded `restart`
packet at a natural boundary instead of carrying the full conversation forward.
Use scripts for repetitive work; do not delegate to Luna yet. File-backed cache
rules and the results storage map are in `docs/result-storage.md`. Cached reports
are conveniences, never substitutes for capture qualification or acceptance.

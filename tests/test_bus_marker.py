import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path

import build_bus_marker_rom as builder
import compare_bus_marker as comparator


def row():
    return dict(kind=55, target=0, variant=0, phase=0, delay=0, repeat=0,
                launch_beam=0x4260, launch_ref=0x4280, counter=0, icr=0x6000,
                irq_beam=0x10, irq_level=0x4000, saved_pc_offset=0x00104000,
                status=0x10, aux=0x4000)


class BusMarkerTests(unittest.TestCase):
    def test_matrix_has_both_owners_marker_orders_and_controls(self):
        rows = builder.trials()
        self.assertEqual(len(rows), 896)
        self.assertEqual(len(set(rows)), 896)
        self.assertEqual({r[2] for r in rows}, set(range(16)))
        self.assertEqual({r[-1] for r in rows}, {0, 1})

    def test_changed_marker_and_busy_have_distinct_first_reads(self):
        a = row()
        marker = comparator.compare([a], [dict(a, counter=0x10)])
        busy = comparator.compare([a], [dict(a, icr=0x2000)])
        self.assertEqual(marker["patterns"][0]["first_divergent_read"], 0)
        self.assertEqual(busy["patterns"][0]["first_divergent_read"], 1)
        self.assertEqual(busy["counts"]["mismatch"], 1)

    def test_missing_and_shifted_brackets_are_not_matches(self):
        a = row()
        self.assertEqual(comparator.compare([a], [])["counts"]["missing"], 1)
        shifted = comparator.compare([a], [dict(a, launch_ref=0x4282)])
        self.assertEqual(shifted["counts"]["different_brackets"], 1)
        self.assertEqual(shifted["counts"]["comparable"], 0)

    def test_unrelated_interrupt_bits_do_not_change_observation(self):
        a = row()
        self.assertEqual(comparator.compare([a], [dict(a, counter=0x40)])["counts"]["match"], 1)
        self.assertEqual(comparator.samples(a)[4:6], (0x10, 0x4000))

    def test_cohort_matching_retains_exact_phase_and_rejects_unstable_refs(self):
        a = row()
        b = dict(a, repeat=1)
        result = comparator.compare_cohorts([a], [b])
        self.assertEqual(result["counts"]["match"], 1)
        shifted = comparator.compare_cohorts([a], [dict(b, launch_ref=0x4282)])
        self.assertEqual(shifted["counts"]["no_identical_bracket"], 1)
        unstable = comparator.compare_cohorts([a, dict(b, icr=0x2000)], [a])
        self.assertEqual(unstable["counts"]["unstable_reference"], 1)
        self.assertEqual(unstable["counts"]["comparable"], 0)

    def test_focused_matrix_is_smaller_and_repeats_completion_controls(self):
        rows = builder.trials(focused=True)
        self.assertEqual(len(rows), 384)
        self.assertEqual({r[1] for r in rows}, {1})
        self.assertEqual({r[3] for r in rows}, {4, 5, 6})
        self.assertEqual({r[-1] for r in rows}, set(range(16)))

    def test_completion_matrix_has_only_copper_and_both_priority_modes(self):
        rows = builder.trials(completion=True)
        self.assertEqual(len(rows), 640)
        self.assertFalse(any(r[2] & 2 for r in rows))
        self.assertEqual({r[2] & 1 for r in rows}, {0, 1})
        a = row()
        self.assertEqual(comparator.samples(dict(a, counter=0x14))[0], 0x14)

    def test_pressure_matrix_and_replaced_samples(self):
        rows = builder.trials(pressure=True)
        self.assertEqual(len(rows), 768)
        self.assertEqual(len(set(rows)), 768)
        self.assertEqual({r[4] for r in rows}, set(range(4)))
        a = dict(row(), delay=3, icr=0xa55a, irq_level=0xa55a)
        self.assertIsNone(comparator.samples(a)[1])
        self.assertIsNone(comparator.samples(a)[3])
        self.assertEqual(comparator.samples(a)[5], 0x4000)

    def test_onset_matrix_samples_short_and_long_blits_before_launch(self):
        rows = builder.trials(onset=True)
        self.assertEqual(len(rows), 2176)
        self.assertEqual(len(set(rows)), len(rows))
        self.assertEqual({r[1] for r in rows}, {0, 1})
        self.assertEqual({r[3] for r in rows}, set(range(17)))

    def test_pressure_staging_keeps_the_experiment_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "source"
            rom = root / "src/rom"
            rom.mkdir(parents=True)
            (root / "vendor/rbcp").mkdir(parents=True)
            (root / "build_rom.py").write_text("")
            (root / "build_bus_marker_rom.py").write_text("")
            (rom / "experiment.asm").write_text("        cmpi.w #10,(a4)\n.channels:\n")
            (rom / "edge_kernel.asm").write_text("")
            (rom / "bus_marker_kernel.i").write_text(".list_end:\n        move.l #$fffffffe,(a0)\n        jsr $ffca00\n")
            (rom / "bus_marker_observer.i").write_text("bus_marker_observer:\n        move.w $002(a6),d1\n        move.w $002(a6),d3\n")
            def fake_build(*args, **kwargs):
                output = builder.build_rom.ROOT / "build/rom"
                output.mkdir(parents=True)
                (output / "fake.bin").write_bytes(b"test")
                return {}
            out = Path(folder) / "output"
            with patch.object(builder, "ROOT", root), patch.object(builder.build_rom, "build", fake_build):
                builder.build("unused", False, out, pressure=True)
            staged = out / "source_snapshot/src/rom"
            self.assertIn("jsr bus_marker_trial", (staged / "experiment.asm").read_text())
            self.assertIn("cmpi.w #10", (staged / "experiment.asm").read_text())
            self.assertIn("move.w .dummy(pc),d1", (staged / "bus_marker_pressure_1.i").read_text())

    def test_phase_controls_keep_sample_layout_and_cover_both_owners(self):
        for entry, total in ((False, 768), (True, 1792)):
            rows = builder.trials(phasepad=True, phase_entry=entry)
            self.assertEqual(len(rows), total)
            self.assertEqual(len(set(rows)), total)
            self.assertEqual({r[2] & 16 for r in rows}, {0, 16})
            self.assertEqual({r[2] & 2 for r in rows}, {0, 2})

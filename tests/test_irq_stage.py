import unittest
import compare_irq_stage as c
import build_irq_stage_rom as b


def row():
    r = dict.fromkeys(c.rom_results.FIELDS, 0)
    r.pop("pc_hi"); r.pop("pc_lo")
    r.update(kind=56, target=0, variant=1, status=0, aux=1, irq_level=3,
             irq_beam=0x4260, saved_pc_offset=0xffcc02)
    return r


class IRQStageTests(unittest.TestCase):
    def test_bounded_matrix(self):
        self.assertEqual(len(b.trials()), 1600)
        self.assertEqual(len(set(b.trials())), 1600)
        with self.assertRaises(ValueError):
            b.trials(3)

    def test_mutations_and_missing_records_are_detected(self):
        h = row()
        self.assertEqual(c.compare([h], [dict(h)])["counts"]["matches"], 1)
        for field in ("counter", "irq_beam"):
            bad = dict(h); bad[field] += 1
            self.assertEqual(c.compare([h], [bad])["counts"]["mismatches"], 1)
        self.assertEqual(c.compare([h], [])["counts"]["missing_results"], 1)

    def test_bracket_shift_cannot_be_aligned_away(self):
        h = row(); bad = dict(h, launch_ref=1)
        d = c.compare([h], [bad])["counts"]
        self.assertEqual(d["matches"], 0)
        self.assertEqual(d["no_identical_bracket"], 1)

    def test_watchdog_and_duplicate_event_invalid(self):
        for bad in (dict(row(), status=1), dict(row(), aux=2), dict(row(), irq_level=1)):
            with self.assertRaises(ValueError):
                c.validate(bad)

    def test_conflicting_independent_reference_runs_are_excluded(self):
        h = row()
        changed = dict(h, repeat=1, counter=1)
        d = c.compare([h, changed], [h])["counts"]
        self.assertEqual(d["unstable_reference"], 1)
        self.assertEqual(d["matches"] + d["mismatches"], 0)

    def test_diagnostic_flags_stay_visible_without_becoming_timing_errors(self):
        h = row()
        p = c.compare([h], [dict(h, end_ref=8)])
        self.assertEqual(p["counts"]["mismatches"], 1)
        self.assertEqual(c.software_summary(p)["timing_or_visibility_mismatches"], 0)
        self.assertEqual(c.software_summary(p)["diagnostic_cia_icr_mismatches"], 1)
        p = c.compare([h], [dict(h, irq_beam=h["irq_beam"]+1)])
        self.assertEqual(c.software_summary(p)["timing_or_visibility_mismatches"], 1)

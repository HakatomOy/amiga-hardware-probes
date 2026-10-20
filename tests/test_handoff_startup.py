import unittest
import build_handoff_startup_rom as probe


class HandoffStartupTests(unittest.TestCase):
    def test_sweep_crosses_source_masks_without_fake_copper_control(self):
        rows = probe.trials()
        self.assertEqual(len(rows), 1152)
        self.assertEqual(len(set(rows)), len(rows))
        self.assertEqual({r[1] for r in rows}, {0, 3, 6})
        self.assertEqual({(r[2] >> 1) & 3 for r in rows}, {0, 1, 2})
        self.assertEqual({r[2] >> 5 for r in rows}, {0, 1, 2, 3})
        for target in (0, 3, 6):
            subset = [r for r in rows if r[1] == target]
            self.assertEqual(sum(bool(r[2] & 8) for r in subset), 192)

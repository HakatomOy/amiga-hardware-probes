import unittest

import build_line_c_history_rom as suite


class LineCHistoryRomTests(unittest.TestCase):
    def test_default_matrix_and_named_subsets(self):
        rows = suite.line_c_history_rows()
        self.assertEqual(len(rows), 960)
        self.assertEqual({row[0] for row in rows}, {45})
        selected = suite.line_c_history_rows(["a-ffff", "b-ffff", "all-ffff"])
        self.assertEqual(len(selected), 480)
        self.assertEqual({row[2] for row in selected}, {2, 3, 5})

    def test_unknown_pattern_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown priming pattern"):
            suite.line_c_history_rows(["not-a-pattern"])


if __name__ == "__main__":
    unittest.main()

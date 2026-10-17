import unittest

import build_blitter_handoff_rom as probe


class BlitterHandoffRomTests(unittest.TestCase):
    def test_full_matrix_has_unique_kind49_rows(self):
        rows = probe.blitter_handoff_rows()
        self.assertEqual(len(rows), 2304)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual({row[0] for row in rows}, {49})
        self.assertEqual({row[2] for row in rows}, set(range(8)))
        self.assertEqual({row[3] for row in rows}, {0, 1})
        self.assertEqual({row[4] for row in rows}, set(range(8)))
        self.assertEqual({row[5] for row in rows}, {0, 1})

    def test_targets_decode_to_single_line_widths_and_channel_modes(self):
        expected_width_words = (1, 2, 16)
        expected_control = (0x01FF, 0x09F0, 0x0FFF)
        expected_result = (0xFFFF, 0xAAAA, 0xFFFF)
        by_target = {mode * 3 + width: (mode, width)
                     for mode in range(3) for width in range(3)}
        self.assertEqual(set(by_target), set(range(9)))

        for target, (mode, width_index) in by_target.items():
            words = expected_width_words[width_index]
            bltsize = (1 << 6) | words
            # BLTSIZE stores vertical size in bits 15:6 and horizontal size in 5:0.
            decoded_height = (bltsize >> 6) & 0x3FF
            decoded_width = bltsize & 0x3F
            self.assertEqual(decoded_height, 1)
            self.assertEqual(decoded_width, words)
            channel = probe.CHANNEL_MODES[mode]
            self.assertEqual(channel["bltcon0"], expected_control[mode])
            self.assertEqual(channel["output"], expected_result[mode])
            self.assertEqual(target // 3, mode)
            self.assertEqual(target % 3, width_index)

    def test_variant_bits_are_orthogonal(self):
        for variant in probe.VARIANTS:
            value = variant["id"]
            self.assertEqual(value & 1, variant["priority"])
            self.assertEqual((value >> 1) & 3, variant["dma_mode"])
        self.assertEqual({v["priority"] for v in probe.VARIANTS}, {0, 1})
        self.assertEqual({v["dma_mode"] for v in probe.VARIANTS}, set(range(4)))

    def test_archive_metadata_matches_hardware_encodings_and_record(self):
        rows = probe.blitter_handoff_rows()
        meta = probe.metadata(rows, [])
        self.assertEqual(meta["poll_bound"], 4096)
        by_target = {entry["id"] * 3 + entry["width_index"]: entry
                     for entry in meta["channel_modes"]}
        for mode in range(3):
            for width_index, expected_words in enumerate((1, 2, 16)):
                entry = by_target[mode * 3 + width_index]
                size = entry["bltsize"]
                self.assertEqual((size >> 6) & 0x3FF, 1)
                self.assertEqual(size & 0x3F, expected_words)
                self.assertEqual(entry["words"], expected_words)
        measurement = meta["measurement"]
        self.assertEqual(measurement["status_offset"], 32)
        self.assertEqual(measurement["fields"]["status"], 32)
        self.assertEqual(meta["result_status"], {"offset": 32, "success": 0, "timeout": 1})
        self.assertEqual(measurement["fields"], {
            "launch_vhposr": 12, "first_clear_dmaconr": 14, "early_d": 16,
            "postwrite_dmaconr": 18, "handoff_vhposr": 20, "postwrite_vhposr": 22,
            "final_first_d": 24, "final_last_d": 26, "intreqr": 28,
            "settled_vhposr": 30, "status": 32,
        })

    def test_invalid_selection_is_rejected(self):
        with self.assertRaises(ValueError):
            probe.blitter_handoff_rows(channel_modes=(3,))
        with self.assertRaises(ValueError):
            probe.blitter_handoff_rows(delays=(0, 0))
        with self.assertRaises(ValueError):
            probe.blitter_handoff_rows(
                channel_modes=range(3), width_indexes=range(3), variants=range(8),
                phases=range(2), delays=range(8), repeats=range(3))


if __name__ == "__main__":
    unittest.main()

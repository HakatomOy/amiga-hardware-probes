import unittest
from pathlib import Path

import build_line_a_bit_rom as suite

ROOT = Path(__file__).resolve().parents[1]


class LineABitRomTests(unittest.TestCase):
    def test_exact_kind48_matrix_and_variant_encoding(self):
        rows = suite.line_a_bit_rows()
        self.assertEqual(len(rows), 1536)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual(suite.VARIANTS, (0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14))
        self.assertEqual({row[0] for row in rows}, {48})
        self.assertEqual({row[1] for row in rows}, set(range(16)))
        self.assertEqual({row[2] for row in rows}, set(suite.VARIANTS))
        self.assertEqual({row[3] for row in rows}, {0})
        self.assertEqual({row[4] for row in rows}, {0})
        self.assertEqual({row[5] for row in rows}, set(range(8)))

        variants = suite.variant_metadata()
        self.assertEqual(variants["unused_variant_values"], [3, 7, 11, 15])
        self.assertEqual([item["ashift"] for item in variants["variants"]],
                         [0, 2, 4] * 4)
        self.assertEqual([item["b_data"] for item in variants["variants"]],
                         [0, 0, 0, 0xffff, 0xffff, 0xffff,
                          0, 0, 0, 0xffff, 0xffff, 0xffff])
        self.assertEqual([item["pixels"] for item in variants["variants"]],
                         [1] * 6 + [2] * 6)
        self.assertEqual([item["bltsize"] for item in variants["variants"]],
                         [0x0042] * 6 + [0x0082] * 6)

    def test_history_control_matrix_is_bounded_and_discriminates_prime_state(self):
        rows = suite.line_a_history_control_rows()
        self.assertEqual(len(rows), 2016)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertLessEqual(len(rows), suite.MAX_PAYLOAD_ROWS)
        self.assertEqual({row[1] for row in rows}, {0, 6, 7})
        self.assertEqual({row[2] & 0x30 for row in rows}, {0x30})
        self.assertEqual({row[2] & 3 for row in rows}, {0, 1, 2, 3})
        self.assertEqual({(row[2] >> 2) & 3 for row in rows}, {0, 1, 2})
        self.assertEqual({row[3] for row in rows}, set(range(7)))
        self.assertEqual({row[4] for row in rows}, {0})
        self.assertEqual({row[5] for row in rows}, set(range(8)))
        metadata = suite.history_control_metadata()
        self.assertEqual(metadata["a_pattern_indices"], [0, 6, 7])
        self.assertEqual(metadata["a_pattern_values"], ["0x8000", "0x2800", "0x2801"])
        self.assertEqual(metadata["minterms"], ["0xf0", "0xcc", "0x40", "0xca"])
        self.assertEqual([p["name"] for p in metadata["prime_profiles"]],
                         list(suite.HISTORY_PRIMES))
        self.assertEqual([o["name"] for o in metadata["bdat_orders"]],
                         list(suite.HISTORY_BDAT_ORDERS))
        self.assertEqual(len(suite.line_a_truth_control_rows()), 2048)

    def test_history_control_flag_does_not_overlap_truth_control_dispatch(self):
        parser_source = (ROOT / "build_line_a_bit_rom.py").read_text()
        self.assertIn('controls.add_argument("--history-control"', parser_source)
        self.assertIn('controls.add_argument("--truth-control"', parser_source)
        self.assertIn('controls.add_argument("--normal-history-control"', parser_source)
        self.assertIn('controls.add_argument("--normal-history-no-dma-control"', parser_source)
        self.assertIn('controls.add_argument("--line-hold-matrix"', parser_source)
        self.assertIn('controls.add_argument("--line-hold-c-dma-matrix"', parser_source)
        self.assertIn("line_hold_c_dma_matrix)) > 1", parser_source)
        self.assertIn("0x30 | (order_index << 2) | minterm_index", parser_source)

    def test_normal_history_control_matrix_is_bounded(self):
        rows = suite.line_a_normal_history_control_rows()
        self.assertEqual(len(rows), 168)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual({row[1] for row in rows}, {0})
        self.assertEqual({row[2] for row in rows}, {0x71, 0x75, 0x79})
        self.assertEqual({row[3] for row in rows}, set(range(7)))
        self.assertEqual({row[4] for row in rows}, {0})
        self.assertEqual({row[5] for row in rows}, set(range(8)))
        metadata = suite.normal_history_control_metadata()
        self.assertEqual(metadata["row_count"], 168)
        self.assertEqual(metadata["target"]["bltcon0"].split()[0], "0x01cc")
        self.assertEqual(metadata["target"]["bltsize"], "0x0041 (one D word)")

    def test_normal_history_no_dma_matrix_has_two_profiles_and_48_rows(self):
        rows = suite.line_a_normal_history_no_dma_control_rows()
        self.assertEqual(len(rows), 48)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual({row[1] for row in rows}, {0})
        self.assertEqual({row[2] for row in rows}, {0x71, 0x75, 0x79})
        self.assertEqual({row[3] for row in rows}, {7, 8})
        self.assertEqual({row[4] for row in rows}, {0})
        self.assertEqual({row[5] for row in rows}, set(range(8)) )
        profiles = suite.normal_history_no_dma_control_metadata()["prime_profiles"]
        self.assertEqual([p["bdat_cpu_write"] for p in profiles], ["0x2800", "0xd7ff"])
        self.assertTrue(all(p["bltcon0"].startswith("0x00cc") for p in profiles))

    def test_line_hold_matrix_dimensions_and_prediction_metadata(self):
        rows = suite.line_a_line_hold_matrix_rows()
        self.assertEqual(len(rows), 1152)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual({row[1] for row in rows}, set(range(4)))
        self.assertEqual({row[2] for row in rows},
                         {0xf0 | (order << 2) | shift
                          for order in range(3) for shift in range(4)})
        self.assertEqual({row[3] for row in rows}, {1, 2, 3})
        self.assertEqual({row[4] for row in rows}, {0})
        self.assertEqual({row[5] for row in rows}, set(range(8)))
        metadata = suite.line_hold_matrix_metadata()
        self.assertEqual(metadata["b_patterns"],
                         ["0x0001", "0x8000", "0xa55a", "0x1248"])
        self.assertEqual(metadata["bshifts"], [0, 1, 7, 15])
        self.assertEqual(metadata["line_prime"]["bltcon0"],
                         "0x00cc (all DMA channels disabled)")
        measured = metadata["predicted_model"]
        self.assertEqual(measured["end_BSHIFT"], "(BSHIFT - pixels) & 15")
        self.assertEqual(measured["before_con1"],
                         "shift_combine(raw_BDAT, 0, end_BSHIFT, false)")
        self.assertEqual(measured["skip"],
                         "pixels == 1: shift_combine(0, raw_BDAT, BSHIFT, false); "
                         "pixels in 2..3: rotate_right(raw_BDAT, "
                         "(BSHIFT - (pixels - 1)) & 15)")
        self.assertIn("A500 measurement", measured["status"])
        self.assertEqual(measured["source_id"],
                         "f721cceba127d7b3f226ab1ac3ae8ae6ee458e5e33ae5ddada142c94204949d2")
        self.assertEqual(measured["hardware_packet_sha256"],
                         "64d4776bafe96e924c5dae365917ff24b712daaef3ab5bed7eac7fe1950181db")

    def test_line_hold_c_dma_cohort_is_distinct_and_has_safe_initialized_buffer(self):
        rows = suite.line_a_line_hold_c_dma_matrix_rows()
        self.assertEqual(len(rows), 1152)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual({row[2] for row in rows},
                         {0xe0 | (order << 2) | shift
                          for order in range(3) for shift in range(4)})
        self.assertEqual({row[1] for row in rows}, set(range(4)))
        self.assertEqual({row[3] for row in rows}, {1, 2, 3})
        metadata = suite.line_hold_c_dma_matrix_metadata()
        self.assertIn("C DMA enabled", metadata["line_prime"]["bltcon0"])
        self.assertEqual(metadata["line_prime"]["c_pointer"], "0x14000")
        self.assertEqual(metadata["line_prime"]["c_data"],
                         "zero-filled 128-word buffer (256 bytes)")
        self.assertEqual(metadata["line_prime"]["d_pointer"],
                         "0x15000 for the first line-prime D write; later D writes track C "
                         "to 0x14050/0x140a0")
        self.assertIn("subsequent line D writes land in the zeroed C buffer",
                      metadata["line_prime"]["d_sink_span"])
        self.assertIn("not yet validated",
                      metadata["predicted_model"]["status"])
        self.assertIn("whether the measured B hold rule generalizes",
                      metadata["rationale"])

        asm = (ROOT / "src/rom/line_a_bit_kernel.i").read_text()
        hold = asm.split("line_a_bit_line_hold_trial:", 1)[1].split(
            "line_a_history_minterms:", 1)[0]
        dispatch = asm.split("line_a_bit_trial:", 1)[1].split(
            "line_a_bit_truth_trial:", 1)[0]
        self.assertLess(dispatch.index("btst #7,5(a4)"),
                        dispatch.index("btst #6,5(a4)"))
        self.assertIn("btst #4,5(a4)", hold)
        self.assertIn("lea $14000,a0", hold)
        self.assertIn("move.w #127,d7", hold)
        self.assertIn("move.l #$14000,$48(a6)", hold)
        self.assertIn("move.l #$15000,$54(a6)", hold)
        self.assertIn("move.w #$02cc,$40(a6)", hold)
        self.assertIn("move.l #$10000,$54(a6)", hold)
        self.assertLess(hold.index(".hold_clear_c:"),
                        hold.index("move.w #$02cc,$40(a6)"))

    def test_history_kernel_preserves_prime_and_selects_separate_lf_table(self):
        asm = (ROOT / "src/rom/line_a_bit_kernel.i").read_text()
        history = asm.split("line_a_bit_history_trial:", 1)[1].split(
            "line_a_history_minterms:", 1)[0]
        self.assertIn("btst #5,5(a4)", asm)
        self.assertIn("bne.w line_a_bit_history_trial", asm)
        self.assertIn("move.w #$04cc,$40(a6)", history)
        self.assertIn("move.w #$0042,$58(a6)", history)
        self.assertIn("move.w #$0082,$58(a6)", history)
        self.assertIn("move.l #-80,$50(a6)", history)
        self.assertIn("move.w #-280,$64(a6)", history)
        self.assertIn("move.w #80,$60(a6)", history)
        self.assertIn("move.w #80,$66(a6)", history)
        self.assertIn("move.w #$2800,$18000", history)
        self.assertIn("move.w #$d7ff,$18002", history)
        self.assertIn("lea line_a_history_minterms(pc),a0", history)
        self.assertIn("move.w #1,$42(a6)", history)
        self.assertIn("move.l #$16000,$4c(a6)", history)
        self.assertIn("move.w #0,$62(a6)", history)
        self.assertIn("move.l #-80,$50(a6)", history)
        self.assertLess(history.index("move.w #$8000,$74(a6)"),
                        history.index("move.w (a0),$74(a6)"))
        self.assertIn("move.w #$0082,d5", history)
        self.assertLess(history.index("move.w #$0082,d5"),
                        history.index("movea.l #$ff7800,a2"))
        self.assertIn("rept 16", history)
        self.assertIn("movea.l #$ff7800,a2", history)
        self.assertIn("dc.w $00f0,$00cc,$0040,$00ca", asm)

    def test_normal_history_kernel_selects_single_word_normal_target(self):
        asm = (ROOT / "src/rom/line_a_bit_kernel.i").read_text()
        history = asm.split("line_a_bit_history_trial:", 1)[1].split(
            "line_a_history_minterms:", 1)[0]
        normal = history.split(".history_normal_target:", 1)[1]
        self.assertIn("btst #6,5(a4)", asm)
        self.assertIn("move.w #$01cc,$40(a6)", normal)
        self.assertIn("move.w #0,$62(a6)", normal)
        self.assertIn("move.w #0,$66(a6)", normal)
        self.assertIn("move.w #0,$42(a6)", normal)
        self.assertIn("move.w #$0041,d5", normal)
        self.assertLess(normal.index("move.w #$0041,d5"),
                        normal.index("movea.l #$ff7800,a2"))
        self.assertIn("move.w #$0082,d5", history)

    def test_no_dma_prime_loads_bdat_in_normal_mode_then_starts_line_mode(self):
        asm = (ROOT / "src/rom/line_a_bit_kernel.i").read_text()
        history = asm.split("line_a_bit_history_trial:", 1)[1].split(
            "line_a_history_minterms:", 1)[0]
        prime = history.split(".history_no_dma_2800:", 1)[1].split(
            ".history_prime_settle:", 1)[0]
        self.assertIn("move.w #0,$42(a6)", prime)
        self.assertIn("move.w #$2800,$72(a6)", prime)
        self.assertIn("move.w #$d7ff,$72(a6)", prime)
        self.assertIn("move.w #1,$42(a6)", prime)
        self.assertIn("move.w #$00cc,$40(a6)", prime)
        self.assertIn("move.w #$0082,$58(a6)", prime)

    def test_line_hold_kernel_uses_literal_tables_no_dma_prime_and_normal_target(self):
        asm = (ROOT / "src/rom/line_a_bit_kernel.i").read_text()
        hold = asm.split("line_a_bit_line_hold_trial:", 1)[1].split(
            "line_a_history_minterms:", 1)[0]
        self.assertIn("btst #7,5(a4)", asm)
        self.assertIn("move.w #0,$42(a6)", hold)
        self.assertIn("lea line_a_hold_b_patterns(pc),a0", hold)
        self.assertIn("lea line_a_hold_bshifts(pc),a0", hold)
        self.assertIn("lsl.w #8,d1", hold)
        self.assertIn("lsl.w #4,d1", hold)
        self.assertIn("move.w #$00cc,$40(a6)", hold)
        self.assertIn("lsl.w #6,d5", hold)
        self.assertIn("ori.w #2,d5", hold)
        self.assertIn("move.w d5,$58(a6)", hold)
        self.assertIn("move.w #$01cc,$40(a6)", hold)
        self.assertIn("move.w #$0041,d5", hold)
        self.assertLess(hold.index("move.w #$0041,d5"),
                        hold.index("movea.l #$ff7800,a2"))
        self.assertIn("dc.w $0001,$8000,$a55a,$1248", asm)
        self.assertIn("dc.w 0,1,7,15", asm)


    def test_kernel_initializes_inputs_and_uses_the_kind46_observer(self):
        asm = (ROOT / "src/rom/line_a_bit_kernel.i").read_text()
        self.assertIn("line_a_bit_trial:", asm)
        self.assertIn("move.w #1023,d7", asm)
        self.assertIn("move.w #15,d7", asm)
        self.assertIn("move.w #81,d7", asm)
        self.assertIn("move.w d0,$11050", asm)
        self.assertIn("move.w #$ffff,$44(a6)", asm)
        self.assertIn("move.w #$ffff,$46(a6)", asm)
        self.assertIn("move.l #$11000,$48(a6)", asm)
        self.assertIn("move.l #$16000,$4c(a6)", asm)
        self.assertIn("move.l #-80,$50(a6)", asm)
        self.assertIn("move.l #$10000,$54(a6)", asm)
        self.assertIn("ori.w #$0bca,d0", asm)
        self.assertIn("move.w #$0001,$42(a6)", asm)
        self.assertIn("move.w #$0042,d5", asm)
        self.assertIn("move.w #$0082,d5", asm)
        self.assertIn("move.w #$8000,d1", asm)
        self.assertIn("lsr.w d0,d1", asm)
        self.assertIn("move.w d1,$74(a6)", asm)
        self.assertIn("move.w #0,$70(a6)", asm)
        self.assertIn("move.w #$ffff,$72(a6)", asm)
        self.assertIn("clr.w $72(a6)", asm)
        self.assertIn("source_lengths_words=dict(a=16, b=16, c=82)",
                      (ROOT / "build_line_a_bit_rom.py").read_text())
        self.assertIn("destination_length_words=1024",
                      (ROOT / "build_line_a_bit_rom.py").read_text())
        self.assertIn("lsl.w #8,d0", asm)
        self.assertIn("lsl.w #4,d0", asm)
        legacy = asm.split("; Truth-control extension", 1)[0]
        self.assertNotIn("lsl.w #12,d0", legacy)
        self.assertNotIn("#$0081", asm)
        self.assertIn("lea line_a_bit_observer_values(pc),a2", asm)
        self.assertIn("lea line_a_bit_scratch_regions(pc),a3", asm)
        self.assertIn("movea.l #$ff7800,a2", asm)
        self.assertIn("dc.l $18000", asm)
        self.assertIn("dc.w 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0", asm)
        self.assertIn("move.l a3,-(sp)", asm)
        self.assertIn("move.l (sp)+,a3", asm)
        self.assertIn("move.l d7,-(sp)", asm)
        self.assertIn("move.l (sp)+,d7", asm)

    def test_truth_control_matrix_is_bounded_and_uses_reserved_marker(self):
        rows = suite.line_a_truth_control_rows()
        self.assertEqual(len(rows), 2048)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertLessEqual(len(rows), suite.MAX_PAYLOAD_ROWS)
        self.assertEqual({row[1] for row in rows}, set(range(8)))
        self.assertEqual({row[2] for row in rows}, set(range(16, 32)))
        self.assertEqual({row[3] for row in rows}, {0, 1})
        self.assertEqual({row[4] for row in rows}, {0})
        self.assertEqual({row[5] for row in rows}, set(range(8)))
        self.assertEqual(len(suite.line_a_bit_rows()), 1536)

        metadata = suite.truth_control_metadata()
        self.assertEqual(metadata["a_pattern_values"],
                         ["0x8000", "0x4000", "0x2000", "0x1000",
                          "0x0800", "0x0400", "0x2800", "0x2801"])
        self.assertEqual([int(row["value"], 16) for row in metadata["minterms"]],
                         [0x00, 0xff, 0xf0, 0xcc, 0x33, 0xaa, 0x40, 0xca])

    def test_truth_control_kernel_preserves_phase_for_bshift_and_observer(self):
        asm = (ROOT / "src/rom/line_a_bit_kernel.i").read_text()
        truth = asm.split("line_a_bit_truth_trial:", 1)[1].split(
            "line_a_bit_observer_values:", 1)[0]
        self.assertIn("btst #4,5(a4)", asm)
        self.assertIn("bne.w line_a_bit_truth_trial", asm)
        self.assertIn("move.w (sp),d0", truth)
        self.assertIn("lsl.w #8,d0", truth)
        self.assertIn("lsl.w #4,d0", truth)
        self.assertNotIn("lsl.w #12,d0", truth)
        self.assertIn("ori.w #$0001,d0", truth)
        self.assertLess(truth.index("move.w #$8000,$74(a6)"),
                        truth.index("move.w (a0),$74(a6)"))
        self.assertLess(truth.index("move.w #$ffff,$72(a6)"),
                        truth.index("move.w d0,$42(a6)"))
        self.assertLess(truth.index("clr.w $72(a6)"),
                        truth.index("move.w d0,$42(a6)"))
        self.assertIn("move.w #$0082,d5", truth)
        self.assertIn("move.l #$11000,$48(a6)", truth)
        self.assertIn("move.w (sp)+,6(a4)", truth)
        self.assertIn("movea.l #$ff7800,a2", truth)
        self.assertIn("move.w (a0),$74(a6)", truth)
        self.assertIn("ori.w #$0b00,d0", truth)
        self.assertIn("dc.w $0000,$00ff,$00f0,$00cc,$0033,$00aa,$0040,$00ca", asm)
        metadata = suite.truth_control_metadata()
        self.assertEqual(metadata["controls"]["custom_register_write_order"], [
            "BLTADAT=$8000 seed", "BLTADAT=selected pattern",
            "BLTCON0=0x0b00|minterm", "BLTBDAT=selected B data",
            "BLTCON1=0x0001 or 0x1001 from saved BSHIFT phase"])
        self.assertEqual(metadata["controls"]["ca_bshift0_reproduction"]["a_patterns"],
                         ["0x2000", "0x0800", "0x2800", "0x2801"])


if __name__ == "__main__":
    unittest.main()












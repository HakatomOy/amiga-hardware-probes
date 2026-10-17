import importlib.util
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "copper_start_busy_rom", ROOT / "build_copper_start_busy_rom.py")
suite = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(suite)


class CopperStartBusyRomTests(unittest.TestCase):
    def test_descriptor_matrix_is_unique_bounded_and_complete(self):
        rows = suite.copper_start_busy_rows()
        self.assertEqual(len(rows), 528)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertLessEqual(len(rows), suite.MAX_ROWS)
        self.assertEqual({row[0] for row in rows}, {50})
        self.assertEqual({row[1] for row in rows}, {0, 1, 2})
        self.assertEqual({row[2] for row in rows}, set(range(8)))
        self.assertEqual({row[3] for row in rows}, set(range(11)))
        self.assertEqual({row[4] for row in rows}, {0})
        self.assertEqual({row[5] for row in rows}, {0, 1})
        self.assertEqual(suite.GATE_HPOS,
                         (0x10, 0x18, 0x20, 0x28, 0x30, 0x38,
                          0x40, 0x48, 0x50, 0x58, 0x60))

    def test_bltsize_words_decode_to_requested_widths(self):
        sizes = (0x0041, 0x0048, 0x0050)
        for width_index, size in enumerate(sizes):
            height = (size >> 6) & 0x3ff
            width = size & 0x3f or 64
            self.assertEqual((height, width), (1, suite.WIDTHS[width_index]))

    def test_rom_observer_preserves_raw_read_train_and_record_contract(self):
        kernel = (ROOT / "src/rom/copper_start_busy_kernel.i").read_text()
        self.assertIn("copper_start_busy_trial:", kernel)
        self.assertIn("move.w #$4261,(a0)+", kernel)
        self.assertIn("move.w #$fffe,(a0)+", kernel)
        self.assertIn("move.w #$7ffe,(a0)+", kernel)
        self.assertIn("move.w #$01fe,(a0)+", kernel)
        self.assertIn("move.w #$0058,(a0)+", kernel)
        self.assertIn("jsr $ffc200", kernel)
        self.assertIn("move.w #$ffff,16(a4)", kernel)
        self.assertIn("dbra d7,.sync_leave64", kernel)
        self.assertIn("dbra d7,.sync_line64", kernel)
        self.assertIn("dbra d7,.sync_hpos", kernel)
        observer = (ROOT / "src/rom/copper_start_busy_observer.i").read_text()
        self.assertIn("copper_start_busy_observer:", observer)
        self.assertIn("move.w d5,a2", observer)
        self.assertEqual(observer.count("move.w d5,d6"), 4)
        self.assertEqual(observer.count("andi.w #$00ff,d6"), 2)
        self.assertIn("move.w d5,d6\n        andi.w #$00ff,d6", observer)
        self.assertIn("move.w $002(a6),d0\n"
                      "        move.w $002(a6),d1\n"
                      "        move.w $002(a6),d2\n"
                      "        move.w $002(a6),d3\n"
                      "        move.w $002(a6),d4\n"
                      "        move.w $002(a6),d5\n"
                      "        move.w $002(a6),d6\n"
                      "        move.w $002(a6),d7", observer)
        train = observer.split(".train_ready:", 1)[1].split(".gate_timeout:", 1)[0]
        self.assertNotIn("(a4)", train.split("move.w $006(a6),a3", 1)[0])
        self.assertIn("movem.w d0-d7,20(a4)", train)
        self.assertIn("move.w $01e(a6),18(a4)", observer)
        self.assertIn("move.w (a0),36(a4)", kernel)
        self.assertIn("move.w 30(a0),38(a4)", kernel)
        self.assertIn("dbra d7,.train_poll", observer)
        self.assertIn("dbra d7,.marker_poll", kernel)

    def test_dispatch_and_rom_slot_are_wired_with_dma_start_after_sync(self):
        source = (ROOT / "src/rom/experiment.asm").read_text()
        self.assertIn("cmpi.w #50,(a4)\n        beq .copper_start_busy", source)
        self.assertIn(".copper_start_busy:\n        jsr copper_start_busy_trial", source)
        self.assertIn('include "copper_start_busy_kernel.i"', source)
        edge = (ROOT / "src/rom/edge_kernel.asm").read_text()
        self.assertIn("dcb.b $ffc200-*,0\n        include \"copper_start_busy_observer.i\"", edge)
        self.assertIn("dcb.b $ffc600-*,0", edge)
        kernel = (ROOT / "src/rom/copper_start_busy_kernel.i").read_text()
        self.assertLess(kernel.index(".sync_ready:"), kernel.index("move.w d2,$96(a6)"))
        self.assertLess(kernel.index("move.w d2,$96(a6)"), kernel.index("jsr $ffc200"))


if __name__ == "__main__":
    unittest.main()

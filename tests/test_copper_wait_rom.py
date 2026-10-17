import unittest
from pathlib import Path
import re

import build_copper_wait_rom as suite


ROOT = Path(__file__).resolve().parents[1]


class CopperWaitRomTests(unittest.TestCase):
    def test_exact_kind47_matrix_and_limits(self):
        rows = suite.copper_wait_rows()
        self.assertEqual(len(rows), 1024)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual({row[1] for row in rows}, set(range(4)))
        self.assertEqual({row[2] for row in rows}, set(range(8)))
        self.assertEqual({row[3] for row in rows}, {0, 1})
        self.assertEqual({row[4] for row in rows}, set(range(8)))
        self.assertEqual({row[5] for row in rows}, {0, 1})
        self.assertLessEqual(len(rows), suite.MAX_PAYLOAD_ROWS)

    def test_unrolled_control_uses_same_matrix_and_variant_bit3(self):
        rows = suite.copper_wait_rows(unrolled=True)
        self.assertEqual(len(rows), 1024)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual({row[2] for row in rows}, set(range(8, 16)))
        self.assertEqual({row[2] & 7 for row in rows}, set(range(8)))

        rom = (ROOT / "src/rom/edge_kernel.asm").read_text()
        quiet = rom.split("copper_wait_unrolled_quiet:", 1)[1].split(
            "copper_wait_unrolled_reads:", 1)[0]
        reads = rom.split("copper_wait_unrolled_reads:", 1)[1]
        self.assertIn("rept 512", quiet)
        self.assertIn("rept 256", reads)
        self.assertNotIn("dbra", quiet.lower())
        self.assertNotIn("dbra", reads.lower())
        self.assertIn("jmp $ff7a00", rom)
        self.assertIn("jmp $ff7e10", rom)

    def test_no_blit_control_uses_same_matrix_and_two_word_noop(self):
        rows = suite.copper_wait_rows(no_blit=True)
        self.assertEqual(len(rows), 1024)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual({row[2] for row in rows}, set(range(16, 24)))
        self.assertEqual({row[2] & 7 for row in rows}, set(range(8)))
        unrolled_rows = suite.copper_wait_rows(unrolled=True, no_blit=True)
        self.assertEqual({row[2] for row in unrolled_rows}, set(range(24, 32)))

        kernel = (ROOT / "src/rom/copper_wait_kernel.i").read_text()
        slot = kernel.split(".no_blit:", 1)[1].split(".blit_slot_ready:", 1)[0]
        self.assertIn("move.w #$01fe,(a0)+", slot)
        self.assertIn("move.w #$0000,(a0)+", slot)
        self.assertIn("move.w #$0058,(a0)+", kernel)
        self.assertIn("move.w #$0050,(a0)+", kernel)
        self.assertIn("btst #4,5(a4)", kernel)

    def test_cpu_launch_control_is_unrolled_and_uses_variant_bit5(self):
        rows = suite.copper_wait_rows(unrolled=True, cpu_launch=True)
        self.assertEqual(len(rows), 1024)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual({row[2] for row in rows}, set(range(40, 48)))
        self.assertEqual({row[2] & 7 for row in rows}, set(range(8)))
        with self.assertRaises(ValueError):
            suite.copper_wait_rows(cpu_launch=True)
        with self.assertRaises(ValueError):
            suite.copper_wait_rows(unrolled=True, no_blit=True, cpu_launch=True)

        kernel = (ROOT / "src/rom/copper_wait_kernel.i").read_text()
        self.assertIn("btst #5,5(a4)", kernel)
        self.assertIn("move.w #$4221,(a0)+", kernel)
        self.assertIn("move.w #$fffe,(a0)+", kernel)
        self.assertIn("andi.w #$006a,d3", kernel)
        edge = (ROOT / "src/rom/edge_kernel.asm").read_text()
        loop = edge.split("copper_wait_cpu_loop:", 1)[1].split(
            "; Fixed code paths", 1)[0]
        self.assertIn("btst #5,d3", loop)
        self.assertIn("jmp $ffc000", loop)
        stub = edge.split("copper_wait_cpu_launch:", 1)[1]
        self.assertIn("dcb.b $ffc000-*,0", edge)
        self.assertIn("cmpi.w #$4200,d0", stub)
        self.assertIn("cmpi.w #$0030,d0", stub)
        self.assertIn("move.w 6(a6),14(a4)", stub)
        self.assertIn("move.w #$0050,$58(a6)", stub)
        self.assertLess(stub.index("move.w 6(a6),14(a4)"),
                        stub.index("move.w #$0050,$58(a6)"))
        self.assertEqual(suite.CPU_LAUNCH_STUB_SIZE, 0x3a)
        self.assertIn("jmp $ff7a00", stub)
        self.assertIn("jmp $ff7e10", stub)

    def test_cpu_finish_sweep_crosses_widths_and_uses_nop_launch_pad(self):
        rows = suite.copper_wait_rows(unrolled=True, finish_sweep=True)
        self.assertEqual(len(rows), 2048)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertLessEqual(len(rows), suite.MAX_PAYLOAD_ROWS)
        self.assertEqual({row[1] for row in rows}, set(range(16)))
        self.assertEqual({row[2] for row in rows}, set(range(104, 108)))
        self.assertEqual({row[3] for row in rows}, {0, 1})
        self.assertEqual({row[4] for row in rows}, set(range(8)))
        self.assertEqual({row[5] for row in rows}, {0, 1})
        self.assertEqual({row[1] >> 2 for row in rows}, set(range(4)))
        self.assertEqual({row[1] & 3 for row in rows}, set(range(4)))
        # Independently decode the hardware BLTSIZE words expected for every
        # descriptor width. The low six bits encode width (zero means 64),
        # while the upper ten bits encode height.
        sizes_by_width = (0x0041, 0x0044, 0x0048, 0x0050)
        for row in rows:
            target = row[1]
            width_index = target >> 2
            size_word = sizes_by_width[width_index]
            decoded_height = (size_word >> 6) & 0x3ff
            decoded_width = size_word & 0x3f or 64
            self.assertEqual((decoded_height, decoded_width),
                             (1, (1, 4, 8, 16)[width_index]))
        with self.assertRaises(ValueError):
            suite.copper_wait_rows(finish_sweep=True)
        with self.assertRaises(ValueError):
            suite.copper_wait_rows(unrolled=True, finish_sweep=True, no_blit=True)

        kernel = (ROOT / "src/rom/copper_wait_kernel.i").read_text()
        self.assertIn("btst #6,5(a4)", kernel)
        self.assertIn("move.w #$0041,d5", kernel)
        self.assertIn("move.w #$0044,d5", kernel)
        self.assertIn("move.w #$0048,d5", kernel)
        self.assertIn("move.w #$0050,d5", kernel)
        self.assertIn("move.w d2,14(a4)", kernel)
        self.assertIn("move.w 6(a0),38(a4)", kernel)
        self.assertIn("move.w 14(a0),38(a4)", kernel)
        self.assertIn("move.w 30(a0),38(a4)", kernel)
        self.assertIn("move.w (a0),38(a4)", kernel)
        self.assertIn("andi.w #$006a,d3", kernel)
        self.assertIn("move.w #$4261,d0", kernel)
        self.assertIn("move.w #$4205,(a0)+", kernel)
        self.assertIn("btst #6,5(a4)\n        beq.s .cpu_launch_initial_wait", kernel)
        edge = (ROOT / "src/rom/edge_kernel.asm").read_text()
        loop = edge.split("copper_wait_cpu_loop:", 1)[1].split(
            "; Fixed code paths", 1)[0]
        self.assertIn("btst #6,d3", loop)
        self.assertIn("jmp $ffc100", loop)
        stub = edge.split("copper_wait_finish_sweep:", 1)[1]
        self.assertIn("move.w 0(a0,d0.w),d0", stub)
        self.assertIn("cmpi.w #$0010,d0", stub)
        self.assertIn("move.w 6(a6),d2\n        move.w d5,$58(a6)", stub)
        self.assertNotIn("move.w d2,14(a4)", stub)
        self.assertIn("dc.w .pad0-.pad_table", stub)
        self.assertIn("dcb.b $ffc200-*,0", stub)
        self.assertEqual(suite.CPU_FINISH_SWEEP_STUB_SIZE, 0x100)

    def test_descriptor_and_observer_contract(self):
        source = (ROOT / "src/rom/experiment.asm").read_text()
        dispatch = source.split("main:", 1)[1].split(".recorded:", 1)[0]
        self.assertIn("cmpi.w #47,(a4)\n        beq .copper_wait", dispatch)
        kernel = (ROOT / "src/rom/copper_wait_kernel.i").read_text()
        self.assertIn("move.w 6(a6),EVBEAM2(a5)", kernel)
        self.assertIn("move.w $01e(a6),d0", kernel)
        self.assertIn("move.w $002(a6),20(a4)", kernel)
        self.assertIn("move.w #$fffe,(a0)+", kernel)
        self.assertIn("move.w #$7ffe,(a0)+", kernel)
        self.assertEqual(kernel.count("move.w #$7ffe,(a0)+"), 2)
        self.assertIn("move.w #2,$02e(a6)", kernel)
        self.assertIn("andi.w #$006a,d3", kernel)
        self.assertIn("movem.l d0-d7/a0-a3,-(sp)", kernel)
        self.assertIn("movem.l (sp)+,d0-d7/a0-a3", kernel)
        size_word = int(re.search(
            r"move\.w #\$(\w+),\(a0\)\+\s*bra\.s \.blit_slot_ready", kernel).group(1), 16)
        height = (size_word >> 6) & 0x3ff
        width = size_word & 0x3f or 64
        self.assertEqual((height, width), (1, 16))
        self.assertIn("clr.w 32(a4)", kernel)
        self.assertIn("move.w #1,32(a4)", kernel)
        clear_request = kernel.index("move.w #$7fff,$9c(a6)")
        unmask = kernel.index("move.w #$2000,sr")
        self.assertLess(clear_request, unmask)
        critical = kernel.split("jsr $ff7900", 1)[0]
        self.assertNotIn("$02(a6)", critical)
        rom = (ROOT / "src/rom/edge_kernel.asm").read_text()
        observer = rom.split("dcb.b $ff7900-*,0", 1)[1]
        self.assertIn("copper_wait_cpu_loop:", observer)
        self.assertIn("move.w $18000,d0", observer)


if __name__ == "__main__":
    unittest.main()

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "cia_cpu_irq_rom", ROOT / "build_cia_cpu_irq_rom.py")
suite = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(suite)


class CiaCpuIrqRomTests(unittest.TestCase):
    def test_descriptor_matrix_is_unique_bounded_and_complete(self):
        rows = suite.cia_cpu_irq_rows()
        self.assertEqual(len(rows), 1536)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertLessEqual(len(rows), suite.MAX_ROWS)
        self.assertEqual({row[0] for row in rows}, {51})
        self.assertEqual({row[1] for row in rows}, {0, 1, 2, 3})
        self.assertEqual({row[2] for row in rows}, {0, 1, 2})
        self.assertEqual({row[3] for row in rows}, set(range(4)))
        self.assertEqual({row[4] for row in rows}, set(range(16)))
        self.assertEqual({row[5] for row in rows}, {0, 1})

    def test_matrix_rejects_invalid_or_oversized_selections(self):
        with self.assertRaisesRegex(ValueError, "targets"):
            suite.cia_cpu_irq_rows(targets=(4,))
        with self.assertRaisesRegex(ValueError, "sources"):
            suite.cia_cpu_irq_rows(sources=(0, 0))
        with self.assertRaisesRegex(ValueError, "phase"):
            suite.cia_cpu_irq_rows(phases=(4,))
        with self.assertRaisesRegex(ValueError, "event_offsets"):
            suite.cia_cpu_irq_rows(event_offsets=(16,))
        with self.assertRaisesRegex(ValueError, "repeats"):
            suite.cia_cpu_irq_rows(repeats=3)

    def test_metadata_keeps_clock_units_and_irq_record_semantics_explicit(self):
        meta = suite.metadata(suite.cia_cpu_irq_rows(), 2)
        self.assertIn("E-clock ticks", meta["sources"][0]["timing"])
        self.assertIn("color clocks", meta["sources"][1]["timing"])
        self.assertIn("captured beam values", meta["event_offset"]["warning"])
        self.assertEqual(meta["observer"]["record_offsets"]["a1_low_at_irq"], 22)
        self.assertEqual(meta["observer"]["record_offsets"]["status"], 32)
        self.assertEqual(meta["observer"]["record_offsets"]["post_start_vhposr"], 12)
        self.assertEqual(meta["observer"]["record_offsets"]["pre_start_vhposr"], 14)
        self.assertEqual(meta["sources"][2]["level"], 6)
        self.assertEqual(meta["observer"]["timer_a"]["cia_b"]["icr"], 0xbfdd00)
        self.assertEqual(meta["observer"]["timer_a"]["cia_b"]["cra"], 0xbfde00)
        self.assertEqual(meta["observer"]["status"],
                         {"0": "exactly one event received", "1": "event count was not exactly one"})
        self.assertIn("CHIP RAM", meta["targets"][2]["storage"])
        self.assertIn("bit1", meta["target_bits"])

    def test_kernel_builds_disjoint_copper_and_cia_sources_and_syncs_before_release(self):
        kernel = (ROOT / "src/rom/cia_cpu_irq_kernel.i").read_text()
        self.assertIn("cia_cpu_irq_trial:", kernel)
        self.assertIn("move.l #$ffc900,$68", kernel)
        self.assertIn("move.l #$ffc940,$6c", kernel)
        self.assertIn("move.l #$ffc980,$78", kernel)
        self.assertIn("addi.w #16,d0", kernel)
        self.assertIn("addi.w #$4151,d0", kernel)
        self.assertIn("move.w #$fffe,(a0)+", kernel)
        self.assertIn("move.w #$009c,(a0)+", kernel)
        self.assertIn("move.w #$8010,(a0)+", kernel)
        self.assertIn("clr.w 6(a4)", kernel)
        self.assertLess(kernel.index("jsr sync_beam"), kernel.index("jsr $ffc600"))
        self.assertIn("move.w d2,14(a4)", kernel)
        self.assertIn("move.w d3,12(a4)", kernel)
        self.assertIn("move.w CIAEVLOOP(a5),20(a4)", kernel)
        self.assertIn("move.w CIAEVPTR(a5),22(a4)", kernel)
        self.assertIn("move.w #1,32(a4)", kernel)
        self.assertIn("jsr $1c000", kernel)
        self.assertIn("subi.l #$0001c100,d0", kernel)
        self.assertIn("subi.l #$0001c200,d0", kernel)
        self.assertIn("cmpi.w #1,EVCOUNT(a5)", kernel)
        self.assertIn("move.b #$7f,$bfed01", kernel)
        self.assertIn("move.w #$01ff,d0", kernel)
        self.assertIn("move.w (a0)+,(a1)+\n        dbra d0,.observer_copy", kernel)
        self.assertLess(kernel.index(".observer_copy:"), kernel.index("jsr sync_beam"))

    def test_common_dispatch_and_fixed_rom_copy_are_integrated(self):
        source = (ROOT / "src/rom/experiment.asm").read_text()
        self.assertIn("cmpi.w #51,(a4)\n        beq .cia_cpu_irq", source)
        self.assertIn(".cia_cpu_irq:\n        jsr cia_cpu_irq_trial", source)
        self.assertIn('include "cia_cpu_irq_kernel.i"', source)
        edge = (ROOT / "src/rom/edge_kernel.asm").read_text()
        self.assertIn('dcb.b $ffc600-*,0\n        include "cia_cpu_irq_observer.i"', edge)

    def test_fixed_observer_runs_rom_loops_without_done_or_beam_poll(self):
        observer = (ROOT / "src/rom/cia_cpu_irq_observer.i").read_text()
        self.assertIn("cia_cpu_irq_observer:", observer)
        self.assertIn("moveq #127,d1", observer)
        self.assertIn("move.b #$19,$bfee01", observer)
        cia_start = observer.index("move.b #$19,$bfee01")
        cia_post = observer.index("move.w 6(a6),d3", cia_start)
        self.assertLess(cia_start, cia_post)
        self.assertLess(cia_post, observer.index("move.w #$2000,sr", cia_post))
        self.assertIn("move.w #$8280,$96(a6)", observer)
        self.assertIn("move.w #0,$88(a6)", observer)
        copjmp = observer.index("move.w #0,$88(a6)")
        copper_post = observer.index("move.w 6(a6),d3", copjmp)
        self.assertLess(copper_post, observer.index("move.w #$2000,sr", copper_post))
        self.assertIn("cia_cpu_nop_loop:", observer)
        self.assertIn("nop\n        dbra d1,cia_cpu_nop_loop", observer)
        self.assertIn("cia_cpu_move_loop:", observer)
        self.assertIn("move.b d0,-(a1)\n        dbra d1,cia_cpu_move_loop", observer)
        self.assertNotIn("DONE", observer)
        self.assertNotIn("$006(a6)", observer)
        self.assertIn("dcb.b $ffc700-*,0", observer)
        self.assertIn("dcb.b $ffc800-*,0", observer)
        self.assertIn("dcb.b $ffc900-*,0", observer)
        self.assertIn("dcb.b $ffc940-*,0", observer)
        self.assertIn("dcb.b $ffca00-*,0", observer)
        self.assertIn("lea cia_cpu_nop_loop(pc),a2", observer)
        self.assertIn("lea cia_cpu_move_loop(pc),a2", observer)
        self.assertNotIn("jmp $ffc", observer)
        self.assertIn("move.w #$0008,$9c(a6)", observer)
        self.assertIn("move.w #$0008,$9a(a6)", observer)
        self.assertIn("move.w #$0010,$9c(a6)", observer)
        self.assertIn("move.b #$81,$bfdd00", observer)
        self.assertIn("move.w #$e000,$9a(a6)", observer)
        self.assertIn("move.b #$19,$bfde00", observer)
        self.assertIn("cia_cpu_irq6:", observer)
        self.assertIn("move.b $bfdd00,d0", observer)
        self.assertIn("move.w #$2000,$9c(a6)", observer)
        self.assertIn("move.w #$2000,$9a(a6)", observer)
        self.assertIn("move.w #$0010,$9a(a6)", observer)
        self.assertEqual(observer.count("addq.w #1,EVCOUNT(a5)"), 3)
        self.assertNotIn("jsr $ffc", observer)

    def test_handler_records_timestamp_before_saving_registers(self):
        observer = (ROOT / "src/rom/cia_cpu_irq_observer.i").read_text()
        for label in ("cia_cpu_irq2:", "cia_cpu_irq3:"):
            body = observer.split(label, 1)[1]
            self.assertTrue(body.lstrip().startswith("move.w 6(a6),EVBEAM(a5)"))
            self.assertLess(body.index("move.w 6(a6),EVBEAM(a5)"),
                            body.index("move.l 2(sp),EVPC(a5)"))
            self.assertLess(body.index("move.l 2(sp),EVPC(a5)"),
                            body.index("movem.l d0,-(sp)") if "movem.l d0,-(sp)" in body
                            else body.index("rte"))
        self.assertIn("move.b $bfed01,d0", observer)
        self.assertIn("move.w #$0010,$9c(a6)", observer)


if __name__ == "__main__":
    unittest.main()

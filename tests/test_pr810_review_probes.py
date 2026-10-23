import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import build_cia_review_rom as mask
import build_cia_zero_autostart_rom as zero
import build_cia_zero_pulse_rom as pulse
import build_handoff_destination_review_rom as destination
import build_irq_stage_rom as base


class ReviewProbeTests(unittest.TestCase):
    def test_descriptor_coverage_and_unique_ids(self):
        for module, count, kind in [(mask, 32, 125), (zero, 288, 126),
                                    (destination, 384, 127), (pulse, 288, 128)]:
            rows = module.trials()
            self.assertEqual(len(rows), count)
            self.assertEqual(len(set(rows)), count)
            self.assertEqual({r[0] for r in rows}, {kind})

    def test_mask_probe_does_not_acknowledge_icr_on_stale_ir_path(self):
        critical = mask.KERNEL.split('.no_ack:')[1].split('.serial_wait:')[0]
        self.assertNotIn('tst.b $d00(a0)', critical)
        self.assertIn('move.w d7,$9c(a6)', critical)
        self.assertIn('move.b #$88,$d00(a0)', critical)

    def test_zero_probe_pairs_timer_registers_without_changing_gap(self):
        kernel = zero.kernel()
        self.assertIn('lea $200(a0),a0', kernel)
        self.assertIn('lea -$100(a1),a1', kernel)
        for gap in range(8):
            body = kernel.split(f'.gap{gap}:')[1].split('bra.w .done')[0]
            self.assertEqual(body.count('        nop\n'), gap)
            self.assertLess(body.index('clr.b $500(a0)'), body.index('move.b (a1),d0'))


if __name__ == '__main__':
    unittest.main()

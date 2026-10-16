from __future__ import annotations

import importlib.util
import math
import struct
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "analyze_bzero_bus.py"
SPEC = importlib.util.spec_from_file_location("analyze_bzero_bus", TOOL)
analyzer = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(analyzer)


def sample(*, valid: bool = False, address: int = 0, read: bool = False,
           bbusy: int = 0, bzero: int = 0, clock: int = 0,
           regen: bool = True, uds: bool = True, dtack: bool = True) -> int:
    word = clock
    if not valid or not regen:
        word |= 1 << analyzer.AS_N
    if read:
        word |= 1 << analyzer.RW
    if not valid or not uds:
        word |= 1 << analyzer.UDS_N
    if not valid or not dtack:
        word |= 1 << analyzer.DTACK_N
    if bbusy:
        word |= 1 << analyzer.D14
    if bzero:
        word |= 1 << analyzer.D13
    if not valid or not regen:
        word |= 1 << analyzer.REGEN_N
    for bit, channel in analyzer.ADDRESS_BITS.items():
        if address & (1 << bit):
            word |= 1 << channel
    return word


def packet(words: list[int], *, declared_payload: int | None = None) -> bytes:
    payload = struct.pack(f"<{len(words)}I", *words)
    wh = bytearray(140)
    struct.pack_into("<IIII", wh, 0, 140, 6, 1, len(words))
    struct.pack_into("<dd", wh, 32, 0.25e-9, 0.0)
    wh[112:128] = b"LA\0" + bytes(13)
    dh = bytearray(16)
    struct.pack_into("<IHHII", dh, 0, 16, 5, 4,
                     len(payload) if declared_payload is None else declared_payload, 0)
    body = bytes(wh) + bytes(dh) + payload
    return b"RG03" + struct.pack("<QI", len(body) + 16, 1) + body


class BzeroBusTests(unittest.TestCase):
    def test_inferred_period_and_jitter(self) -> None:
        words = []
        level = 0
        for i in range(1000):
            if i % 20 == 0:
                level ^= 1
            words.append(sample(clock=level))
        result = analyzer.decode_words(words, sample_interval_s=1e-9)
        self.assertEqual(result["cpu_clock"]["period_samples"], 40)
        self.assertAlmostEqual(result["cpu_clock"]["estimated_cpu_hz"], 25_000_000)
        with self.assertRaisesRegex(ValueError, "jitter"):
            analyzer.infer_cpu_period([0, 1] * 20 + [0] * 5 + [1, 0] * 10,
                                      max_jitter_fraction=0.05)

    def test_nominal_clock_scale_is_labeled_estimated(self) -> None:
        words = [sample(clock=(i // 10) & 1) for i in range(500)]
        result = analyzer.decode_words(words, nominal_cpu_reference_hz=7_000_000)
        self.assertAlmostEqual(result["cpu_clock"]["sample_interval_s"], 1 / (20 * 7_000_000))
        self.assertIn("not an independent", result["cpu_clock"]["scale_source"])
        with self.assertRaisesRegex(ValueError, "exactly one"):
            analyzer.decode_words(words)

    def test_reads_dmaconr_only_inside_fully_qualified_stable_window(self) -> None:
        words = [sample(clock=(i // 5) & 1) for i in range(1000)]
        for i in range(200, 240):
            words[i] = sample(valid=True, address=0x002, read=True, bbusy=1,
                              bzero=1, clock=(i // 5) & 1)
        # A one-sample qualifier glitch and a transfer without DTACK are ignored.
        words[300] = sample(valid=True, address=0x002, read=True, bzero=1,
                            clock=(300 // 5) & 1)
        for i in range(400, 440):
            words[i] = sample(valid=True, address=0x002, read=True, bbusy=0,
                              bzero=0, clock=(i // 5) & 1, dtack=False)
        result = analyzer.decode_words(words, nominal_cpu_reference_hz=7_000_000)
        reads = [w for w in result["custom_windows"] if w.get("register") == "DMACONR"]
        self.assertEqual(len(reads), 1)
        self.assertEqual(reads[0]["address_low9"], 0x002)
        bits = reads[0]["data_bits"]
        self.assertEqual(bits["BBUSY_D14"]["level"], 1)
        self.assertTrue(bits["BBUSY_D14"]["stable"])
        self.assertEqual(bits["BZERO_D13"]["level"], 1)
        self.assertTrue(bits["BZERO_D13"]["stable"])
        self.assertGreaterEqual(reads[0]["start_cpu_cycle"], 0)

    def test_dmaconr_reports_data_transitions_without_collapsing_them(self) -> None:
        words = [sample(clock=(i // 5) & 1) for i in range(1000)]
        for i in range(200, 240):
            words[i] = sample(valid=True, address=0x002, read=True, bbusy=1,
                              bzero=1, clock=(i // 5) & 1)
        words[211] &= ~(1 << analyzer.D13)
        result = analyzer.decode_words(words, sample_interval_s=1e-9)
        window = next(w for w in result["custom_windows"] if w.get("register") == "DMACONR")
        zero = window["data_bits"]["BZERO_D13"]
        self.assertFalse(zero["stable"])
        self.assertIsNone(zero["level"])
        self.assertEqual((zero["first_level"], zero["last_level"]), (1, 1))
        self.assertEqual(zero["transitions"], [
            {"sample_offset": 11, "cpu_cycle_offset": (200 + 11 - analyzer.rising_edges(words, 0)[0]) / result["cpu_clock"]["period_samples"], "from": 1, "to": 0},
            {"sample_offset": 12, "cpu_cycle_offset": (200 + 12 - analyzer.rising_edges(words, 0)[0]) / result["cpu_clock"]["period_samples"], "from": 0, "to": 1},
        ])

    def test_decodes_bltsize_launch_without_claiming_full_address(self) -> None:
        words = [sample(clock=(i // 10) & 1) for i in range(500)]
        for i in range(120, 150):
            words[i] = sample(valid=True, address=0x058, read=False,
                              clock=(i // 10) & 1)
        result = analyzer.decode_words(words, sample_interval_s=1e-9)
        launches = [w for w in result["custom_windows"] if w["address_low9"] == 0x058]
        self.assertEqual(len(launches), 1)
        self.assertFalse(launches[0]["read"])
        self.assertNotIn("bbusy", launches[0])
        self.assertIn("full custom address is unavailable", result["address_scope"])

    def test_rg03_la_only_known_overstated_payload(self) -> None:
        words = [sample(clock=(i // 5) & 1) for i in range(1000)]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "la.bin"
            path.write_bytes(packet(words, declared_payload=len(words) * 16))
            result = analyzer.analyze(path, sample_interval_s=None,
                                      nominal_cpu_reference_hz=7_000_000,
                                      max_jitter_fraction=0.05)
        self.assertEqual(result["analog_record_count"], 0)
        self.assertEqual(result["la_payload_bytes"], len(words) * 4)
        self.assertEqual(result["la_declared_minus_actual_payload_bytes"], len(words) * 12)

    def test_rejects_invalid_payload_count_or_unknown_format(self) -> None:
        words = [sample(clock=(i // 5) & 1) for i in range(1000)]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.bin"
            good = packet(words)
            path.write_bytes(good[:-4])
            with self.assertRaisesRegex(ValueError, "exceeds file boundary"):
                analyzer.parse_capture(path)
            bad = bytearray(good)
            bad[16 + 140 + 4:16 + 140 + 6] = struct.pack("<H", 9)
            path.write_bytes(bad)
            with self.assertRaisesRegex(ValueError, "expected data format"):
                analyzer.parse_capture(path)
            bad = bytearray(good)
            bad[16 + 4:16 + 8] = struct.pack("<I", 9)
            path.write_bytes(bad)
            with self.assertRaisesRegex(ValueError, "unsupported wave type"):
                analyzer.parse_capture(path)


if __name__ == "__main__":
    unittest.main()

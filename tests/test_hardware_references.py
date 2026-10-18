import hashlib
import json
from pathlib import Path
import unittest

import rom_results


class HardwareReferenceTests(unittest.TestCase):
    def test_versioned_reference_integrity_and_provenance(self):
        manifests = list((Path(__file__).parents[1] / "references").glob("*/manifest.json"))
        self.assertTrue(manifests)
        for path in manifests:
            with self.subTest(reference=path.parent.name):
                manifest = json.loads(path.read_text())
                data = (path.parent / "results.bin").read_bytes()
                metadata, rows = rom_results.decode(data)
                self.assertEqual(hashlib.sha256(data).hexdigest(), manifest["results_sha256"])
                self.assertEqual(metadata, manifest["metadata"])
                self.assertEqual(metadata["source_id"], manifest["source_id"])
                self.assertEqual(len(rows), manifest["record_count"])
                self.assertEqual(len({tuple(r[k] for k in rom_results.FIELDS[:6]) for r in rows}), len(rows))
                if manifest.get("observation_profile") == "copper-busy-kind50":
                    import compare_copper_busy
                    self.assertFalse(any(compare_copper_busy.validate(r) for r in rows))
                else:
                    self.assertFalse(any(r["status"] for r in rows))
                self.assertEqual(len(manifest["test_rom_sha256"]), 64)
                self.assertTrue(manifest["hardware"] and manifest["capture_method"] and manifest["repeatability"])

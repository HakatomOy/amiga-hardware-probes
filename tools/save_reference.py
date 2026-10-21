#!/usr/bin/env python3
"""Version a verified live capture without copying ROM images or historical logs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import rom_results


def save(capture, out, repeatability, limitations, *, session_restoration=None):
    capture, out = Path(capture), Path(out)
    build = json.loads((capture / "build-manifest.json").read_text())
    restore = (dict(session_restoration, scope="session") if session_restoration is not None
               else json.loads((capture / "restoration.json").read_text()))
    if not (restore.get("restored_verified") and restore.get("reset_release_verified")) or restore.get("errors"):
        raise ValueError("Hardware restoration not verified")
    data = (capture / "capture/results.bin").read_bytes()
    meta, rows = rom_results.decode(data)
    if meta["source_id"] != build["source_id"] or len(rows) != build["trial_count"]:
        raise ValueError("Capture does not match build manifest")
    if [[r[f] for f in rom_results.FIELDS[:6]] for r in rows] != build["trials"]:
        raise ValueError("Capture descriptors do not match manifest")
    if meta["timeouts"] or meta["skipped"]:
        raise ValueError("Capture contains failed cases")
    manifest = dict(schema_version=1, reference_id=out.name,
        hardware=dict(machine="PAL A500", cpu="stock 68000", chip_ram_kib=512,
                      slow_ram_kib=512, silicon_revisions="unconfirmed",
                      agnus_vposr=meta["agnus_vposr"], denise_id_raw=meta["denise_id_raw"]),
        capture_method="OneROM live substitution; checksum-protected RBCP; verified restoration",
        original_capture=str(capture), test_rom_sha256=build["rom_sha256"],
        source_id=meta["source_id"], results_sha256=hashlib.sha256(data).hexdigest(),
        record_count=len(rows), metadata=meta, restoration=restore,
        observation_profile=build.get("irq_stage", {}),
        repeatability=repeatability, uncontrolled_state=limitations)
    out.mkdir(parents=True, exist_ok=False)
    (out / "results.bin").write_bytes(data)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--repeatability", required=True)
    p.add_argument("--limitations", required=True)
    a = p.parse_args()
    result = save(a.capture, a.out, a.repeatability, a.limitations)
    print(json.dumps({k: result[k] for k in ("reference_id", "record_count", "results_sha256")}))

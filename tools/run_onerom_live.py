#!/usr/bin/env python3
"""Collect the A500 timing ROM live through One ROM without flashing firmware."""

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROM_BYTES = 0x80000
COMMAND_TIMEOUT_SECONDS = 60
CHILD_START_TIMEOUT_SECONDS = 30
POLL_SECONDS = 0.25
COLLECTOR = ROOT / "collect_rom_usb.py"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256(Path(path).read_bytes())


def _swap_words(data):
    swapped = bytearray(data)
    swapped[0::2] = data[1::2]
    swapped[1::2] = data[0::2]
    return bytes(swapped)


def validate_romdir(romdir):
    """Validate manifest identity, both image hashes, and byte-lane order."""
    romdir = Path(romdir).resolve()
    manifest_path = romdir / "manifest.json"
    normal_path = romdir / "a500-timing-rom.bin"
    swapped_path = romdir / "a500-timing-rom-onerom.bin"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        normal = normal_path.read_bytes()
        swapped = swapped_path.read_bytes()
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load built ROM set from {romdir}: {error}") from error

    source_id = manifest.get("source_id")
    if not isinstance(source_id, str) or re.fullmatch(r"[0-9a-fA-F]{64}", source_id) is None:
        raise ValueError("ROM manifest source_id must be 64 hexadecimal characters")
    if len(normal) != ROM_BYTES or len(swapped) != ROM_BYTES:
        raise ValueError("Both A500 timing ROM images must be exactly 512 KiB")

    normal_hash, swapped_hash = sha256(normal), sha256(swapped)
    if manifest.get("rom_sha256") != normal_hash:
        raise ValueError("a500-timing-rom.bin does not match manifest rom_sha256")
    if manifest.get("onerom_sha256") != swapped_hash:
        raise ValueError("a500-timing-rom-onerom.bin does not match manifest onerom_sha256")
    if swapped != _swap_words(normal):
        raise ValueError("One ROM image is not the word-byte-swapped normal ROM")

    # The result header starts with this magic; its source fingerprint follows
    # the first 24 header bytes and binds the manifest to the actual ROM.
    magic = b"A5RBCP01"
    offsets = [match.start() for match in re.finditer(re.escape(magic), normal)]
    if len(offsets) != 1:
        raise ValueError("Expected exactly one A5RBCP01 header in the normal ROM")
    embedded_source_id = normal[offsets[0] + 24:offsets[0] + 56].hex()
    if embedded_source_id != source_id.lower():
        raise ValueError("ROM manifest source_id does not match the ROM result header")
    return manifest, manifest_path, normal_path, swapped_path, normal, swapped


def _serial_args(serial):
    if serial is None:
        return []
    if not isinstance(serial, str) or not serial.strip() or any(c.isspace() for c in serial):
        raise ValueError("serial must be a non-empty One ROM serial without whitespace")
    if "*" in serial or "?" in serial:
        raise ValueError("serial must be exact; wildcard One ROM selectors cannot be validated")
    return ["--serial", serial]


def _serial_in_info(serial, info):
    """Require an exact serial match in human-readable or JSON info output."""
    text = info.casefold()
    wanted = serial.casefold()
    human_match = re.search(r"\bserial\s*:\s*([^\s,]+)", text)
    if human_match and human_match.group(1).rstrip(".,;") == wanted:
        return True
    try:
        parsed = json.loads(info)
    except json.JSONDecodeError:
        parsed = None

    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.casefold().replace("_", "") in {"serial", "serialnumber"} and isinstance(item, str):
                    yield item
                yield from visit(item)
        elif isinstance(value, list):
            for item in value:
                yield from visit(item)

    return parsed is not None and any(value.casefold() == wanted for value in visit(parsed))


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_logged(onerom, args, serial, out, command_log, runner, label):
    command = [str(onerom), *_serial_args(serial), *map(str, args)]
    try:
        completed = runner(
            command,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        returncode = completed.returncode
    except BaseException as error:
        record = {
            "label": label,
            "command": command,
            "exception": f"{type(error).__name__}: {error}",
        }
        with command_log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
        raise

    record = {
        "label": label,
        "command": command,
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
    }
    with command_log.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")
    _write_json(out / f"command-{label}.json", record)
    if returncode != 0:
        raise RuntimeError(
            f"One ROM command {label!r} failed with status {returncode}: {stderr.strip() or stdout.strip()}"
        )
    return stdout, stderr


def _wait_for_receiver(process, capture, deadline, sleep_fn, monotonic_fn):
    invocation = capture / "invocation.json"
    console_log = capture / "console.log"
    while monotonic_fn() < deadline:
        status = process.poll()
        if status is not None:
            raise RuntimeError(
                f"ROM collector exited before receiver readiness (status {status}); "
                f"see {capture / 'collector.stdout.txt'}"
            )
        if invocation.is_file() and console_log.is_file():
            return
        sleep_fn(min(POLL_SECONDS, max(0, deadline - monotonic_fn())))
    raise TimeoutError("ROM collector did not start its console receiver before the deadline")


def _kill_process_tree(process):
    if os.name == "nt":
        completed = subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if completed.returncode != 0 and process.poll() is None:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or
                               "taskkill could not stop the collector process tree")
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return


def _stop_child(process, child_log, tree_killer):
    try:
        if process is not None and process.poll() is None:
            tree_killer(process)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    tree_killer(process)
                else:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait(timeout=10)
            if os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
    finally:
        if child_log is not None:
            child_log.close()


def collect_live(onerom, romdir, out, timeout=240, serial=None, *, runner=None,
                 popen_factory=None, sleep_fn=time.sleep, monotonic_fn=time.monotonic,
                 tree_killer=None, restore_after=True, session_backup=None):
    """Run a reset-held live-ROM swap and collect a checksum-protected packet.

    Share ``session_backup`` across runs and set ``restore_after=False`` while
    continuing experiments. Restore from that original backup only on the last
    run. Deferred runs record their state honestly and still release reset;
    callers/users can restore the saved backup manually after an error.

    Hardware calls are ordinary ``onerom`` subprocesses. Tests inject a
    command runner and child process factory, so they never touch hardware.
    """
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 3600:
        raise ValueError("timeout must be an integer from 1 through 3600 seconds")
    serial_args = _serial_args(serial)
    (manifest, source_manifest, normal_path, swapped_path,
     normal, swapped) = validate_romdir(romdir)
    onerom = str(onerom)
    out = Path(out).resolve()
    if out.exists():
        raise FileExistsError(f"Output directory already exists: {out}")
    out.mkdir(parents=True, exist_ok=False)
    (out / "capture").parent.mkdir(parents=True, exist_ok=True)
    saved_manifest = out / "build-manifest.json"
    saved_manifest.write_bytes(source_manifest.read_bytes())
    (out / "a500-timing-rom.bin").write_bytes(normal)
    (out / "a500-timing-rom-onerom.bin").write_bytes(swapped)

    invocation = {
        "onerom": onerom,
        "serial": serial,
        "romdir": str(Path(romdir).resolve()),
        "source_id": manifest["source_id"],
        "rom_sha256": sha256(normal),
        "onerom_sha256": sha256(swapped),
        "timeout_seconds": timeout,
        "collector": str(COLLECTOR),
    }
    _write_json(out / "invocation.json", invocation)
    command_log = out / "onerom-commands.jsonl"
    if runner is None:
        runner = subprocess.run
    if popen_factory is None:
        popen_factory = subprocess.Popen
    if tree_killer is None:
        tree_killer = _kill_process_tree

    backup = None
    backup_hash = None
    write_attempted = False
    reset_pin_attempted = False
    process = None
    child_log = None
    restore_report = {
        "write_attempted": False,
        "backup_sha256": None,
        "restore_attempted": False,
        "deferred": not restore_after,
        "session_backup": str(session_backup) if session_backup else None,
        "restored_verified": False,
        "reset_release_verified": False,
        "errors": [],
    }
    primary_error = None

    def command(args, label):
        return _run_logged(onerom, args, serial, out, command_log, runner, label)

    try:
        info, info_stderr = command(["inspect", "info"], "inspect-info")
        (out / "onerom-info.txt").write_text(info + info_stderr, encoding="utf-8")
        if serial is not None and not _serial_in_info(serial, info + info_stderr):
            raise RuntimeError(f"One ROM info did not confirm requested serial {serial!r}")

        backup_path = out / "live-before.bin"
        session_path = Path(session_backup).resolve() if session_backup else None
        if session_path is not None and session_path.exists():
            backup_path.write_bytes(session_path.read_bytes())
        else:
            command(["peek", "--address", "0", "--length", hex(ROM_BYTES),
                     "--output", backup_path], "peek-backup")
            if session_path is not None and session_path != backup_path:
                session_path.parent.mkdir(parents=True, exist_ok=True)
                session_path.write_bytes(backup_path.read_bytes())
        backup = backup_path.read_bytes()
        if len(backup) != ROM_BYTES:
            raise RuntimeError(f"Fresh live ROM backup is {len(backup)} bytes, expected {ROM_BYTES}")
        backup_hash = sha256(backup)
        restore_report["backup_sha256"] = backup_hash
        _write_json(out / "checksums.json", {
            "source_id": manifest["source_id"],
            "normal_rom_sha256": sha256(normal),
            "onerom_rom_sha256": sha256(swapped),
            "fresh_live_backup_sha256": backup_hash,
        })

        reset_pin_attempted = True
        command(["control", "pin", "--pin", "sel_c", "--state", "low"], "reset-assert")
        write_attempted = True
        restore_report["write_attempted"] = True
        command(["control", "poke", "live", "--address", "0", "--input", swapped_path],
                "poke-swapped-rom")
        verified_path = out / "live-swapped-readback.bin"
        command(["peek", "--address", "0", "--length", hex(ROM_BYTES),
                 "--output", verified_path], "peek-swapped-readback")
        actual = verified_path.read_bytes()
        actual_hash = sha256(actual)
        if actual != swapped or actual_hash != manifest["onerom_sha256"]:
            raise RuntimeError("Live swapped-ROM readback failed exact-byte/hash verification")
        _write_json(out / "checksums.json", {
            "source_id": manifest["source_id"],
            "normal_rom_sha256": sha256(normal),
            "onerom_rom_sha256": sha256(swapped),
            "fresh_live_backup_sha256": backup_hash,
            "live_swapped_readback_sha256": actual_hash,
            "live_swapped_readback_matches": True,
        })

        capture = out / "capture"
        child_command = [
            sys.executable, str(COLLECTOR), "--onerom", onerom,
            "--out", str(capture), "--timeout", str(timeout),
            "--manifest", str(saved_manifest),
        ]
        if serial_args:
            child_command += serial_args
        _write_json(out / "collector-invocation.json", {
            "command": child_command,
            "timeout_seconds": timeout,
            "output": str(capture),
        })
        child_log = (out / "collector.stdout.txt").open("wb")
        collection_deadline = monotonic_fn() + timeout
        popen_kwargs = {"stdout": child_log, "stderr": subprocess.STDOUT}
        if os.name != "nt":
            popen_kwargs["start_new_session"] = True
        process = popen_factory(child_command, **popen_kwargs)
        receiver_deadline = min(collection_deadline,
                                monotonic_fn() + CHILD_START_TIMEOUT_SECONDS)
        _wait_for_receiver(process, capture, receiver_deadline, sleep_fn, monotonic_fn)
        command(["control", "pin", "--pin", "sel_c", "--state", "z"], "reset-release-for-run")

        while process.poll() is None and monotonic_fn() < collection_deadline:
            sleep_fn(min(POLL_SECONDS, max(0, collection_deadline - monotonic_fn())))
        if process.poll() is None:
            raise TimeoutError(f"ROM collection exceeded its {timeout}s timeout")
        child_log.close()
        child_log = None
        if process.returncode != 0:
            raise RuntimeError(
                f"ROM collector failed with status {process.returncode}; see {out / 'collector.stdout.txt'}"
            )

        result_path = capture / "results.json"
        result_bin = capture / "results.bin"
        transcript = capture / "usb.txt"
        results = json.loads(result_path.read_text(encoding="utf-8"))
        metadata = results["metadata"]
        if metadata.get("source_id") != manifest["source_id"]:
            raise RuntimeError("Collected result source_id does not match the requested ROM")
        _write_json(out / "checksum-result.json", {
            "source_id": metadata["source_id"],
            "record_count": metadata.get("record_count"),
            "results_sha256": sha256_file(result_bin),
            "transcript_sha256": sha256_file(transcript),
            "checksum_validated_by_collector": True,
        })
        return out
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            _stop_child(process, child_log, tree_killer)
        except BaseException as error:
            restore_report["errors"].append(f"Could not stop collector child: {error}")
        if restore_after and write_attempted and backup is not None:
            restore_report["restore_attempted"] = True
            restore_ok = False
            try:
                reset_pin_attempted = True
                command(["control", "pin", "--pin", "sel_c", "--state", "low"],
                        "reset-assert-for-restore")
                restore_ok = True
            except BaseException as error:
                restore_report["errors"].append(f"Could not assert reset for restore: {error}")

            if restore_ok:
                try:
                    command(["control", "poke", "live", "--address", "0", "--input",
                             out / "live-before.bin"], "poke-restore-backup")
                except BaseException as error:
                    restore_report["errors"].append(f"Backup restore command failed: {error}")
                try:
                    restore_readback = out / "live-restored-readback.bin"
                    command(["peek", "--address", "0", "--length", hex(ROM_BYTES),
                             "--output", restore_readback], "peek-restore-readback")
                    restored = restore_readback.read_bytes()
                    restore_report["restore_readback_sha256"] = sha256(restored)
                    restore_report["restored_verified"] = (
                        len(restored) == ROM_BYTES and restored == backup and sha256(restored) == backup_hash
                    )
                    if not restore_report["restored_verified"]:
                        restore_report["errors"].append("Restored live ROM does not match the fresh backup")
                except BaseException as error:
                    restore_report["errors"].append(f"Could not verify restored backup: {error}")

        if reset_pin_attempted:
            try:
                command(["control", "pin", "--pin", "sel_c", "--state", "z"],
                        "reset-release-final")
                restore_report["reset_release_verified"] = True
            except BaseException as error:
                restore_report["errors"].append(f"Could not release SEL_C to high impedance: {error}")

        _write_json(out / "restoration.json", restore_report)
        if (restore_after and write_attempted and not restore_report["restored_verified"]) or (
            reset_pin_attempted and not restore_report["reset_release_verified"]
        ):
            message = (
                "CRITICAL: live One ROM restoration could not be verified; "
                f"preserve {out / 'live-before.bin'} and inspect {out / 'restoration.json'}"
            )
            print(message, file=sys.stderr, flush=True)
            raise RuntimeError(message) from primary_error


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--onerom", type=Path, required=True, help="path to the onerom CLI")
    parser.add_argument("--romdir", type=Path, default=ROOT / "build" / "rom",
                        help="built A500 timing ROM directory")
    parser.add_argument("--out", type=Path, required=True, help="new output directory")
    parser.add_argument("--serial", help="exact One ROM serial when selecting among connected devices")
    parser.add_argument("--timeout", type=int, default=240, help="collection timeout in seconds")
    args = parser.parse_args(argv)
    collect_live(args.onerom, args.romdir, args.out, args.timeout, args.serial)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Capture MHO98 digital LA data with a verified edge trigger and FTP export.

This intentionally uses the proven single-digital-edge SCPI path. It does not
attempt an undocumented multi-input digital pattern trigger.
"""
from __future__ import annotations

import argparse
import ftplib
import hashlib
import json
import math
import os
import pathlib
import re
import socket
import struct
import sys
import time
import uuid
from decimal import Decimal, InvalidOperation


DEFAULT_HOST = "192.168.1.247"
DEFAULT_TIMEBASE = 20e-6
DEFAULT_DEPTH = 1_000_000
DEFAULT_TRIGGER_SOURCE = "D15"
DEFAULT_TRIGGER_SLOPE = "NEG"
CPU_REFERENCE_HZ = 7_093_790
MAX_ERROR_QUEUE_DRAIN = 8


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default=DEFAULT_HOST, help=f"scope host (default {DEFAULT_HOST})")
    ap.add_argument("--out", required=True, type=pathlib.Path,
                    help="new local .bin destination; existing file/sidecars are refused")
    ap.add_argument("--timebase", type=float, default=DEFAULT_TIMEBASE,
                    help="MHO98 timebase scale in seconds/division (default 20e-6)")
    ap.add_argument("--depth", type=int, default=DEFAULT_DEPTH,
                    help="acquisition depth (default 1000000; unsupported values are refused)")
    ap.add_argument("--trigger-source", default=DEFAULT_TRIGGER_SOURCE,
                    help="one digital edge source D0..D15 (default D15)")
    ap.add_argument("--trigger-slope", default=DEFAULT_TRIGGER_SLOPE,
                    help="POS or NEG digital edge (default NEG)")
    ap.add_argument("--connect-timeout", type=float, default=5.0)
    ap.add_argument("--socket-timeout", type=float, default=10.0)
    ap.add_argument("--trigger-timeout", type=float, default=60.0)
    ap.add_argument("--save-timeout", type=float, default=120.0)
    ap.add_argument("--ftp-timeout", type=float, default=30.0)
    ap.add_argument("--ftp-discovery-timeout", type=float, default=30.0,
                    help="bounded wait for the saved capture to appear in the FTP listing")
    ap.add_argument("--poll-interval", type=float, default=0.25)
    ap.add_argument("--analyze", action="store_true",
                    help="also run the existing decoder (large captures can use substantial RAM)")
    args = ap.parse_args(argv)
    if not args.host.strip():
        ap.error("--host must not be empty")
    if not math.isfinite(args.timebase) or args.timebase <= 0:
        ap.error("--timebase must be finite and greater than zero")
    if args.depth <= 0:
        ap.error("--depth must be greater than zero")
    args.trigger_source = args.trigger_source.upper()
    if not re.fullmatch(r"D(?:[0-9]|1[0-5])", args.trigger_source):
        ap.error("--trigger-source must be a digital source D0..D15")
    args.trigger_slope = args.trigger_slope.upper()
    if args.trigger_slope not in ("POS", "NEG"):
        ap.error("--trigger-slope must be POS or NEG")
    for name in ("connect_timeout", "socket_timeout", "trigger_timeout", "save_timeout",
                 "ftp_timeout", "ftp_discovery_timeout", "poll_interval"):
        value = getattr(args, name)
        if not math.isfinite(value) or value <= 0:
            ap.error(f"--{name.replace('_', '-')} must be finite and greater than zero")
    target = args.out.expanduser().resolve()
    if target.suffix.lower() != ".bin":
        ap.error("--out must name a .bin file")
    args.out = target
    sidecars = [target.with_suffix(".capture.json"), target.with_suffix(".scpi.json")]
    if args.analyze:
        sidecars.append(target.with_suffix(".analysis.json"))
    for path in [target, *sidecars, target.with_suffix(".part")]:
        if path.exists():
            ap.error(f"output already exists; refusing to overwrite: {path}")
    return args


def scpi_error_code(reply: str) -> int:
    try:
        return int(reply.split(",", 1)[0].strip())
    except (ValueError, AttributeError) as exc:
        raise RuntimeError(f"unrecognized :SYST:ERR? response: {reply!r}") from exc


def parse_raw_metadata(path: pathlib.Path) -> dict:
    """Read RG03 headers by seeking over payloads, without loading samples."""
    file_size = path.stat().st_size
    with path.open("rb") as f:
        header = f.read(16)
        if len(header) != 16 or header[:4] != b"RG03":
            raise ValueError("capture is not a complete RG03 file")
        declared_size, wave_count = struct.unpack_from("<QI", header, 4)
        if not 1 <= wave_count <= 64:
            raise ValueError(f"implausible RG03 wave count: {wave_count}")
        waves = []
        for index in range(wave_count):
            wave_start = f.tell()
            wh = f.read(140)
            if len(wh) != 140:
                raise ValueError(f"wave {index}: truncated 140-byte header")
            header_len, wave_type, buffer_count, points = struct.unpack_from("<IIII", wh, 0)
            xincr, xorigin = struct.unpack_from("<dd", wh, 32)
            label = wh[112:128].split(b"\0", 1)[0].decode("ascii", "replace").strip()
            if header_len < 140:
                raise ValueError(f"wave {index}: invalid header size {header_len}")
            if header_len > 140:
                extra = f.read(header_len - 140)
                if len(extra) != header_len - 140:
                    raise ValueError(f"wave {index}: truncated extended wave header")
            dh = f.read(16)
            if len(dh) != 16:
                raise ValueError(f"wave {index}: truncated data header")
            data_header_len, data_format, bytes_per_point, declared_payload, reserved = struct.unpack(
                "<IHHII", dh
            )
            if data_header_len < 16:
                raise ValueError(f"wave {index}: invalid data header size {data_header_len}")
            if data_header_len > 16:
                extra = f.read(data_header_len - 16)
                if len(extra) != data_header_len - 16:
                    raise ValueError(f"wave {index}: truncated extended data header")
            if points <= 0 or bytes_per_point <= 0:
                raise ValueError(f"wave {index}: invalid point/bytes-per-point metadata")
            payload_bytes = points * bytes_per_point
            payload_offset = f.tell()
            f.seek(payload_bytes, os.SEEK_CUR)
            if f.tell() > file_size:
                raise ValueError(f"wave {index}: payload extends beyond end of file")
            waves.append({
                "index": index, "offset": wave_start, "label": label or f"wave{index}",
                "type": wave_type, "buffer_count": buffer_count, "points": points,
                "wave_header_bytes": header_len,
                "x_increment_header_s_untrusted": xincr, "x_origin_s": xorigin,
                "data_header_bytes": data_header_len, "data_format": data_format,
                "bytes_per_point": bytes_per_point, "reserved": reserved,
                "declared_payload_bytes": declared_payload,
                "actual_payload_bytes": payload_bytes, "payload_offset": payload_offset,
            })
        parsed_end = f.tell()
    if parsed_end != file_size:
        raise ValueError(f"RG03 records end at {parsed_end}, file ends at {file_size}")
    las = [wave for wave in waves if wave["type"] == 6]
    if len(las) != 1:
        raise ValueError(f"expected exactly one LA wave, found {len(las)}")
    return {"signature": "RG03", "actual_file_bytes": file_size,
            "declared_file_bytes": declared_size, "parsed_end": parsed_end,
            "wave_count": wave_count, "waves": waves,
            "la_points": las[0]["points"], "la_payload_bytes": las[0]["actual_payload_bytes"],
            "la_x_increment_header_untrusted_s": las[0]["x_increment_header_s_untrusted"],
            "la_x_origin_s": las[0]["x_origin_s"],
            "warning": "The LA X-increment header is retained as raw metadata; use the validated capture-span/sample-count method for timing.",
            "declared_minus_actual_file_bytes": declared_size - file_size}


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ScopeSession:
    def __init__(self, conn: socket.socket, socket_timeout: float):
        self.conn = conn
        self.conn.settimeout(socket_timeout)
        self.reader = conn.makefile("rb")
        self.log: list[dict] = []

    def command(self, command: str, query: bool = False) -> str | None:
        self.conn.sendall((command + "\n").encode("ascii"))
        reply = self.reader.readline().decode("ascii", "replace").strip() if query else None
        self.log.append({"command": command, "reply": reply})
        if query and not reply:
            raise RuntimeError(f"empty reply to {command}")
        return reply

    def ask(self, command: str) -> str:
        reply = self.command(command, query=True)
        assert reply is not None
        return reply


def check_no_error(session: ScopeSession, stage: str) -> str:
    reply = session.ask(":SYST:ERR?")
    if scpi_error_code(reply) != 0:
        raise RuntimeError(f"scope reported SCPI error {reply!r} {stage}")
    return reply


def save_json_no_overwrite(path: pathlib.Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, indent=2)
        f.write("\n")


def discover_remote_capture(ftp, token: str, timeout: float, poll_interval: float,
                            attempts: list[dict], *, monotonic=time.monotonic,
                            sleep=time.sleep) -> str:
    """Poll FTP until exactly one matching saved capture appears or time expires."""
    started = monotonic()
    deadline = started + timeout
    while True:
        names = ftp.nlst()
        matches = [name for name in names
                   if token.lower() in pathlib.PurePosixPath(name).name.lower()]
        elapsed = monotonic() - started
        if len(matches) > 1:
            attempts.append({"attempt": len(attempts) + 1, "state": "ambiguous",
                             "elapsed_s": elapsed, "matches": matches})
            raise RuntimeError(f"expected one unique remote capture for {token}, found {matches}")
        if matches:
            attempts.append({"attempt": len(attempts) + 1, "state": "found",
                             "elapsed_s": elapsed, "matches": matches})
            return matches[0]
        remaining = deadline - monotonic()
        state = "timeout" if remaining <= 0 else "waiting"
        attempts.append({"attempt": len(attempts) + 1, "state": state,
                         "elapsed_s": elapsed, "matches": []})
        if remaining <= 0:
            raise TimeoutError(
                f"remote capture {token} did not appear in FTP listing within {timeout:g}s"
            )
        sleep(min(poll_interval, remaining))


def validate_trigger_edge(path: pathlib.Path, metadata: dict, source: str, slope: str) -> dict:
    """Stream the LA payload and require the configured trigger edge to be present."""
    la_waves = [wave for wave in metadata["waves"] if wave["type"] == 6]
    if len(la_waves) != 1:
        raise ValueError(f"expected exactly one LA wave, found {len(la_waves)}")
    la = la_waves[0]
    if la["data_format"] != 5 or la["bytes_per_point"] != 4:
        raise ValueError("trigger-edge validation requires RG03 LA uint32 samples")
    points = la["points"]
    bit = int(source[1:])
    counts = {"POS": 0, "NEG": 0}
    first_sample = {"POS": None, "NEG": None}
    last_sample = {"POS": None, "NEG": None}
    previous = None
    sample_index = 0
    remaining = points
    chunk_points = 262_144
    with path.open("rb") as capture:
        capture.seek(la["payload_offset"])
        while remaining:
            count = min(remaining, chunk_points)
            chunk = capture.read(count * la["bytes_per_point"])
            if len(chunk) != count * la["bytes_per_point"]:
                raise ValueError("truncated LA payload while validating trigger edge")
            for (word,) in struct.iter_unpack("<I", chunk):
                current = (word >> bit) & 1
                if previous is not None and current != previous:
                    direction = "POS" if current else "NEG"
                    counts[direction] += 1
                    if first_sample[direction] is None:
                        first_sample[direction] = sample_index
                    last_sample[direction] = sample_index
                previous = current
                sample_index += 1
            remaining -= count
    target_count = counts[slope]
    return {
        "source": source, "slope": slope, "rising_edges": counts["POS"],
        "falling_edges": counts["NEG"], "target_edge_count": target_count,
        "first_target_edge_sample": first_sample[slope],
        "last_target_edge_sample": last_sample[slope],
        "target_edge_observed": target_count > 0,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if any(path.exists() for path in [args.out, args.out.with_suffix(".capture.json"),
                                      args.out.with_suffix(".scpi.json"),
                                      args.out.with_suffix(".part")]):
        raise FileExistsError("an output appeared after validation; refusing to overwrite")

    result = {"host": args.host, "requested": {
        "timebase_s_per_div": args.timebase, "depth_points": args.depth,
        "trigger_source": args.trigger_source, "trigger_slope": args.trigger_slope,
    }, "commands": [], "status": "starting"}
    session: ScopeSession | None = None
    conn: socket.socket | None = None
    downloaded = False
    part = args.out.with_suffix(".part")
    remote_token = "clscope_" + uuid.uuid4().hex[:16]
    try:
        conn = socket.create_connection((args.host, 5555), timeout=args.connect_timeout)
        session = ScopeSession(conn, args.socket_timeout)
        result["idn"] = session.ask("*IDN?")
        if "RIGOL" not in result["idn"].upper() or "MHO98" not in result["idn"].upper():
            raise RuntimeError(f"expected Rigol MHO98, got {result['idn']!r}")

        before = {
            "gen1_output": session.ask(":SOUR1:OUTP:STAT?"),
            "gen2_output": session.ask(":SOUR2:OUTP:STAT?"),
            "analog_display": {f"CHAN{i}": session.ask(f":CHAN{i}:DISP?") for i in range(1, 5)},
            "la_enabled": session.ask(":LA:ENAB?"),
            "pod_display": {f"POD{i}": session.ask(f":LA:POD{i}:DISP?") for i in range(1, 3)},
            "timebase_s_per_div": session.ask(":TIM:SCAL?"),
            "depth_points": session.ask(":ACQ:MDEP?"),
            "trigger_mode": session.ask(":TRIG:MODE?"),
            "trigger_source": session.ask(":TRIG:EDGE:SOUR?"),
            "trigger_slope": session.ask(":TRIG:EDGE:SLOP?"),
        }
        result["before"] = before
        if before["gen1_output"] != "0" or before["gen2_output"] != "0":
            raise RuntimeError("both built-in generator outputs must already be OFF; refusing to continue")
        baseline_error = session.ask(":SYST:ERR?")
        result["baseline_scpi_error"] = baseline_error
        if scpi_error_code(baseline_error) != 0:
            raise RuntimeError(f"scope had a pre-existing SCPI error: {baseline_error!r}")

        for command in (
            ":STOP",
            ":CHAN1:DISP OFF", ":CHAN2:DISP OFF", ":CHAN3:DISP OFF", ":CHAN4:DISP OFF",
            f":TIM:SCAL {args.timebase:.12g}", f":ACQ:MDEP {args.depth}",
            ":LA:ENAB ON", ":LA:POD1:DISP ON", ":LA:POD2:DISP ON",
            ":LA:POD1:THR 1.4", ":LA:POD2:THR 1.4",
            ":TRIG:MODE EDGE", f":TRIG:EDGE:SOUR {args.trigger_source}",
            f":TRIG:EDGE:SLOP {args.trigger_slope}", ":TRIG:SWEEP NORM",
        ):
            session.command(command)

        actual = {
            "timebase_s_per_div": session.ask(":TIM:SCAL?"),
            "depth_points": session.ask(":ACQ:MDEP?"),
            "analog_display": {f"CHAN{i}": session.ask(f":CHAN{i}:DISP?") for i in range(1, 5)},
            "la_enabled": session.ask(":LA:ENAB?"),
            "pod_display": {f"POD{i}": session.ask(f":LA:POD{i}:DISP?") for i in range(1, 3)},
            "trigger_mode": session.ask(":TRIG:MODE?"),
            "trigger_source": session.ask(":TRIG:EDGE:SOUR?"),
            "trigger_slope": session.ask(":TRIG:EDGE:SLOP?"),
        }
        result["actual"] = actual
        try:
            actual_timebase = Decimal(actual["timebase_s_per_div"])
            requested_timebase = Decimal(str(args.timebase))
            actual_depth = Decimal(actual["depth_points"])
        except InvalidOperation as exc:
            raise RuntimeError("scope returned nonnumeric timebase/depth readback") from exc
        if actual_timebase != requested_timebase:
            raise RuntimeError(f"scope timebase readback {actual_timebase} does not match requested {requested_timebase}")
        if actual_depth != Decimal(args.depth):
            raise RuntimeError(f"scope depth readback {actual_depth} does not match requested {args.depth}")
        if actual["analog_display"] != {f"CHAN{i}": "0" for i in range(1, 5)}:
            raise RuntimeError(f"scope did not disable all analog channels: {actual['analog_display']}")
        if actual["la_enabled"] not in ("1", "ON"):
            raise RuntimeError(f"scope LA did not enable: {actual['la_enabled']!r}")
        if actual["pod_display"] != {"POD1": "1", "POD2": "1"}:
            raise RuntimeError(f"scope LA pods did not enable: {actual['pod_display']}")
        if (actual["trigger_mode"] != "EDGE" or actual["trigger_source"] != args.trigger_source
                or actual["trigger_slope"] not in (args.trigger_slope, "POSitive" if args.trigger_slope == "POS" else "NEGative")):
            raise RuntimeError(f"trigger readback did not match request: {actual}")
        result["configuration_scpi_error"] = check_no_error(session, "after configuration")

        session.command(":SING")
        deadline = time.monotonic() + args.trigger_timeout
        trigger_states = []
        while True:
            state = session.ask(":TRIG:STAT?").upper()
            trigger_states.append(state)
            if state == "STOP":
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"no trigger within {args.trigger_timeout:g}s; last state={state}")
            time.sleep(args.poll_interval)
        result["trigger_states"] = trigger_states

        session.command(f":SAVE:MEM:WAV C:/{remote_token}.bin")
        save_deadline = time.monotonic() + args.save_timeout
        save_states = []
        while True:
            state = session.ask(":SAVE:STAT?")
            save_states.append(state)
            if state == "1":
                break
            if state != "0":
                raise RuntimeError(f"unexpected SAVE:STAT? response: {state!r}")
            if time.monotonic() >= save_deadline:
                raise TimeoutError(f"scope save did not finish within {args.save_timeout:g}s")
            time.sleep(args.poll_interval)
        result["save_states"] = save_states

        ftp_attempts = []
        result["ftp_discovery"] = {
            "timeout_s": args.ftp_discovery_timeout,
            "poll_interval_s": args.poll_interval,
            "attempts": ftp_attempts,
        }
        with ftplib.FTP(args.host, timeout=args.ftp_timeout) as ftp:
            ftp.login()
            remote_name = discover_remote_capture(
                ftp, remote_token, args.ftp_discovery_timeout, args.poll_interval, ftp_attempts
            )
            result["remote_filename"] = remote_name
            with part.open("xb") as output:
                ftp.retrbinary("RETR " + remote_name, output.write, blocksize=1024 * 1024)
        part.replace(args.out)
        downloaded = True
        result["file_bytes"] = args.out.stat().st_size
        result["sha256"] = sha256_file(args.out)
        result["raw_metadata"] = parse_raw_metadata(args.out)
        edge_validation = validate_trigger_edge(
            args.out, result["raw_metadata"], args.trigger_source, args.trigger_slope
        )
        result["trigger_edge_validation"] = edge_validation
        if not edge_validation["target_edge_observed"]:
            raise RuntimeError(
                f"configured {args.trigger_slope} edge on {args.trigger_source} "
                "was absent from captured LA samples"
            )
        result["capture_span_s_from_analog_metadata"] = None
        result["metadata_note"] = "Raw RG03 X-increment fields are preserved, not trusted as LA sample intervals."

        final_error = session.ask(":SYST:ERR?")
        result["final_scpi_error"] = final_error
        if scpi_error_code(final_error) != 0:
            raise RuntimeError(f"scope reported final SCPI error: {final_error!r}")
        result["status"] = "complete"
        if args.analyze:
            probe_root = pathlib.Path(__file__).resolve().parents[1]
            if str(probe_root / "tools") not in sys.path:
                sys.path.insert(0, str(probe_root / "tools"))
            from analyze_bzero_bus import analyze
            decoded = analyze(args.out, sample_interval_s=None,
                              nominal_cpu_reference_hz=CPU_REFERENCE_HZ,
                              max_jitter_fraction=0.05)
            decoded.pop("words_uint32", None)
            analysis_path = args.out.with_suffix(".analysis.json")
            save_json_no_overwrite(analysis_path, decoded)
            result["analysis_json"] = str(analysis_path)
        return 0
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
        if session is not None:
            try:
                session.command(":STOP")
            except Exception as stop_exc:
                result["stop_on_exception_error"] = f"{type(stop_exc).__name__}: {stop_exc}"
            try:
                result["final_scpi_error"] = session.ask(":SYST:ERR?")
            except Exception as err_exc:
                result["final_scpi_error_query_error"] = f"{type(err_exc).__name__}: {err_exc}"
        raise
    finally:
        if session is not None:
            result["commands"] = session.log
            try:
                session.reader.close()
            except Exception:
                pass
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        if part.exists():
            part.unlink()
        # Save an audit trail even on a failed configuration/capture. The raw
        # capture is only retained if FTP transfer completed successfully.
        capture_json = args.out.with_suffix(".capture.json")
        scpi_json = args.out.with_suffix(".scpi.json")
        try:
            if not capture_json.exists():
                save_json_no_overwrite(capture_json, result)
            if not scpi_json.exists():
                save_json_no_overwrite(scpi_json, {"commands": result["commands"]})
        except Exception as sidecar_exc:
            print(f"Could not write audit sidecar: {sidecar_exc}", file=sys.stderr)
        if not downloaded and args.out.exists():
            args.out.unlink()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"capture failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)

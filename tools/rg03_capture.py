"""Strict parser for the RG03 analog-float32 and LA-uint32 wave records."""
from __future__ import annotations

import math
import struct
from pathlib import Path

GLOBAL_HEADER_BYTES = 16
WAVE_HEADER_BYTES = 140
DATA_HEADER_BYTES = 16


def _u16(buf: bytes, off: int) -> int:
    return struct.unpack_from("<H", buf, off)[0]


def _u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def _u64(buf: bytes, off: int) -> int:
    return struct.unpack_from("<Q", buf, off)[0]


def _f64(buf: bytes, off: int) -> float:
    return struct.unpack_from("<d", buf, off)[0]


def parse_capture(path: Path) -> dict:
    """Parse complete RG03 records, including LA-only files.

    Payload size is determined by point count and bytes per point. The
    advertised payload length is preserved as evidence because some known
    LA-only captures overstate it; truncated payloads and trailing bytes are
    still rejected exactly.
    """
    data = path.read_bytes()
    if len(data) < GLOBAL_HEADER_BYTES:
        raise ValueError("truncated global header")
    if data[:4] != b"RG03":
        raise ValueError(f"unexpected signature {data[:4]!r}; expected b'RG03'")
    wave_count = _u32(data, 12)
    if wave_count == 0 or wave_count > 64:
        raise ValueError(f"implausible wave record count: {wave_count}")
    pos, waves = GLOBAL_HEADER_BYTES, []
    for wi in range(wave_count):
        if pos + WAVE_HEADER_BYTES + DATA_HEADER_BYTES > len(data):
            raise ValueError(f"wave {wi}: truncated wave/data header at offset {pos}")
        wh = data[pos:pos + WAVE_HEADER_BYTES]
        wh_len, wave_type, buffer_count, points = (_u32(wh, 0), _u32(wh, 4), _u32(wh, 8), _u32(wh, 12))
        xincr, xorigin = _f64(wh, 32), _f64(wh, 40)
        label = wh[112:128].split(b"\0", 1)[0].decode("ascii", "replace").strip()
        if wh_len < WAVE_HEADER_BYTES:
            raise ValueError(f"wave {wi}: header length {wh_len} is shorter than {WAVE_HEADER_BYTES}")
        if points == 0 or points > 100_000_000:
            raise ValueError(f"wave {wi}: implausible point count {points}")
        if buffer_count != 1:
            raise ValueError(f"wave {wi} ({label}): expected wave buffer count 1, got {buffer_count}")
        if not math.isfinite(xincr) or xincr <= 0 or not math.isfinite(xorigin):
            raise ValueError(f"wave {wi}: invalid time metadata")
        data_header_pos = pos + wh_len
        if data_header_pos + DATA_HEADER_BYTES > len(data):
            raise ValueError(f"wave {wi}: truncated data header")
        dh = data[data_header_pos:data_header_pos + DATA_HEADER_BYTES]
        dh_len, fmt, bpp = _u32(dh, 0), _u16(dh, 4), _u16(dh, 6)
        declared_payload, reserved = _u32(dh, 8), _u32(dh, 12)
        if dh_len < DATA_HEADER_BYTES:
            raise ValueError(f"wave {wi}: data header length {dh_len} is too short")
        payload_pos = data_header_pos + dh_len
        if wave_type not in (1, 6):
            raise ValueError(f"wave {wi} ({label}): unsupported wave type {wave_type}")
        expected_fmt = 1 if wave_type == 1 else 5
        if fmt != expected_fmt:
            raise ValueError(f"wave {wi} ({label}): expected data format {expected_fmt} for type {wave_type}, got {fmt}")
        if bpp != 4:
            raise ValueError(f"wave {wi} ({label}): expected 4 bytes per point, got {bpp}")
        if reserved != 0:
            raise ValueError(f"wave {wi} ({label}): unsupported nonzero data-header reserved field {reserved}")
        actual_payload = points * bpp
        payload_end = payload_pos + actual_payload
        if payload_end > len(data):
            raise ValueError(f"wave {wi} ({label}): {actual_payload}-byte payload exceeds file boundary")
        waves.append({"index": wi, "label": label or f"wave{wi}", "type": wave_type,
                      "buffer_count": buffer_count, "points": points,
                      "x_increment_header_s": xincr, "x_origin_s": xorigin,
                      "wave_header_bytes": wh_len, "data_header_bytes": dh_len,
                      "format": fmt, "bytes_per_point_header": bpp,
                      "data_header_reserved": reserved,
                      "declared_payload_bytes": declared_payload,
                      "actual_payload_bytes": actual_payload, "payload_offset": payload_pos,
                      "payload": data[payload_pos:payload_end]})
        pos = payload_end
    if pos != len(data):
        raise ValueError(f"parsed records end at {pos}, actual file ends at {len(data)} (trailing or mis-sized data)")
    analogs = [w for w in waves if w["type"] == 1]
    las = [w for w in waves if w["type"] == 6]
    if len(las) != 1:
        raise ValueError(f"expected exactly one LA record; found {len(las)}")
    ch1 = None
    if analogs:
        ch1s = [w for w in analogs if w["label"].upper() == "CH1"]
        if len(ch1s) != 1:
            raise ValueError(f"expected exactly one CH1 analog record; found {len(ch1s)}")
        ch1 = ch1s[0]
        for w in analogs:
            if not math.isclose(w["x_origin_s"], ch1["x_origin_s"], rel_tol=1e-9, abs_tol=1e-15) or not math.isclose(
                w["points"] * w["x_increment_header_s"],
                ch1["points"] * ch1["x_increment_header_s"], rel_tol=1e-9, abs_tol=1e-15):
                raise ValueError(f"analog record {w['label']} does not share CH1's capture span")
    return {"path": str(path), "actual_file_bytes": len(data),
            "declared_file_bytes": _u64(data, 4), "parsed_end": pos,
            "wave_count": wave_count, "waves": waves,
            "analogs": analogs, "analog": ch1, "la": las[0]}

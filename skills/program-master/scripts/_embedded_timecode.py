"""Map file-relative seconds to embedded SMPTE timecode (tmcd / container tags)."""

from __future__ import annotations

import re
from typing import Any

from timecode import Timecode

TIMECODE_RE = re.compile(
    r"^(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})(?P<sep>[:;.])(?P<f>\d{2,3})$"
)


def normalize_fps(fps: float | str) -> str:
    if isinstance(fps, str):
        raw = fps.strip()
        if "/" in raw:
            return raw
        try:
            fps = float(raw)
        except ValueError:
            return raw

    value = float(fps)
    aliases = {23.976: "23.976", 29.97: "29.97", 59.94: "59.94"}
    for key, mapped in aliases.items():
        if abs(value - key) < 0.005:
            return mapped
    if value.is_integer():
        return str(int(value))
    return str(value)


def _video_fps(probe_meta: dict[str, Any], *, video_stream: int = 0) -> str:
    videos = [stream for stream in probe_meta.get("streams") or [] if stream.get("codec_type") == "video"]
    if 0 <= video_stream < len(videos):
        stream = videos[video_stream]
        return normalize_fps(stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "29.97")
    return "29.97"


def extract_embedded_timecode(
    probe_meta: dict[str, Any],
    *,
    video_stream: int = 0,
) -> dict[str, Any] | None:
    """Read embedded TC, preferring the tmcd data stream over container tags."""
    tmcd_tc: str | None = None
    tmcd_index: int | None = None
    for stream in probe_meta.get("streams") or []:
        if stream.get("codec_tag_string") != "tmcd":
            continue
        tc = (stream.get("tags") or {}).get("timecode")
        if tc:
            tmcd_tc = str(tc)
            tmcd_index = stream.get("index")

    format_tc = (probe_meta.get("format") or {}).get("tags") or {}
    container_tc = format_tc.get("timecode")

    tc_value = tmcd_tc or container_tc
    if not tc_value:
        return None

    fps = _video_fps(probe_meta, video_stream=video_stream)
    drop_frame = TIMECODE_RE.match(str(tc_value).strip()) is not None and ";" in str(tc_value)
    return {
        "timecode": str(tc_value),
        "fps": fps,
        "drop_frame": drop_frame,
        "source": "tmcd" if tmcd_tc else "container",
        "stream_index": tmcd_index,
    }


def _fps_as_float(fps: float | str) -> float:
    if isinstance(fps, str) and "/" in fps:
        num, den = fps.split("/", 1)
        return float(num) / float(den)
    return float(fps)


def embedded_timecode_at_seconds(
    base_timecode: str,
    fps: float | str,
    file_seconds: float,
) -> str:
    """Map file timeline seconds to embedded SMPTE TC via exact video frame rate."""
    base = Timecode(normalize_fps(fps), base_timecode)
    rate = _fps_as_float(fps)
    delta_frames = int(round(file_seconds * rate))
    return str(base + delta_frames)


def apply_embedded_timecodes(
    segments: list[dict[str, Any]],
    embedded: dict[str, Any],
) -> None:
    """Set start_timecode/end_timecode from embedded SMPTE track; keep file-relative copies."""
    base = embedded["timecode"]
    fps = embedded["fps"]
    for seg in segments:
        start = float(seg["start"])
        end = float(seg["end"])
        seg["start_timecode_file"] = seg.get("start_timecode")
        seg["end_timecode_file"] = seg.get("end_timecode")
        seg["start_timecode"] = embedded_timecode_at_seconds(base, fps, start)
        seg["end_timecode"] = embedded_timecode_at_seconds(base, fps, end)

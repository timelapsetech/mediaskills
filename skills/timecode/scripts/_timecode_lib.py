"""Timecode helpers built on the eoyilmaz/timecode library."""

from __future__ import annotations

import re
from typing import Any

from timecode import Timecode

NTSC_NOMINAL = {23.976, 24.0, 29.97, 30.0, 59.94, 60.0}
SUPPORTED_FPS = ["23.976", "24", "25", "29.97", "30", "50", "59.94", "60", "30000/1001", "24000/1001", "60000/1001"]

TIMECODE_RE = re.compile(
    r"^(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})(?P<sep>[:;.])(?P<f>\d{2,3})$"
)


def normalize_fps(fps: float | str) -> str:
    """Map common fps inputs to strings the timecode library accepts."""
    if isinstance(fps, str):
        raw = fps.strip()
        if "/" in raw:
            return raw
        try:
            fps = float(raw)
        except ValueError:
            return raw

    value = float(fps)
    aliases = {
        23.98: "23.976",
        23.976: "23.976",
        29.97: "29.97",
        59.94: "59.94",
    }
    for key, mapped in aliases.items():
        if abs(value - key) < 0.005:
            return mapped
    if value.is_integer():
        return str(int(value))
    return str(value)


def delimiter_in_string(timecode: str) -> str | None:
    match = TIMECODE_RE.match(timecode.strip())
    if not match:
        return None
    return match.group("sep")


def infer_drop_frame_from_string(timecode: str) -> bool | None:
    """Return True/False when delimiter is unambiguous, else None."""
    sep = delimiter_in_string(timecode)
    if sep == ";":
        return True
    if sep == ":":
        return False
    return None


def is_ntsc_nominal(fps: float | str) -> bool:
    try:
        if isinstance(fps, str) and "/" in fps:
            num, den = fps.split("/", 1)
            value = float(num) / float(den)
        else:
            value = float(fps)
    except (TypeError, ValueError, ZeroDivisionError):
        return False
    for nominal in NTSC_NOMINAL:
        if abs(value - nominal) < 0.02:
            int_fps = round(value * 1001 / 1000)
            expected = int_fps * 1000 / 1001
            if abs(value - expected) < 0.005:
                return int_fps % 30 == 0
    return False


def build_timecode(
    fps: float | str,
    timecode: str | None = None,
    *,
    seconds: float | None = None,
    frames: int | None = None,
    force_non_drop_frame: bool = False,
) -> Timecode:
    """Construct a Timecode with drop-frame inferred from the string when possible."""
    rate = normalize_fps(fps)
    inferred = infer_drop_frame_from_string(timecode) if timecode else None
    ndf = force_non_drop_frame or (inferred is False)

    if timecode is not None:
        return Timecode(rate, timecode, force_non_drop_frame=ndf)
    if frames is not None:
        return Timecode(rate, frames=frames, force_non_drop_frame=ndf)
    if seconds is not None:
        return timecode_from_seconds(seconds, rate, force_non_drop_frame=ndf)
    return Timecode(rate, "00:00:00:00", force_non_drop_frame=ndf)


def timecode_from_seconds(
    seconds: float,
    fps: float | str,
    *,
    force_non_drop_frame: bool = False,
) -> Timecode:
    """Build a Timecode from wall-clock seconds."""
    rate = normalize_fps(fps)
    probe = Timecode(rate, "00:00:00:00", force_non_drop_frame=force_non_drop_frame)
    if seconds == 0:
        return probe
    if probe._ntsc_framerate and not force_non_drop_frame:
        system_seconds = seconds / 1.001
        frames = probe.float_to_tc(system_seconds)
        return Timecode(rate, frames=frames)
    frames = int(round(seconds * probe._int_framerate)) + 1
    return Timecode(rate, frames=frames, force_non_drop_frame=force_non_drop_frame)


def linear_seconds(tc: Timecode) -> float:
    """Elapsed seconds from 0-based frame index and integer frame rate."""
    return tc.frame_number / float(tc._int_framerate)


def timecode_payload(tc: Timecode) -> dict[str, Any]:
    return {
        "timecode": str(tc),
        "fps": tc.framerate,
        "drop_frame": tc.drop_frame,
        "frame_delimiter": tc.frame_delimiter,
        "frames": tc.frame_number,
        "frames_1based": tc.frames,
        "seconds": linear_seconds(tc),
        "seconds_system": tc.float,
        "seconds_realtime": tc.to_realtime(as_float=True),
    }


def convert_realtime(
    tc: Timecode,
    target_fps: float | str,
    *,
    force_non_drop_frame: bool | None = None,
) -> Timecode:
    """Retime while preserving wall-clock duration."""
    ndf = tc.force_non_drop_frame if force_non_drop_frame is None else force_non_drop_frame
    wall = tc.to_realtime(as_float=True)
    return timecode_from_seconds(wall, target_fps, force_non_drop_frame=ndf)


def convert_drop_frame_mode(
    tc: Timecode,
    *,
    to_drop_frame: bool,
    preserve: str = "realtime",
) -> Timecode:
    """Convert between drop-frame and non-drop-frame display."""
    ndf = not to_drop_frame
    if preserve == "frames":
        return Timecode(tc.framerate, frames=tc.frames, force_non_drop_frame=ndf)
    return Timecode(tc.framerate, start_seconds=tc.float, force_non_drop_frame=ndf)


def analyze_timecode_string(timecode: str, fps: float | str | None = None) -> dict[str, Any]:
    sep = delimiter_in_string(timecode)
    inferred_df = infer_drop_frame_from_string(timecode)
    notes: list[str] = []

    if sep == ";":
        notes.append("Semicolon frame delimiter indicates drop-frame display (SMPTE 12M).")
    elif sep == ":":
        notes.append("Colon frame delimiter indicates non-drop-frame display.")
    elif sep == ".":
        notes.append("Dot separator indicates fractional seconds or millisecond timecode.")

    ntsc = is_ntsc_nominal(fps) if fps is not None else None
    if ntsc and inferred_df is None:
        notes.append("NTSC nominal rate without delimiter hint defaults to drop-frame in the library.")
    if ntsc is False and inferred_df is True:
        notes.append("Semicolon delimiter on a non-NTSC rate is unusual; verify source metadata.")

    effective_df: bool | None = inferred_df
    if fps is not None and effective_df is None and ntsc:
        effective_df = True

    return {
        "timecode": timecode,
        "fps": normalize_fps(fps) if fps is not None else None,
        "delimiter": sep,
        "inferred_drop_frame": inferred_df,
        "effective_drop_frame": effective_df,
        "ntsc_nominal_rate": ntsc,
        "notes": notes,
    }


def _scan_mapping(mapping: dict[str, Any], *keys: str) -> str | None:
    lowered = {str(k).lower(): v for k, v in mapping.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value not in (None, ""):
            return str(value)
    return None


def analyze_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Infer timecode format from ffprobe/mediainfo-style metadata blobs."""
    tags: dict[str, Any] = {}
    tags.update(metadata.get("format", {}).get("tags") or {})
    for stream in metadata.get("streams") or []:
        tags.update(stream.get("tags") or {})
    tags.update(metadata.get("tags") or {})

    flat = metadata.get("media_info") or metadata.get("mediainfo") or {}
    if isinstance(flat, dict):
        tags.update(flat)

    tc_value = _scan_mapping(
        tags,
        "timecode",
        "TIMECODE",
        "time_code_of_first_frame",
        "timecode_of_first_frame",
        "time_code_of_last_frame",
        "timecode_of_last_frame",
    )
    settings = _scan_mapping(
        tags,
        "time_code_settings",
        "timecode_settings",
        "timecode_dropframe",
        "drop_frame",
    )

    fps_raw = _scan_mapping(
        tags,
        "timecode_rate",
        "time_code_rate",
        "frame_rate",
        "framerate",
    )
    for stream in metadata.get("streams") or []:
        if stream.get("codec_type") == "video" and not fps_raw:
            fps_raw = stream.get("avg_frame_rate") or stream.get("r_frame_rate")

    fps: float | str | None = None
    if fps_raw:
        if "/" in str(fps_raw):
            num, den = str(fps_raw).split("/", 1)
            fps = f"{num}/{den}" if float(den) else None
        else:
            try:
                fps = float(fps_raw)
            except ValueError:
                fps = str(fps_raw)

    string_analysis = analyze_timecode_string(tc_value, fps) if tc_value else None

    inferred_df: bool | None = None
    reasons: list[str] = []
    if string_analysis and string_analysis["inferred_drop_frame"] is not None:
        inferred_df = string_analysis["inferred_drop_frame"]
        reasons.append("timecode string delimiter")
    if settings:
        lowered = settings.lower()
        if "drop" in lowered and "non" not in lowered:
            inferred_df = True
            reasons.append(f"timecode settings: {settings}")
        elif "non" in lowered and "drop" in lowered:
            inferred_df = False
            reasons.append(f"timecode settings: {settings}")
    if inferred_df is None and fps is not None and is_ntsc_nominal(fps):
        inferred_df = True
        reasons.append("NTSC nominal frame rate")

    return {
        "timecode": tc_value,
        "fps": normalize_fps(fps) if fps is not None else None,
        "timecode_settings": settings,
        "inferred_drop_frame": inferred_df,
        "inference_reasons": reasons,
        "string_analysis": string_analysis,
        "tags": tags,
    }

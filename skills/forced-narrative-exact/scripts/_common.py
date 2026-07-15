"""Shared media, path, and SMPTE helpers for forced-narrative scripts."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


def generated_dir() -> Path:
    data_dir = os.environ.get("MEDIASKILLS_DATA_DIR")
    if data_dir and Path(data_dir).is_absolute():
        out = Path(data_dir) / "generated"
    else:
        out = Path.cwd() / ".mediaskills" / "generated"
    out.mkdir(parents=True, exist_ok=True)
    return out.resolve()


def media_stem(path: str | Path) -> str:
    return Path(path).stem


def run_json(cmd: list[str]) -> dict[str, Any]:
    return json.loads(subprocess.check_output(cmd, text=True))


def probe_video(path: str | Path, *, count_frames: bool = False) -> dict[str, Any]:
    src = str(Path(path).expanduser().resolve())
    cmd = ["ffprobe", "-v", "error"]
    if count_frames:
        cmd.append("-count_frames")
    cmd += ["-show_streams", "-show_format", "-of", "json", src]
    doc = run_json(cmd)
    video = next((s for s in doc.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video:
        raise ValueError("No video stream found")
    fps_text = video.get("avg_frame_rate") or video.get("r_frame_rate")
    fps = Fraction(fps_text)
    duration = float(video.get("duration") or doc.get("format", {}).get("duration") or 0)
    frames_value = video.get("nb_read_frames") or video.get("nb_frames")
    frames = int(frames_value) if frames_value and str(frames_value).isdigit() else round(duration * float(fps))
    embedded = None
    for stream in doc.get("streams", []):
        tags = stream.get("tags") or {}
        if stream.get("codec_tag_string") == "tmcd" and tags.get("timecode"):
            embedded = str(tags["timecode"])
            break
    if embedded is None:
        tags = video.get("tags") or {}
        if tags.get("timecode"):
            embedded = str(tags["timecode"])
    return {
        "input_path": src,
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": f"{fps.numerator}/{fps.denominator}",
        "fps_fraction": fps,
        "frame_count": frames,
        "duration_seconds": duration,
        "embedded_start_timecode": embedded,
        "drop_frame": bool(embedded and ";" in embedded) or fps in (Fraction(30000, 1001), Fraction(60000, 1001)),
    }


def nominal_rate(fps: Fraction) -> int:
    return int(round(float(fps)))


def drop_frames_per_minute(fps: Fraction) -> int:
    if fps == Fraction(30000, 1001):
        return 2
    if fps == Fraction(60000, 1001):
        return 4
    return 0


def tc_to_frames(tc: str, fps: Fraction) -> int:
    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2})[:;](\d{2})", tc.strip())
    if not match:
        raise ValueError(f"Invalid SMPTE timecode: {tc}")
    hours, minutes, seconds, frames = map(int, match.groups())
    nominal = nominal_rate(fps)
    total_minutes = hours * 60 + minutes
    count = ((hours * 3600 + minutes * 60 + seconds) * nominal) + frames
    drop = drop_frames_per_minute(fps) if ";" in tc else 0
    if drop:
        count -= drop * (total_minutes - total_minutes // 10)
    return count


def frames_to_tc(frame_number: int, fps: Fraction, drop_frame: bool) -> str:
    if frame_number < 0:
        raise ValueError("Negative timecode frames are unsupported")
    nominal = nominal_rate(fps)
    drop = drop_frames_per_minute(fps) if drop_frame else 0
    display = int(frame_number)
    if drop:
        frames_per_10_minutes = nominal * 60 * 10 - drop * 9
        frames_per_minute = nominal * 60 - drop
        tens, remainder = divmod(display, frames_per_10_minutes)
        display += drop * 9 * tens
        if remainder >= drop:
            display += drop * ((remainder - drop) // frames_per_minute)
    frames = display % nominal
    seconds_total = display // nominal
    seconds = seconds_total % 60
    minutes_total = seconds_total // 60
    minutes = minutes_total % 60
    hours = (minutes_total // 60) % 24
    delimiter = ";" if drop else ":"
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{delimiter}{frames:02d}"


def timing_fields(frame: int, fps: Fraction, embedded_start: str | None, drop_frame: bool) -> dict[str, Any]:
    seconds = frame * fps.denominator / fps.numerator
    file_tc = frames_to_tc(frame, fps, drop_frame)
    embedded_tc = None
    if embedded_start:
        embedded_tc = frames_to_tc(tc_to_frames(embedded_start, fps) + frame, fps, ";" in embedded_start)
    return {"seconds": round(seconds, 6), "file_timecode": file_tc, "embedded_timecode": embedded_tc}


def parse_crop(value: str | None, width: int, height: int) -> dict[str, int]:
    if value:
        parts = [int(p.strip()) for p in value.split(",")]
        if len(parts) != 4:
            raise ValueError("--crop must be x,y,width,height")
        x, y, w, h = parts
    else:
        x, y = 0, round(height * 0.6944444444)
        w, h = width, round(height * 0.3055555556)
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
        raise ValueError(f"Crop is outside {width}x{height}: {x},{y},{w},{h}")
    return {"x": x, "y": y, "width": w, "height": h}


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def emit(ok: bool, op: str, data: Any, output_paths: list[str] | None = None) -> None:
    """Emit the mediaskills JSON contract (success on stdout; errors on stderr)."""
    if ok:
        print(
            json.dumps(
                {"ok": True, "op": op, "data": data, "output_paths": output_paths or []},
                ensure_ascii=False,
            )
        )
        return
    err = data.get("error", str(data)) if isinstance(data, dict) else str(data)
    print(json.dumps({"ok": False, "op": op, "error": err}, ensure_ascii=False), file=sys.stderr)

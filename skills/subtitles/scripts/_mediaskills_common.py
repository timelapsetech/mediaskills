"""Shared helpers for mediaskills portable scripts (vendored into each skill)."""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from shutil import which
from typing import Any

EXIT_OK = 0
EXIT_BAD_ARGS = 1
EXIT_MISSING_DEP = 2
EXIT_PROCESSING = 3


def emit_success(op: str, data: dict[str, Any], outputs: list[str] | None = None) -> None:
    print(json.dumps({"ok": True, "op": op, "data": data, "output_paths": outputs or []}))


def emit_error(op: str, err: str, *, code: int = EXIT_PROCESSING) -> None:
    print(json.dumps({"ok": False, "op": op, "error": err}), file=sys.stderr)
    sys.exit(code)


def emit_progress(stage: str, pct: float) -> None:
    print(json.dumps({"progress": pct, "stage": stage}), file=sys.stderr)


def require_cmd(cmd: str, op: str) -> None:
    if which(cmd) is None:
        emit_error(
            op,
            f"{cmd} not found on PATH. Install via install-media-tools skill "
            "(scripts/install.sh) or your system package manager.",
            code=EXIT_MISSING_DEP,
        )


def run(cmd: list[str], op: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or str(e))[:800]
        emit_error(op, f"Command failed: {err}", code=EXIT_PROCESSING)


def run_bytes(cmd: list[str], op: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode("utf-8", errors="replace")[:800]
        emit_error(op, f"Command failed: {err}", code=EXIT_PROCESSING)


def workspace_root() -> Path:
    """Directory containing `.agents/skills` (repo / workspace root)."""
    here = Path(__file__).resolve().parent
    for parent in (here, *here.parents):
        if (parent / ".agents" / "skills").is_dir():
            return parent
    return Path.cwd()


def mediaskills_dir() -> Path:
    data_dir = os.environ.get("MEDIASKILLS_DATA_DIR")
    if data_dir and data_dir.startswith("/"):
        return Path(data_dir)
    return workspace_root() / ".mediaskills"


def generated_dir() -> Path:
    out = mediaskills_dir() / "generated"
    out.mkdir(parents=True, exist_ok=True)
    return out


def resolve_output(input_path: str | None, suffix: str, explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    stem = Path(input_path).stem if input_path else "output"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    token = f"{ts}_{random.randint(1000, 9999)}"
    if suffix.startswith("."):
        name = f"{stem}_{token}{suffix}"
    else:
        label = suffix[1:] if suffix.startswith("_") else suffix
        if "." in label:
            base, ext = label.rsplit(".", 1)
            name = f"{stem}_{base}_{token}.{ext}"
        else:
            name = f"{stem}_{label}_{token}"
    return generated_dir() / name


def is_truthy(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def ffprobe_json(path: str, op: str) -> dict[str, Any]:
    require_cmd("ffprobe", op)
    result = run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            path,
        ],
        op,
    )
    return json.loads(result.stdout)


def probe_duration(path: str) -> float:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        text=True,
    ).strip()
    return float(out)


def summarize_probe(data: dict[str, Any]) -> dict[str, Any]:
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    return {
        "format": fmt.get("format_name"),
        "duration": fmt.get("duration"),
        "size": fmt.get("size"),
        "video": (
            {
                "codec": video.get("codec_name"),
                "width": video.get("width"),
                "height": video.get("height"),
            }
            if video
            else None
        ),
        "audio_codecs": [s.get("codec_name") for s in audio],
    }


def compare_probe_summaries(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    def summary(d: dict[str, Any]) -> dict[str, Any]:
        fmt = d.get("format", {})
        video = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), None)
        return {
            "duration": fmt.get("duration"),
            "size": fmt.get("size"),
            "video": f"{video.get('width')}x{video.get('height')}" if video else None,
        }

    return {"a": summary(a), "b": summary(b)}


def format_srt_ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{milli:03d}"


def format_vtt_ts(seconds: float) -> str:
    return format_srt_ts(seconds).replace(",", ".")


def parse_srt_ts(value: str) -> float:
    value = value.strip().replace(",", ".")
    h, m, rest = value.split(":")
    s = float(rest)
    return int(h) * 3600 + int(m) * 60 + s


def parse_srt(text: str) -> list[dict[str, Any]]:
    blocks = re.split(r"\n\s*\n", text.strip(), flags=re.MULTILINE)
    cues: list[dict[str, Any]] = []
    for block in blocks:
        lines = [ln.strip("\ufeff") for ln in block.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        idx = 1 if re.fullmatch(r"\d+", lines[0]) else 0
        if idx >= len(lines) or "-->" not in lines[idx]:
            continue
        start_s, end_s = [p.strip() for p in lines[idx].split("-->")]
        start_s = start_s.split()[0]
        end_s = end_s.split()[0]
        body = "\n".join(lines[idx + 1 :]).strip()
        if not body:
            continue
        cues.append(
            {
                "start": parse_srt_ts(start_s),
                "end": parse_srt_ts(end_s),
                "text": body,
            }
        )
    return cues


def cues_to_srt(cues: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for i, cue in enumerate(cues, 1):
        lines.append(str(i))
        lines.append(f"{format_srt_ts(cue['start'])} --> {format_srt_ts(cue['end'])}")
        lines.append(cue["text"])
        lines.append("")
    return "\n".join(lines)


def cues_to_vtt(cues: list[dict[str, Any]]) -> str:
    lines = ["WEBVTT", ""]
    for cue in cues:
        lines.append(f"{format_vtt_ts(cue['start'])} --> {format_vtt_ts(cue['end'])}")
        lines.append(cue["text"])
        lines.append("")
    return "\n".join(lines)


def text_to_cues(text: str, duration: float = 5.0) -> list[dict[str, Any]]:
    chunks = [c.strip() for c in re.split(r"(?<=[.!?])\s+|\n+", text) if c.strip()]
    if not chunks:
        chunks = [text.strip() or "[empty]"]
    each = max(1.5, duration / max(len(chunks), 1))
    cues = []
    t = 0.0
    for chunk in chunks:
        cues.append({"start": t, "end": t + each, "text": chunk})
        t += each
    return cues


def tc_to_frames(tc: str, fps: float) -> int:
    parts = tc.replace(";", ":").split(":")
    if len(parts) != 4:
        raise ValueError(f"Invalid timecode: {tc}")
    h, m, s, f = (int(p) for p in parts)
    fps_i = int(round(fps))
    return ((h * 3600 + m * 60 + s) * fps_i) + f


def frames_to_tc(frames: int, fps: float) -> str:
    fps_i = max(1, int(round(fps)))
    if frames < 0:
        frames = 0
    f = frames % fps_i
    total_s = frames // fps_i
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"


def tc_to_seconds(tc: str, fps: float) -> float:
    return tc_to_frames(tc, fps) / float(fps)


def seconds_to_tc(seconds: float, fps: float) -> str:
    return frames_to_tc(int(round(seconds * fps)), fps)


def parse_time_arg(value: str) -> float:
    """Parse seconds (float) or HH:MM:SS[.mmm] or HH:MM:SS:FF timecode."""
    if re.fullmatch(r"-?\d+(\.\d+)?", value):
        return float(value)
    if ":" in value:
        parts = value.replace(",", ".").split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        if len(parts) == 4:
            return tc_to_seconds(value, 30.0)
    raise ValueError(f"Unrecognized time format: {value}")


def add_input_arg(parser: argparse.ArgumentParser, *, required: bool = True) -> None:
    parser.add_argument(
        "--input",
        "-i",
        required=required,
        help="Path to input media file",
    )


def add_output_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output",
        "-o",
        help="Output path (default: workspace .mediaskills/generated/)",
    )


def validate_input_path(path: str, op: str) -> Path:
    p = Path(path)
    if not p.is_file():
        emit_error(op, f"Input file not found: {path}", code=EXIT_BAD_ARGS)
    return p


def main_wrapper(main_fn: Any) -> None:
    try:
        main_fn()
    except SystemExit:
        raise
    except ValueError as e:
        emit_error("unknown", str(e), code=EXIT_BAD_ARGS)
    except subprocess.CalledProcessError as e:
        detail = e.stderr or e.stdout or str(e)
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", errors="replace")
        emit_error("unknown", str(detail).strip()[:1200], code=EXIT_PROCESSING)
    except RuntimeError as e:
        emit_error("unknown", str(e), code=EXIT_PROCESSING)

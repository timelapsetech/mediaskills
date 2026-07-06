# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Extract still frames at a fixed time interval (default 1s) across the full video."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from _mediaskills_common import (
    add_input_arg,
    emit_error,
    emit_progress,
    emit_success,
    generated_dir,
    is_truthy,
    main_wrapper,
    probe_duration,
    require_cmd,
    run,
    seconds_to_tc,
    validate_input_path,
)

OP = "vision.extract_interval_frames"


def canonical_output(input_path: str, suffix: str) -> Path:
    """Stable output path for reuse checks (no timestamp token)."""
    stem = Path(input_path).stem if input_path else "output"
    label = suffix[1:] if suffix.startswith("_") else suffix
    if "." in label:
        base, ext = label.rsplit(".", 1)
        return generated_dir() / f"{stem}_{base}.{ext}"
    return generated_dir() / f"{stem}_{label}"


def probe_fps(path: str) -> float:
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=r_frame_rate",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            text=True,
        ).strip()
        if "/" in out:
            num, den = out.split("/", 1)
            n, d = float(num), float(den)
            return n / d if d else 29.97
        return float(out) if out else 29.97
    except (subprocess.CalledProcessError, ValueError, ZeroDivisionError):
        return 29.97


def probe_image(image_path: Path) -> dict:
    result = run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(image_path),
        ],
        OP,
    )
    data = json.loads(result.stdout)
    stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
        {},
    )
    fmt = data.get("format", {})
    size_bytes = fmt.get("size")
    try:
        size = int(size_bytes) if size_bytes is not None else image_path.stat().st_size
    except (TypeError, ValueError, OSError):
        size = None
    return {
        "width": stream.get("width"),
        "height": stream.get("height"),
        "size_bytes": size,
    }


def manifest_is_valid(manifest_path: Path, video: Path, interval: float) -> dict | None:
    if not manifest_path.is_file():
        return None
    try:
        doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if str(doc.get("input_path", "")).strip() != str(video.resolve()):
        return None
    doc_interval = float(doc.get("interval_seconds") or 0)
    if abs(doc_interval - interval) > 0.01:
        return None
    frames = doc.get("frames") or []
    if not frames:
        return None
    sample = frames[: min(5, len(frames))]
    for entry in sample:
        frame_path = entry.get("frame_path") or entry.get("path")
        if not frame_path or not Path(str(frame_path)).is_file():
            return None
    return doc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run extract_interval_frames.py --input clip.mp4 --interval 1",
    )
    add_input_arg(parser)
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between frames (default 1.0)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=3600,
        help="Maximum frames to keep (default 3600)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-extract even when a matching manifest exists",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    video = validate_input_path(args.input, OP)
    interval = max(0.1, float(args.interval))
    max_frames = max(1, int(args.max_frames))
    force = is_truthy(args.force)

    require_cmd("ffmpeg", OP)
    require_cmd("ffprobe", OP)

    duration = probe_duration(str(video))
    fps = probe_fps(str(video))

    frames_dir = generated_dir() / f"{video.stem}_interval_frames"
    canonical_manifest = canonical_output(str(video), "_interval_frames.json")

    if not force:
        candidates = [canonical_manifest, *sorted(
            generated_dir().glob(f"{video.stem}*interval_frames*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )]
        for candidate in candidates:
            doc = manifest_is_valid(candidate, video, interval)
            if doc:
                emit_progress("done", 100)
                emit_success(
                    OP,
                    {
                        "manifest_path": str(candidate),
                        "output_path": str(candidate),
                        "frames_dir": doc.get("frames_dir") or str(frames_dir),
                        "frame_count": doc.get("frame_count") or len(doc.get("frames") or []),
                        "interval_seconds": doc.get("interval_seconds", interval),
                        "duration_seconds": doc.get("duration_seconds", duration),
                        "reused": True,
                        "skip_reason": "interval_frames already extracted for this video and interval",
                    },
                    [str(candidate)],
                )
                return

    frames_dir.mkdir(parents=True, exist_ok=True)

    emit_progress("extracting frames", 10)
    pattern = str(frames_dir / "frame_%06d.jpg")
    ffmpeg_fps = 1.0 / interval
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-vf",
            f"fps={ffmpeg_fps}",
            "-q:v",
            "2",
            pattern,
        ],
        OP,
    )

    paths = sorted(frames_dir.glob("frame_*.jpg"))
    if len(paths) > max_frames:
        paths = paths[:max_frames]

    if not paths:
        emit_error(OP, "No frames extracted from video")

    frames: list[dict] = []
    output_paths: list[str] = []
    total = len(paths)
    for i, frame_path in enumerate(paths):
        start = round(i * interval, 3)
        end = round(min((i + 1) * interval, duration), 3)
        emit_progress("probing frames", 20 + 70 * (i + 1) / total)
        try:
            tech = probe_image(frame_path)
        except Exception:
            tech = {}

        entry = {
            "index": i,
            "time_seconds": start,
            "start_seconds": start,
            "end_seconds": end,
            "duration_seconds": round(end - start, 3),
            "start_timecode": seconds_to_tc(start, fps),
            "end_timecode": seconds_to_tc(end, fps),
            "path": str(frame_path),
            "frame_path": str(frame_path),
            "width": tech.get("width"),
            "height": tech.get("height"),
            "size_bytes": tech.get("size_bytes"),
        }
        frames.append(entry)
        output_paths.append(str(frame_path))

    manifest = {
        "input_path": str(video.resolve()),
        "sequence_type": "interval",
        "interval_seconds": interval,
        "duration_seconds": duration,
        "fps": fps,
        "frames_dir": str(frames_dir),
        "frames": frames,
        "frame_count": len(frames),
    }

    out_manifest = canonical_manifest
    out_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    output_paths.insert(0, str(out_manifest))

    emit_progress("done", 100)
    emit_success(
        OP,
        {
            "manifest_path": str(out_manifest),
            "output_path": str(out_manifest),
            "frames_dir": str(frames_dir),
            "frame_count": len(frames),
            "interval_seconds": interval,
            "duration_seconds": duration,
            "frames": frames[:20],
        },
        output_paths,
    )


if __name__ == "__main__":
    main_wrapper(main)

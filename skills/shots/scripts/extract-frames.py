# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Extract a midpoint still frame for every shot in a shots manifest."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from _mediaskills_common import (
    add_input_arg,
    add_output_arg,
    emit_error,
    emit_progress,
    emit_success,
    generated_dir,
    main_wrapper,
    require_cmd,
    resolve_output,
    seconds_to_tc,
    validate_input_path,
)

OP = "shots.extract_frames"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Example: uv run extract-frames.py --shots-path clip_shots.json\n"
            "Or: uv run extract-frames.py --input clip.mp4"
        ),
    )
    add_input_arg(parser, required=False)
    add_output_arg(parser)
    parser.add_argument(
        "--shots-path",
        "--manifest-path",
        dest="shots_path",
        help="Path to shots JSON from detect.py",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=500,
        help="Maximum number of frames to extract (default 500)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.35,
        help="Scene threshold when running detect inline (default 0.35)",
    )
    parser.add_argument(
        "--min-shot-seconds",
        type=float,
        default=0.5,
        help="Min shot length when running detect inline (default 0.5)",
    )
    return parser


def run_detect(input_path: str, threshold: float, min_shot_seconds: float) -> dict:
    detect_script = Path(__file__).resolve().parent / "detect.py"
    proc = subprocess.run(
        [
            sys.executable,
            str(detect_script),
            "--input",
            input_path,
            "--threshold",
            str(threshold),
            "--min-shot-seconds",
            str(min_shot_seconds),
        ],
        capture_output=True,
        text=True,
    )
    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    if not lines:
        err = (proc.stderr or "").strip()[:500] or "shots.detect produced no output"
        emit_error(OP, err)
    try:
        result = json.loads(lines[-1])
    except json.JSONDecodeError:
        emit_error(OP, f"shots.detect returned invalid JSON: {lines[-1][:200]}")
    if not result.get("ok"):
        emit_error(OP, result.get("error") or "shots.detect failed")
    manifest_path = (result.get("data") or {}).get("manifest_path")
    if not manifest_path or not Path(manifest_path).is_file():
        emit_error(OP, "shots.detect did not return a manifest_path")
    return json.loads(Path(manifest_path).read_text(encoding="utf-8"))


def extract_frame(input_path: str, time_seconds: float, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{time_seconds:.3f}",
            "-i",
            input_path,
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )


def probe_image(image_path: Path) -> dict:
    proc = subprocess.run(
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
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(proc.stdout)
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


def main() -> None:
    args = build_parser().parse_args()
    shots_path = args.shots_path
    input_path = args.input
    max_frames = max(1, int(args.max_frames))

    require_cmd("ffmpeg", OP)
    require_cmd("ffprobe", OP)

    manifest: dict
    if shots_path and Path(str(shots_path)).is_file():
        manifest = json.loads(Path(str(shots_path)).read_text(encoding="utf-8"))
        input_path = manifest.get("input_path") or input_path
    elif input_path:
        path = validate_input_path(input_path, OP)
        emit_progress("detecting shots", 5)
        manifest = run_detect(str(path), float(args.threshold), float(args.min_shot_seconds))
        input_path = manifest.get("input_path") or str(path)
    else:
        emit_error(OP, "Provide --shots-path (from detect.py) or --input", code=1)

    if not input_path or not Path(str(input_path)).is_file():
        emit_error(OP, f"Video not found: {input_path}")

    shots = list(manifest.get("shots") or [])
    if not shots:
        emit_error(OP, "No shots in manifest")

    if len(shots) > max_frames:
        shots = shots[:max_frames]

    fps = float(manifest.get("fps") or 29.97)
    video = Path(str(input_path))
    frames_dir = generated_dir() / f"{video.stem}_shot_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    frames: list[dict] = []
    output_paths: list[str] = []
    total = len(shots)
    for i, shot in enumerate(shots):
        start = float(shot["start_seconds"])
        end = float(shot["end_seconds"])
        mid = (start + end) / 2.0
        frame_path = frames_dir / f"shot_{int(shot.get('index', i)):04d}.jpg"
        emit_progress("extracting frames", 10 + 80 * (i + 1) / total)
        try:
            extract_frame(str(video), mid, frame_path)
        except subprocess.CalledProcessError as e:
            err = (e.stderr or b"").decode("utf-8", errors="replace")[:400]
            emit_error(OP, f"Frame extract failed at {mid:.3f}s: {err or e}")

        try:
            tech = probe_image(frame_path)
        except (subprocess.CalledProcessError, json.JSONDecodeError, OSError):
            tech = {}

        entry = {
            "index": int(shot.get("index", i)),
            "shot_index": int(shot.get("index", i)),
            "time_seconds": round(mid, 3),
            "start_seconds": round(start, 3),
            "end_seconds": round(end, 3),
            "duration_seconds": round(end - start, 3),
            "start_timecode": shot.get("start_timecode") or seconds_to_tc(start, fps),
            "end_timecode": shot.get("end_timecode") or seconds_to_tc(end, fps),
            "path": str(frame_path),
            "frame_path": str(frame_path),
            "scene_score": shot.get("scene_score"),
            "width": tech.get("width"),
            "height": tech.get("height"),
            "size_bytes": tech.get("size_bytes"),
        }
        frames.append(entry)
        shot["frame_path"] = str(frame_path)
        shot["mid_seconds"] = round(mid, 3)
        output_paths.append(str(frame_path))

    manifest["frames"] = frames
    manifest["shots"] = shots
    manifest["frame_count"] = len(frames)
    manifest["frames_dir"] = str(frames_dir)

    if shots_path and Path(str(shots_path)).is_file():
        out_manifest = Path(str(shots_path))
    elif args.output:
        out_manifest = resolve_output(str(input_path), "_shots.json", args.output)
    else:
        out_manifest = resolve_output(str(input_path), "_shots.json")
    out_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    output_paths.insert(0, str(out_manifest))

    emit_progress("done", 100)
    emit_success(
        OP,
        {
            "manifest_path": str(out_manifest),
            "shots_path": str(out_manifest),
            "output_path": str(out_manifest),
            "frames_dir": str(frames_dir),
            "frame_count": len(frames),
            "shot_count": len(shots),
            "frames": frames[:20],
        },
        output_paths,
    )


if __name__ == "__main__":
    main_wrapper(main)

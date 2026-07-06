# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Extract multiple time ranges into separate segment files."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from _mediaskills_common import (
    EXIT_BAD_ARGS,
    add_input_arg,
    emit_error,
    emit_progress,
    emit_success,
    generated_dir,
    main_wrapper,
    require_cmd,
    validate_input_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Example: uv run trim_multi.py --input clip.mp4 "
            '--segments-json \'[{"start":0,"end":1},{"start":1.5,"end":2}]\''
        ),
    )
    add_input_arg(parser)
    parser.add_argument(
        "--segments-json",
        help='JSON array of {"start": float, "end": float} objects',
    )
    parser.add_argument(
        "--segment",
        action="append",
        metavar="START:END",
        help="Segment as start:end in seconds (repeatable)",
    )
    return parser


def parse_segments(args: argparse.Namespace, op: str) -> list[dict[str, float]]:
    raw: list[dict[str, object]] = []
    if args.segments_json:
        try:
            parsed = json.loads(args.segments_json)
        except json.JSONDecodeError as e:
            emit_error(op, f"Invalid --segments-json: {e}", code=EXIT_BAD_ARGS)
        if not isinstance(parsed, list) or not parsed:
            emit_error(op, "segments must be a non-empty array", code=EXIT_BAD_ARGS)
        raw = parsed
    elif args.segment:
        for item in args.segment:
            if ":" not in item:
                emit_error(op, f"Invalid --segment {item!r}; use START:END", code=EXIT_BAD_ARGS)
            start_s, end_s = item.split(":", 1)
            raw.append({"start": float(start_s), "end": float(end_s)})
    else:
        emit_error(op, "Provide --segments-json or one or more --segment START:END", code=EXIT_BAD_ARGS)

    segments: list[dict[str, float]] = []
    for i, seg in enumerate(raw):
        if not isinstance(seg, dict):
            emit_error(op, f"segment {i} must be an object with start/end", code=EXIT_BAD_ARGS)
        try:
            start = float(seg["start"])
            end = float(seg["end"])
        except (KeyError, TypeError, ValueError):
            emit_error(op, f"segment {i} needs numeric start/end", code=EXIT_BAD_ARGS)
        if end <= start:
            emit_error(op, f"segment {i}: end must be greater than start", code=EXIT_BAD_ARGS)
        segments.append({"index": i, "start": start, "end": end})
    return segments


def main() -> None:
    args = build_parser().parse_args()
    op = "video.trim_multi"
    path = validate_input_path(args.input, op)
    require_cmd("ffmpeg", op)
    segments = parse_segments(args, op)

    out_dir = generated_dir()
    stem = path.stem
    segment_paths: list[Path] = []
    for seg in segments:
        name = f"{stem}_segment_{seg['index']}.mp4"
        segment_paths.append((out_dir / name).resolve())

    emit_progress("trimming", 5)
    outputs: list[str] = []
    count = len(segments)

    for i, (seg, seg_out) in enumerate(zip(segments, segment_paths, strict=True)):
        seg_out.parent.mkdir(parents=True, exist_ok=True)
        base_cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(seg["start"]),
            "-to",
            str(seg["end"]),
            "-i",
            str(path),
        ]
        result = subprocess.run([*base_cmd, "-c", "copy", str(seg_out)], capture_output=True, text=True)
        if result.returncode != 0:
            result = subprocess.run(
                [
                    *base_cmd,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "23",
                    "-c:a",
                    "aac",
                    "-movflags",
                    "+faststart",
                    str(seg_out),
                ],
                capture_output=True,
                text=True,
            )
        if result.returncode != 0 or not seg_out.is_file():
            emit_error(
                op,
                f"Failed to extract segment {i} (start={seg['start']} end={seg['end']})",
            )
        outputs.append(str(seg_out))
        emit_progress(f"segment_{i}", 5 + (i + 1) * 90 / count)

    rows = [
        {
            "index": seg["index"],
            "start": seg["start"],
            "end": seg["end"],
            "output_path": out_path,
        }
        for seg, out_path in zip(segments, outputs, strict=True)
    ]
    emit_progress("done", 100)
    emit_success(
        op,
        {
            "output_path": outputs[0] if outputs else None,
            "segment_paths": outputs,
            "segments": rows,
            "segment_count": len(outputs),
        },
        outputs,
    )


if __name__ == "__main__":
    main_wrapper(main)

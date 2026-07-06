# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Label TV program segments using black+silent gaps and probe frames.

For each black+silent separator, extracts a still before the gap start,
classifies it as content vs slate (OCR), and assigns labels to adjacent segments.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _mediaskills_common import (
    add_input_arg,
    add_output_arg,
    emit_progress,
    emit_success,
    generated_dir,
    main_wrapper,
    probe_duration,
    require_cmd,
    resolve_output,
    seconds_to_tc,
    validate_input_path,
)
from _segment_lib import (
    apply_probe_labels,
    build_content_segments,
    classify_probe_frame,
    detect_blacks,
    detect_silences,
    extract_frame,
    intersect_black_silence,
    ocr_image,
)

OP = "program_master.label_segments"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run label_segments.py --input program.mp4",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument("--noise", default="-30dB", help="Silence threshold (default -30dB)")
    parser.add_argument(
        "--min-duration",
        type=float,
        default=0.5,
        help="Minimum gap length in seconds (default 0.5)",
    )
    parser.add_argument(
        "--pixel-threshold",
        type=float,
        default=0.10,
        help="Black pixel ratio threshold (default 0.10)",
    )
    parser.add_argument(
        "--min-overlap",
        type=float,
        default=0.25,
        help="Min seconds black and silence must overlap (default 0.25)",
    )
    parser.add_argument(
        "--probe-offset-seconds",
        type=float,
        default=1.0,
        help="How far before each gap to grab the boundary still (default 1.0)",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=29.97,
        help="Timecode display fps (default 29.97)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    path = validate_input_path(args.input, OP)
    require_cmd("ffmpeg", OP)
    require_cmd("ffprobe", OP)

    noise = str(args.noise)
    min_duration = float(args.min_duration)
    pixel_threshold = float(args.pixel_threshold)
    min_overlap = float(args.min_overlap)
    probe_offset = float(args.probe_offset_seconds)
    fps = float(args.fps)

    duration = probe_duration(str(path))

    emit_progress("detecting black+silence gaps", 15)
    silences = detect_silences(str(path), noise=noise, min_duration=min_duration)
    blacks = detect_blacks(
        str(path),
        min_duration=min_duration,
        pixel_threshold=pixel_threshold,
    )
    gaps = intersect_black_silence(blacks, silences, min_overlap=min_overlap)

    frames_dir = generated_dir() / f"{path.stem}_segment_probes"
    frames_dir.mkdir(parents=True, exist_ok=True)

    emit_progress("extracting probe frames", 40)
    probes: list[dict] = []
    for i, gap in enumerate(gaps):
        probe_time = max(0.0, gap["start"] - probe_offset)
        frame_path = frames_dir / f"probe_gap_{i:04d}_{probe_time:.3f}s.jpg"
        extract_frame(str(path), probe_time, frame_path)
        ocr_text = ocr_image(frame_path)
        classification = classify_probe_frame(frame_path, ocr_text)
        probes.append(
            {
                "gap_index": i,
                "gap_start": gap["start"],
                "gap_end": gap["end"],
                "probe_time": probe_time,
                "probe_offset_seconds": probe_offset,
                "frame_path": str(frame_path),
                "ocr_text": ocr_text,
                "classification": classification,
            }
        )

    emit_progress("building labeled segments", 75)
    segments = build_content_segments(gaps, duration)
    apply_probe_labels(segments, probes)

    for seg in segments:
        seg["start_timecode"] = seconds_to_tc(seg["start"], fps)
        seg["end_timecode"] = seconds_to_tc(seg["end"], fps)
        if seg.get("segment_type") == "content" and not seg.get("label"):
            seg["label"] = "unlabeled"
            seg["label_source"] = "none"

    manifest_path = resolve_output(str(path), "_labeled_segments.json", args.output)
    manifest = {
        "input_path": str(path),
        "duration": duration,
        "fps": fps,
        "probe_offset_seconds": probe_offset,
        "black_silence_gaps": gaps,
        "silences": silences,
        "blacks": blacks,
        "probes": probes,
        "segments": segments,
        "frames_dir": str(frames_dir),
        "labeled_count": sum(
            1
            for s in segments
            if s.get("segment_type") == "content" and s.get("label") not in (None, "unlabeled")
        ),
        "content_segment_count": sum(1 for s in segments if s.get("segment_type") == "content"),
        "gap_count": len(gaps),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    emit_progress("done", 100)
    emit_success(
        OP,
        {
            **manifest,
            "output_path": str(manifest_path),
            "structure_path": str(manifest_path),
            "manifest_path": str(manifest_path),
        },
        [str(manifest_path), *[p["frame_path"] for p in probes]],
    )


if __name__ == "__main__":
    main_wrapper(main)

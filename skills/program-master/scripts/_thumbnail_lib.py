"""Select and extract representative program-segment thumbnail frames."""

from __future__ import annotations

import math
import subprocess
from fractions import Fraction
from pathlib import Path
from statistics import median
from typing import Any

from _embedded_timecode import embedded_timecode_at_seconds
from _segment_lib import _probe_luma_means


def fps_as_float(value: float | str) -> float:
    if isinstance(value, str) and "/" in value:
        return float(Fraction(value))
    return float(value)


def first_established_picture_frame(
    frame0: int,
    values: list[float],
    *,
    stable_frames: int = 4,
    plateau_ratio: float = 0.85,
    min_luma_rise: float = 2.0,
) -> int | None:
    """Return the first sustained frame near the upper luma plateau of a fade window."""
    stable = max(2, int(stable_frames))
    if len(values) < max(8, stable + 4):
        return None

    baseline = median(values[:4])
    top_count = max(stable, len(values) // 20)
    established = median(sorted(values)[-top_count:])
    rise = established - baseline
    if rise < float(min_luma_rise):
        return None

    ratio = min(0.98, max(0.5, float(plateau_ratio)))
    target = baseline + ratio * rise
    for index in range(0, len(values) - stable + 1):
        window = values[index : index + stable]
        if min(window) >= target:
            return frame0 + index
    return None


def _previous_gap(segments: list[dict[str, Any]], position: int) -> dict[str, Any] | None:
    if position <= 0:
        return None
    previous = segments[position - 1]
    if previous.get("segment_type") == "gap":
        return previous
    return None


def build_thumbnail_plan(
    manifest: dict[str, Any],
    *,
    source_path: str,
    fade_search_seconds: float = 10.0,
    video_stream: int = 0,
) -> list[dict[str, Any]]:
    """Choose one frame per content segment using fade and black-hold evidence."""
    fps_value = manifest.get("fps") or (manifest.get("embedded_timecode") or {}).get("fps")
    if not fps_value:
        raise ValueError("Manifest does not contain fps")
    fps = fps_as_float(fps_value)
    segments = manifest.get("segments") or []
    plan: list[dict[str, Any]] = []

    for position, segment in enumerate(segments):
        if segment.get("segment_type") != "content":
            continue
        start_frame = int(round(float(segment["start"]) * fps))
        end_frame = int(round(float(segment["end"]) * fps))
        last_frame = max(start_frame, end_frame - 1)
        selected = start_frame
        selection = "segment start"

        previous = _previous_gap(segments, position)
        evidence = (previous or {}).get("boundary_evidence") or {}
        black_end = evidence.get("black_end")
        if black_end is not None:
            black_end_frame = int(round(float(black_end) * fps))
            if black_end_frame > selected:
                selected = min(last_frame, black_end_frame)
                selection = "first picture after black hold"

        refinement = evidence.get("black_boundary_refinement") or {}
        if refinement.get("fade_in_detected"):
            search_count = min(
                max(0, end_frame - start_frame),
                max(8, int(math.ceil(max(0.25, fade_search_seconds) * fps))),
            )
            values = _probe_luma_means(
                source_path,
                start_frame=start_frame,
                count=search_count,
                fps=fps,
                video_stream=video_stream,
            )
            established = first_established_picture_frame(start_frame, values)
            if established is not None:
                selected = min(last_frame, established)
                selection = "first established picture after fade"

        selected = min(last_frame, max(start_frame, selected))
        embedded = manifest.get("embedded_timecode") or {}
        if embedded.get("timecode"):
            thumbnail_tc = embedded_timecode_at_seconds(
                str(embedded["timecode"]),
                embedded.get("fps") or fps_value,
                selected / fps,
            )
        else:
            nominal = max(1, int(round(fps)))
            total_seconds, frames = divmod(selected, nominal)
            hours, rem = divmod(total_seconds, 3600)
            minutes, seconds = divmod(rem, 60)
            thumbnail_tc = f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

        plan.append(
            {
                "segment_index": segment.get("index", position),
                "source_frame": selected,
                "embedded_tc": thumbnail_tc,
                "offset_frames_from_segment_start": selected - start_frame,
                "selection": selection,
            }
        )
    return plan


def extract_thumbnail_frames(
    source_path: str,
    plan: list[dict[str, Any]],
    *,
    output_dir: Path,
    width: int = 320,
    video_stream: int = 0,
) -> dict[int, Path]:
    """Decode the source once and extract all selected native frames in timeline order."""
    output_dir.mkdir(parents=True, exist_ok=True)
    frames = sorted({int(item["source_frame"]) for item in plan})
    if not frames:
        return {}

    select = "+".join(f"eq(n\\,{frame})" for frame in frames)
    pattern = output_dir / "thumbnail_%04d.jpg"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            source_path,
            "-map",
            f"0:v:{video_stream}",
            "-vf",
            f"select={select},scale={max(160, int(width))}:-2",
            "-fps_mode",
            "vfr",
            "-q:v",
            "2",
            "-start_number",
            "0",
            str(pattern),
        ],
        check=True,
    )

    paths = [output_dir / f"thumbnail_{index:04d}.jpg" for index in range(len(frames))]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"Expected {len(frames)} thumbnails; missing {len(missing)}")
    return dict(zip(frames, paths))

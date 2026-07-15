"""Shared helpers for program-master segmentation and TV segment labeling."""

from __future__ import annotations

import re
import subprocess
from fractions import Fraction
from pathlib import Path
from shutil import which
from statistics import median
from typing import Any


def detect_silences(
    input_path: str,
    *,
    noise: str = "-30dB",
    min_duration: float = 0.5,
    audio_stream: int = 0,
    audio_policy: str = "single",
) -> list[dict[str, float]]:
    if audio_policy not in {"single", "all"}:
        raise ValueError("audio_policy must be 'single' or 'all'")
    count = probe_audio_stream_count(input_path)
    if count <= 0:
        raise RuntimeError("Input has no audio streams; black+silence segmentation requires audio")
    if audio_policy == "single":
        if audio_stream < 0 or audio_stream >= count:
            raise ValueError(f"audio_stream {audio_stream} is outside available range 0..{count - 1}")
        return _detect_silences_for_stream(
            input_path,
            stream=audio_stream,
            noise=noise,
            min_duration=min_duration,
        )

    per_stream = [
        _detect_silences_for_stream(
            input_path,
            stream=stream,
            noise=noise,
            min_duration=min_duration,
        )
        for stream in range(count)
    ]
    return intersect_interval_sets(per_stream, min_duration=min_duration)


def probe_audio_stream_count(input_path: str) -> int:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            input_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return len([line for line in (proc.stdout or "").splitlines() if line.strip()])


def _detect_silences_for_stream(
    input_path: str,
    *,
    stream: int,
    noise: str,
    min_duration: float,
) -> list[dict[str, float]]:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-i",
            input_path,
            "-map",
            f"0:a:{stream}",
            "-af",
            f"silencedetect=noise={noise}:d={min_duration}",
            "-vn",
            "-sn",
            "-dn",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    text = proc.stderr or ""
    starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", text)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", text)]
    silences: list[dict[str, float]] = []
    for i, start in enumerate(starts):
        end = ends[i] if i < len(ends) else start + min_duration
        silences.append(
            {
                "start": start,
                "end": end,
                "duration": max(0.0, end - start),
            }
        )
    return silences


def intersect_interval_sets(
    interval_sets: list[list[dict[str, float]]],
    *,
    min_duration: float,
) -> list[dict[str, float]]:
    """Return intervals where every selected audio stream is silent."""
    if not interval_sets:
        return []
    current = [dict(interval) for interval in interval_sets[0]]
    for other in interval_sets[1:]:
        overlaps: list[dict[str, float]] = []
        for left in current:
            for right in other:
                start = max(float(left["start"]), float(right["start"]))
                end = min(float(left["end"]), float(right["end"]))
                if end - start >= min_duration:
                    overlaps.append({"start": start, "end": end, "duration": end - start})
        current = overlaps
        if not current:
            break
    return current


def detect_blacks(
    input_path: str,
    *,
    min_duration: float = 0.5,
    pixel_threshold: float = 0.01,
    picture_threshold: float = 0.98,
    refine_fades: bool = True,
    fade_handle_frames: int = 1,
    video_stream: int = 0,
) -> list[dict[str, Any]]:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-i",
            input_path,
            "-map",
            f"0:v:{video_stream}",
            "-vf",
            (
                f"blackdetect=d={min_duration}:pix_th={pixel_threshold}:"
                f"pic_th={picture_threshold}"
            ),
            "-an",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    blacks: list[dict[str, Any]] = []
    for match in re.finditer(
        r"black_start:([0-9.]+)\s+black_end:([0-9.]+)\s+black_duration:([0-9.]+)",
        proc.stderr or "",
    ):
        blacks.append(
            {
                "start": float(match.group(1)),
                "end": float(match.group(2)),
                "duration": float(match.group(3)),
            }
        )
    if not refine_fades or not blacks:
        return blacks
    fps = probe_video_fps(input_path, video_stream=video_stream)
    return refine_black_fade_boundaries(
        input_path,
        blacks,
        fps=fps,
        handle_frames=max(0, int(fade_handle_frames)),
        video_stream=video_stream,
    )


def probe_video_fps(input_path: str, *, video_stream: int = 0) -> float:
    """Return the exact average video frame rate as a float."""
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            f"v:{video_stream}",
            "-show_entries",
            "stream=avg_frame_rate,r_frame_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            input_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    for value in (proc.stdout or "").splitlines():
        value = value.strip()
        if value and value != "0/0":
            return float(Fraction(value))
    raise RuntimeError(f"Unable to determine video frame rate: {input_path}")


def _probe_luma_means(
    input_path: str,
    *,
    start_frame: int,
    count: int,
    fps: float,
    video_stream: int = 0,
) -> list[float]:
    """Read native-frame YAVG values from an exact, short frame window."""
    if count <= 0:
        return []
    seek_seconds = 0.0 if start_frame <= 0 else (start_frame - 0.5) / fps
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{seek_seconds:.9f}",
            "-i",
            input_path,
            "-map",
            f"0:v:{video_stream}",
            "-vf",
            (
                "signalstats,metadata=mode=print:"
                "key=lavfi.signalstats.YAVG:file=-"
            ),
            "-frames:v",
            str(count),
            "-an",
            "-sn",
            "-dn",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    values = [
        float(value)
        for value in re.findall(
            r"lavfi\.signalstats\.YAVG=([0-9.]+)",
            (proc.stdout or "") + "\n" + (proc.stderr or ""),
        )
    ]
    return values[:count]


def _baseline_tolerance(values: list[float]) -> tuple[float, float]:
    baseline = median(values)
    deviations = [abs(value - baseline) for value in values]
    return baseline, max(0.15, 6.0 * median(deviations))


def fade_up_anchor_frame(
    frame0: int,
    values: list[float],
    *,
    handle_frames: int = 1,
) -> int | None:
    """Return the mathematical black anchor before a gradual fade-up."""
    if len(values) < 7:
        return None
    baseline, tolerance = _baseline_tolerance(values[:4])
    first_changed: int | None = None
    for index in range(1, len(values) - 1):
        if (
            values[index] - baseline > tolerance
            and values[index + 1] - baseline > tolerance
        ):
            first_changed = index
            break
    if first_changed is None:
        return None

    ramp = values[first_changed : first_changed + 6]
    if len(ramp) < 4:
        return None
    steps = [right - left for left, right in zip(ramp, ramp[1:])]
    positive_steps = sum(step > 0.03 for step in steps)
    first_jump = ramp[0] - baseline
    if (
        first_jump <= 8.0
        and ramp[-1] - ramp[0] >= 0.4
        and max(ramp) - baseline >= 1.0
        and positive_steps >= 3
    ):
        return max(frame0, frame0 + first_changed - max(0, handle_frames))
    return None


def fade_down_anchor_frame(
    frame0: int,
    values: list[float],
    *,
    handle_frames: int = 1,
) -> int | None:
    """Return the mathematical black anchor after a gradual fade-down."""
    if len(values) < 7:
        return None
    baseline, tolerance = _baseline_tolerance(values[-4:])
    first_plateau: int | None = None
    for index in range(2, len(values) - 2):
        if all(abs(values[pos] - baseline) <= tolerance for pos in range(index, index + 3)):
            first_plateau = index
            break
    if first_plateau is None:
        return None

    ramp = values[max(0, first_plateau - 6) : first_plateau]
    if len(ramp) < 4:
        return None
    steps = [right - left for left, right in zip(ramp, ramp[1:])]
    negative_steps = sum(step < -0.03 for step in steps)
    if (
        ramp[0] - ramp[-1] >= 0.4
        and ramp[-1] - baseline <= 8.0
        and max(ramp) - baseline >= 1.0
        and negative_steps >= 3
    ):
        return frame0 + first_plateau + max(0, handle_frames)
    return None


def refine_black_fade_boundaries(
    input_path: str,
    blacks: list[dict[str, Any]],
    *,
    fps: float,
    handle_frames: int = 1,
    window_frames: int = 8,
    video_stream: int = 0,
) -> list[dict[str, Any]]:
    """Keep cut boundaries exact and move gradual fades to their black anchors."""
    refined: list[dict[str, Any]] = []
    window = max(6, int(window_frames))
    for black in blacks:
        item = dict(black)
        raw_start = float(black["start"])
        raw_end = float(black["end"])
        raw_start_frame = round(raw_start * fps)
        raw_end_frame = round(raw_end * fps)

        start_frame0 = max(0, raw_start_frame - window)
        start_values = _probe_luma_means(
            input_path,
            start_frame=start_frame0,
            count=(raw_start_frame - start_frame0) + window + 1,
            fps=fps,
            video_stream=video_stream,
        )
        fade_down_frame = fade_down_anchor_frame(
            start_frame0,
            start_values,
            handle_frames=handle_frames,
        )

        end_frame0 = max(0, raw_end_frame - window)
        end_values = _probe_luma_means(
            input_path,
            start_frame=end_frame0,
            count=window * 2 + 1,
            fps=fps,
            video_stream=video_stream,
        )
        fade_up_frame = fade_up_anchor_frame(
            end_frame0,
            end_values,
            handle_frames=handle_frames,
        )

        refined_start_frame = fade_down_frame if fade_down_frame is not None else raw_start_frame
        refined_end_frame = fade_up_frame if fade_up_frame is not None else raw_end_frame
        if refined_end_frame <= refined_start_frame:
            refined_start_frame = raw_start_frame
            refined_end_frame = raw_end_frame
            fade_down_frame = None
            fade_up_frame = None

        item["raw_start"] = raw_start
        item["raw_end"] = raw_end
        item["start"] = refined_start_frame / fps
        item["end"] = refined_end_frame / fps
        item["duration"] = max(0.0, item["end"] - item["start"])
        item["boundary_refinement"] = {
            "fps": fps,
            "raw_start_frame": raw_start_frame,
            "raw_end_frame": raw_end_frame,
            "refined_start_frame": refined_start_frame,
            "refined_end_frame": refined_end_frame,
            "fade_out_detected": fade_down_frame is not None,
            "fade_in_detected": fade_up_frame is not None,
            "fade_handle_frames": handle_frames,
        }
        refined.append(item)
    return refined


def overlap_seconds(a: dict[str, float], b: dict[str, float]) -> float:
    start = max(a["start"], b["start"])
    end = min(a["end"], b["end"])
    return max(0.0, end - start)


def intersect_black_silence(
    blacks: list[dict[str, Any]],
    silences: list[dict[str, float]],
    *,
    min_overlap: float = 0.25,
) -> list[dict[str, Any]]:
    """Return gaps where black video and silent audio overlap (TV break separators)."""
    gaps: list[dict[str, Any]] = []
    for black in blacks:
        for silence in silences:
            overlap = overlap_seconds(black, silence)
            if overlap < min_overlap:
                continue
            start = max(black["start"], silence["start"])
            end = min(black["end"], silence["end"])
            gap = {
                "start": start,
                "end": end,
                "duration": max(0.0, end - start),
                "black_start": black["start"],
                "black_end": black["end"],
                "silence_start": silence["start"],
                "silence_end": silence["end"],
                "start_source": "black" if black["start"] >= silence["start"] else "silence",
                "end_source": "black" if black["end"] <= silence["end"] else "silence",
            }
            if black.get("boundary_refinement"):
                gap["black_boundary_refinement"] = black["boundary_refinement"]
            gaps.append(gap)
    gaps.sort(key=lambda g: g["start"])
    return merge_adjacent_gaps(gaps, tolerance=0.05)


def merge_adjacent_gaps(gaps: list[dict[str, Any]], *, tolerance: float) -> list[dict[str, Any]]:
    if not gaps:
        return []
    merged: list[dict[str, Any]] = [dict(gaps[0])]
    for gap in gaps[1:]:
        prev = merged[-1]
        if gap["start"] <= prev["end"] + tolerance:
            prev["end"] = max(prev["end"], gap["end"])
            prev["duration"] = prev["end"] - prev["start"]
            continue
        merged.append(dict(gap))
    return merged


def normalize_terminal_gap(
    gaps: list[dict[str, Any]],
    *,
    duration: float,
    fps: float,
    tolerance_frames: int = 2,
) -> None:
    """Extend a detected tail gap through the exclusive video-stream end."""
    if not gaps or fps <= 0:
        return
    tail = gaps[-1]
    tolerance = max(1, int(tolerance_frames)) / fps
    if 0.0 <= duration - float(tail["end"]) <= tolerance:
        tail["end"] = duration
        tail["duration"] = max(0.0, duration - float(tail["start"]))
        tail["end_source"] = "stream_end"


def extract_frame(
    input_path: str,
    time_seconds: float,
    out_path: Path,
    *,
    video_stream: int = 0,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{time_seconds:.9f}",
            "-i",
            input_path,
            "-map",
            f"0:v:{video_stream}",
            "-frames:v",
            "1",
            "-update",
            "1",
            "-q:v",
            "2",
            "-pix_fmt",
            "yuvj420p",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )


def ocr_image(
    image_path: Path,
    *,
    mode: str = "optional",
    language: str = "eng",
    psm: int = 6,
) -> str:
    if mode not in {"off", "optional", "required"}:
        raise ValueError("OCR mode must be off, optional, or required")
    if mode == "off":
        return ""
    if which("tesseract") is None:
        if mode == "required":
            raise RuntimeError("tesseract is required by the selected OCR policy but is unavailable")
        return ""
    proc = subprocess.run(
        [
            "tesseract",
            str(image_path),
            "stdout",
            "--oem",
            "1",
            "--psm",
            str(max(3, min(13, int(psm)))),
            "-l",
            language,
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        if mode == "required":
            raise RuntimeError((proc.stderr or "tesseract OCR failed").strip())
        return ""
    return (proc.stdout or "").strip()


def normalize_ocr_text(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)


def looks_like_slate_text(text: str) -> bool:
    cleaned = normalize_ocr_text(text)
    if len(cleaned) < 4:
        return False
    letters = sum(ch.isalpha() for ch in cleaned)
    if letters < 3:
        return False
    words = [w for w in re.split(r"\s+", cleaned) if w]
    if len(words) >= 2:
        return True
    return len(cleaned) >= 8 and letters / max(len(cleaned), 1) >= 0.5


def classify_probe_frame(image_path: Path, ocr_text: str | None = None) -> dict[str, Any]:
    text = normalize_ocr_text(ocr_text if ocr_text is not None else ocr_image(image_path))
    if looks_like_slate_text(text):
        return {
            "kind": "slate",
            "text": text,
            "confidence": 0.75 if which("tesseract") else 0.4,
        }
    if text:
        return {
            "kind": "content",
            "text": text,
            "confidence": 0.6,
            "note": "incidental_on_screen_text",
        }
    return {
        "kind": "content",
        "text": "",
        "confidence": 0.5,
        "note": "no_readable_text",
    }


def build_content_segments(
    gaps: list[dict[str, Any]],
    duration: float,
    *,
    min_segment_seconds: float = 0.25,
) -> list[dict[str, Any]]:
    cuts = [0.0]
    for gap in gaps:
        cuts.append(gap["start"])
        cuts.append(gap["end"])
    cuts.append(duration)
    cuts = sorted(set(cuts))

    segments: list[dict[str, Any]] = []
    for i in range(len(cuts) - 1):
        start, end = cuts[i], cuts[i + 1]
        if end - start < min_segment_seconds:
            continue
        matching_gap = next(
            (
                gap
                for gap in gaps
                if abs(start - gap["start"]) < 0.05 and abs(end - gap["end"]) < 0.05
            ),
            None,
        )
        segment = {
            "index": len(segments),
            "start": start,
            "end": end,
            "duration": end - start,
            "segment_type": "gap" if matching_gap else "content",
        }
        if matching_gap:
            segment["boundary_evidence"] = {
                key: matching_gap[key]
                for key in (
                    "black_start",
                    "black_end",
                    "silence_start",
                    "silence_end",
                    "start_source",
                    "end_source",
                    "black_boundary_refinement",
                )
                if key in matching_gap
            }
        segments.append(segment)
    return segments


def find_segment_before_gap(
    segments: list[dict[str, Any]],
    gap_start: float,
    *,
    tolerance: float = 0.15,
) -> dict[str, Any] | None:
    for seg in segments:
        if seg.get("segment_type") != "content":
            continue
        if abs(seg["end"] - gap_start) <= tolerance:
            return seg
    return None


def find_segment_after_gap(
    segments: list[dict[str, Any]],
    gap_end: float,
    *,
    tolerance: float = 0.15,
) -> dict[str, Any] | None:
    for seg in segments:
        if seg.get("segment_type") != "content":
            continue
        if abs(seg["start"] - gap_end) <= tolerance:
            return seg
    return None


def apply_probe_labels(
    segments: list[dict[str, Any]],
    probes: list[dict[str, Any]],
) -> None:
    """Apply labels from probe frames taken before each black+silent gap."""
    for probe in probes:
        classification = probe.get("classification") or {}
        kind = classification.get("kind")
        text = (classification.get("text") or "").strip()
        gap_start = float(probe.get("gap_start") or 0)
        gap_end = float(probe.get("gap_end") or gap_start)

        if kind == "content":
            seg = find_segment_before_gap(segments, gap_start)
            if seg is None:
                continue
            seg["label"] = "content"
            seg["label_source"] = "probe_before_gap"
            seg["probe_frame_path"] = probe.get("frame_path")
            if text:
                seg["probe_note"] = text

        elif kind == "slate" and text:
            seg = find_segment_after_gap(segments, gap_end)
            if seg is None:
                continue
            seg["label"] = text
            seg["label_source"] = "slate_before_gap"
            seg["slate_text"] = text
            seg["probe_frame_path"] = probe.get("frame_path")

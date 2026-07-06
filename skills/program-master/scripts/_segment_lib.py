"""Shared helpers for program-master segmentation and TV segment labeling."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from shutil import which
from typing import Any


def detect_silences(
    input_path: str,
    *,
    noise: str = "-30dB",
    min_duration: float = 0.5,
) -> list[dict[str, float]]:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            input_path,
            "-af",
            f"silencedetect=noise={noise}:d={min_duration}",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
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


def detect_blacks(
    input_path: str,
    *,
    min_duration: float = 0.5,
    pixel_threshold: float = 0.10,
) -> list[dict[str, float]]:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            input_path,
            "-vf",
            f"blackdetect=d={min_duration}:pix_th={pixel_threshold}",
            "-an",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    blacks: list[dict[str, float]] = []
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
    return blacks


def overlap_seconds(a: dict[str, float], b: dict[str, float]) -> float:
    start = max(a["start"], b["start"])
    end = min(a["end"], b["end"])
    return max(0.0, end - start)


def intersect_black_silence(
    blacks: list[dict[str, float]],
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
            gaps.append(
                {
                    "start": start,
                    "end": end,
                    "duration": max(0.0, end - start),
                    "black_start": black["start"],
                    "black_end": black["end"],
                    "silence_start": silence["start"],
                    "silence_end": silence["end"],
                }
            )
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


def ocr_image(image_path: Path) -> str:
    if which("tesseract") is None:
        return ""
    proc = subprocess.run(
        ["tesseract", str(image_path), "stdout"],
        capture_output=True,
        text=True,
    )
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
        is_gap = any(
            abs(start - gap["start"]) < 0.05 and abs(end - gap["end"]) < 0.05 for gap in gaps
        )
        segments.append(
            {
                "index": len(segments),
                "start": start,
                "end": end,
                "duration": end - start,
                "segment_type": "gap" if is_gap else "content",
            }
        )
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

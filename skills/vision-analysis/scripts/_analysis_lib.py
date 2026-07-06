"""Manifest loading and analysis-document merge helpers (no vision API calls)."""

from __future__ import annotations

import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _mediaskills_common import emit_error

TEXT_TYPES = (
    "title",
    "lower_third",
    "subtitle",
    "locator",
    "graphic",
    "background_text",
    "credit",
    "other",
)

LOCATIONS = (
    "top",
    "bottom",
    "left",
    "right",
    "center",
    "full_screen",
    "unknown",
)


def as_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(as_string(v) for v in value if v)
    if value is None:
        return ""
    return str(value)


def coerce_frame_analysis(raw: dict[str, Any]) -> dict[str, Any]:
    keywords = [
        k.strip()
        for k in (as_string(v) for v in (raw.get("keywords") or []))
        for v in [k]
        if k and k != "..."
    ][:10]
    if not keywords:
        keywords = ["unclassified"]

    on_screen_text: list[dict[str, Any]] = []
    for item in raw.get("on_screen_text") or []:
        if not isinstance(item, dict):
            continue
        text_type_raw = as_string(item.get("text_type") or "other").split("|")[0].strip() or "other"
        text_type = text_type_raw.replace(" ", "_").lower()
        if text_type not in TEXT_TYPES:
            text_type = "other"
        location_raw = (
            as_string(item.get("location")).split("|")[0].strip().replace(" ", "_").lower()
            if item.get("location") is not None
            else None
        )
        location = location_raw if location_raw in LOCATIONS else None
        confidence = item.get("confidence")
        if isinstance(confidence, (int, float)):
            confidence = max(0.0, min(1.0, float(confidence)))
        else:
            confidence = None
        text = as_string(item.get("text")).strip()
        if not text or text == "...":
            continue
        entry: dict[str, Any] = {"text": text, "text_type": text_type}
        if location:
            entry["location"] = location
        if confidence is not None:
            entry["confidence"] = confidence
        on_screen_text.append(entry)

    description = as_string(raw.get("description")).strip()
    if not description or description == "...":
        description = "No description available."

    return {
        "description": description,
        "keywords": keywords,
        "on_screen_text": on_screen_text,
    }


def frame_path(frame: dict[str, Any]) -> str | None:
    p = frame.get("frame_path") or frame.get("path")
    return str(p) if p else None


def frame_key(frame: dict[str, Any]) -> str:
    return str(frame.get("shot_index") or frame.get("index") or frame.get("frame_path") or frame.get("path") or "")


def default_analysis_path(manifest_path: str) -> Path:
    directory = Path(manifest_path).parent
    stem = Path(manifest_path).stem
    base = re.sub(r"_shots(_\d+_\d+)?$", "", stem) or stem
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    token = random.randint(1000, 9999)
    return directory / f"{base}_frame_analysis_{ts}_{token}.json"


def find_existing_analysis_path(manifest_path: str) -> Path | None:
    directory = Path(manifest_path).parent
    resolved_manifest = Path(manifest_path).resolve()
    if not directory.is_dir():
        return None
    for candidate in sorted(directory.glob("*frame_analysis*.json"), reverse=True):
        try:
            doc = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        doc_manifest = doc.get("manifest_path")
        if not doc_manifest:
            continue
        try:
            if Path(str(doc_manifest)).resolve() == resolved_manifest:
                return candidate.resolve()
        except OSError:
            continue
    return None


def resolve_manifest_path_from_analysis(analysis_path: str) -> str | None:
    try:
        doc = json.loads(Path(analysis_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    mp = str(doc.get("manifest_path") or "").strip()
    return mp or None


def manifest_base_stem(manifest_path: str, input_path: str | None) -> str:
    if input_path:
        return Path(input_path).stem
    stem = Path(manifest_path).stem
    shots_idx = stem.find("_shots")
    return stem[:shots_idx] if shots_idx >= 0 else stem


def discover_frames_dir(manifest_path: str, data: dict[str, Any]) -> Path | None:
    candidates: list[Path] = []
    frames_dir = data.get("frames_dir")
    if isinstance(frames_dir, str) and frames_dir.strip():
        candidates.append(Path(frames_dir.strip()))
    directory = Path(manifest_path).parent
    base = manifest_base_stem(manifest_path, data.get("input_path"))
    candidates.append(directory / f"{base}_shot_frames")
    candidates.append(directory / f"{base}_interval_frames")
    stem = Path(manifest_path).stem
    candidates.append(directory / f"{stem}_shot_frames")
    candidates.append(directory / f"{stem}_interval_frames")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def frames_from_disk_dir(frames_dir: Path, shots: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    jpgs = sorted(frames_dir.glob("*.jp*g"), key=lambda p: p.name.lower())
    if not jpgs:
        return []

    shot_by_index: dict[int, dict[str, Any]] = {}
    for shot in shots or []:
        idx = shot.get("shot_index", shot.get("index"))
        if isinstance(idx, int):
            shot_by_index[idx] = shot

    frames: list[dict[str, Any]] = []
    for i, img_path in enumerate(jpgs):
        match = re.search(r"(\d+)", img_path.name)
        idx = int(match.group(1)) if match else i
        shot = shot_by_index.get(idx)
        mid = None
        if shot:
            mid = shot.get("mid_seconds")
            if mid is None and shot.get("start_seconds") is not None and shot.get("end_seconds") is not None:
                mid = (float(shot["start_seconds"]) + float(shot["end_seconds"])) / 2
            if mid is None:
                mid = shot.get("time_seconds")
        frames.append(
            {
                "index": idx,
                "shot_index": idx,
                "frame_path": str(img_path),
                "path": str(img_path),
                "time_seconds": mid,
                "start_seconds": shot.get("start_seconds") if shot else None,
                "end_seconds": shot.get("end_seconds") if shot else None,
                "start_timecode": shot.get("start_timecode") if shot else None,
                "end_timecode": shot.get("end_timecode") if shot else None,
                "duration_seconds": shot.get("duration_seconds") if shot else None,
                "width": shot.get("width") if shot else None,
                "height": shot.get("height") if shot else None,
            }
        )
    return frames


def collect_manifest_frames(manifest_path: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_frames = data.get("frames") or []
    from_frames = [f for f in raw_frames if isinstance(f, dict) and frame_path(f)]
    if from_frames:
        return from_frames

    shots = data.get("shots") or []
    from_shots = [s for s in shots if isinstance(s, dict) and frame_path(s)]
    if from_shots:
        return from_shots

    frames_dir = discover_frames_dir(manifest_path, data)
    if frames_dir:
        return frames_from_disk_dir(frames_dir, shots if isinstance(shots, list) else None)
    return []


def load_manifest(manifest_path: str, op: str) -> dict[str, Any]:
    resolved = Path(manifest_path).resolve()
    lower = str(resolved).lower()
    if re.search(r"\.(mp4|mov|mkv|avi|webm|m4v|mp3|wav|aac|flac|jpg|jpeg|png|gif|webp|bmp)$", lower):
        emit_error(op, f"Expected a frames manifest JSON, not a media file: {resolved}", code=1)

    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        emit_error(op, f"Manifest is not valid JSON: {resolved}", code=1)

    frames = collect_manifest_frames(str(resolved), data)
    frames_dir = data.get("frames_dir")
    if not frames_dir and frames:
        first = frame_path(frames[0])
        if first:
            frames_dir = str(Path(first).parent)
    if not frames_dir:
        discovered = discover_frames_dir(str(resolved), data)
        frames_dir = str(discovered) if discovered else None

    return {
        "manifest_path": str(resolved),
        "frames": frames,
        "input_path": data.get("input_path"),
        "frames_dir": frames_dir,
    }


def load_or_create_analysis(
    analysis_path: Path,
    manifest_path: str,
    input_path: str | None,
) -> dict[str, Any]:
    if analysis_path.is_file():
        try:
            existing = json.loads(analysis_path.read_text(encoding="utf-8"))
            if isinstance(existing.get("frames"), list):
                return existing
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "manifest_path": manifest_path,
        "input_path": input_path,
        "frames": [],
        "frame_count": 0,
        "analyzed_count": 0,
    }


def build_frame_entry(
    frame: dict[str, Any],
    analysis: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    img = frame_path(frame)
    return {
        "index": frame.get("index", frame.get("shot_index")),
        "shot_index": frame.get("shot_index", frame.get("index")),
        "time_seconds": frame.get("time_seconds"),
        "start_seconds": frame.get("start_seconds"),
        "end_seconds": frame.get("end_seconds"),
        "start_timecode": frame.get("start_timecode"),
        "end_timecode": frame.get("end_timecode"),
        "path": img,
        "frame_path": img,
        "description": (analysis or {}).get("description", ""),
        "keywords": (analysis or {}).get("keywords", []),
        "on_screen_text": (analysis or {}).get("on_screen_text", []),
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "error": error,
    }


def merge_frame_results(doc: dict[str, Any], batch_results: list[dict[str, Any]]) -> dict[str, Any]:
    by_key = {frame_key(f): f for f in doc.get("frames") or []}
    for entry in batch_results:
        by_key[frame_key(entry)] = entry
    frames = sorted(
        by_key.values(),
        key=lambda f: (f.get("shot_index") or f.get("index") or 0),
    )
    analyzed_count = sum(1 for f in frames if not f.get("error") and f.get("description"))
    return {**doc, "frames": frames, "analyzed_count": analyzed_count}


def manifest_frame_lookup(manifest_frames: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for frame in manifest_frames:
        lookup[frame_key(frame)] = frame
        if frame.get("index") is not None:
            lookup[str(frame["index"])] = frame
        if frame.get("shot_index") is not None:
            lookup[str(frame["shot_index"])] = frame
    return lookup


def normalize_agent_frame(
    agent_frame: dict[str, Any],
    manifest_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    key = frame_key(agent_frame)
    if not key and agent_frame.get("index") is not None:
        key = str(agent_frame["index"])
    manifest_frame = manifest_lookup.get(key) or manifest_lookup.get(str(agent_frame.get("index", "")))
    if not manifest_frame:
        emit_error(
            "vision.merge_analysis",
            f"Agent frame does not match manifest (index/path): {agent_frame}",
            code=1,
        )

    raw_analysis = {
        "description": agent_frame.get("description"),
        "keywords": agent_frame.get("keywords"),
        "on_screen_text": agent_frame.get("on_screen_text"),
    }
    analysis = coerce_frame_analysis(raw_analysis)
    return build_frame_entry(manifest_frame, analysis)


def validate_analysis_document(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc.get("frames"), list):
        errors.append("frames must be an array")
        return errors
    for i, frame in enumerate(doc["frames"]):
        if not isinstance(frame, dict):
            errors.append(f"frames[{i}] must be an object")
            continue
        if not frame.get("description"):
            errors.append(f"frames[{i}] missing description")
        for j, item in enumerate(frame.get("on_screen_text") or []):
            if not isinstance(item, dict):
                errors.append(f"frames[{i}].on_screen_text[{j}] must be an object")
                continue
            if not item.get("text"):
                errors.append(f"frames[{i}].on_screen_text[{j}] missing text")
            tt = item.get("text_type")
            if tt and tt not in TEXT_TYPES:
                errors.append(f"frames[{i}].on_screen_text[{j}] invalid text_type: {tt}")
    return errors

"""Load and validate versioned program-master run profiles."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from _provenance_lib import sha256_file

PROFILE_VERSION = "1.0"
DEFAULT_PROFILE = Path(__file__).resolve().parents[1] / "profiles" / "broadcast-default.json"


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def validate_profile(profile: dict[str, Any]) -> None:
    if str(profile.get("profile_version")) != PROFILE_VERSION:
        raise ValueError(
            f"Unsupported profile_version {profile.get('profile_version')!r}; expected {PROFILE_VERSION}"
        )
    streams = profile.get("streams") or {}
    if streams.get("audio_policy") not in {"single", "all"}:
        raise ValueError("streams.audio_policy must be 'single' or 'all'")
    timecode = profile.get("timecode") or {}
    if timecode.get("mode") not in {"embedded", "file"}:
        raise ValueError("timecode.mode must be 'embedded' or 'file'")
    ocr = profile.get("ocr") or {}
    if ocr.get("mode") not in {"off", "optional", "required"}:
        raise ValueError("ocr.mode must be 'off', 'optional', or 'required'")
    labels = profile.get("labels") or {}
    if labels.get("mode") not in {"generic", "raw"}:
        raise ValueError("labels.mode must be 'generic' or 'raw'")
    if not isinstance(labels.get("require_overrides_for_content", False), bool):
        raise ValueError("labels.require_overrides_for_content must be true or false")


def load_profile(path: str | None = None) -> tuple[dict[str, Any], Path]:
    default = json.loads(DEFAULT_PROFILE.read_text(encoding="utf-8"))
    selected = Path(path).expanduser().resolve() if path else DEFAULT_PROFILE
    if not selected.is_file():
        raise ValueError(f"Profile not found: {selected}")
    overlay = json.loads(selected.read_text(encoding="utf-8"))
    profile = deep_merge(default, overlay)
    validate_profile(profile)
    return profile, selected


def load_label_overrides(path: str | None) -> dict[int, str]:
    if not path:
        return {}
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"Label override file not found: {source}")
    data = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("segments"), list):
        rows = data["segments"]
        return {
            int(row["index"]): str(row["label"])
            for row in rows
            if row.get("index") is not None and row.get("label")
        }
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        rows = data["rows"]
        return {
            int(row["index"]): str(row["label"])
            for row in rows
            if row.get("index") is not None and row.get("label")
        }
    labels = data.get("labels", data) if isinstance(data, dict) else {}
    if not isinstance(labels, dict):
        raise ValueError("Label overrides must be an object or a report with rows/segments")
    return {int(index): str(label) for index, label in labels.items()}


def effective_label_overrides(profile: dict[str, Any], path: str | None = None) -> dict[int, str]:
    configured = {
        int(index): str(label)
        for index, label in ((profile.get("labels") or {}).get("overrides") or {}).items()
    }
    configured.update(load_label_overrides(path))
    return configured


def validate_label_overrides(
    manifest: dict[str, Any],
    overrides: dict[int, str],
    *,
    require_content: bool = False,
) -> None:
    segments = manifest.get("segments") or []
    indices = {int(segment["index"]) for segment in segments}
    unknown = sorted(set(overrides) - indices)
    if unknown:
        raise ValueError(f"Label overrides reference unknown segment indices: {unknown}")
    empty = sorted(index for index, label in overrides.items() if not str(label).strip())
    if empty:
        raise ValueError(f"Label overrides are empty for segment indices: {empty}")
    if require_content:
        content = {
            int(segment["index"])
            for segment in segments
            if segment.get("segment_type") == "content"
        }
        missing = sorted(content - set(overrides))
        if missing:
            raise ValueError(f"Editorial labels are required for content segment indices: {missing}")


def label_override_provenance(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"Label override file not found: {source}")
    return {"path": str(source), "sha256": sha256_file(source)}

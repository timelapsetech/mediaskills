"""Shared helpers for vision analysis report scripts."""

from __future__ import annotations

import csv
import json
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from _mediaskills_common import emit_success, generated_dir, is_truthy, seconds_to_tc

ALL_TEXT_TYPES = (
    "title",
    "lower_third",
    "subtitle",
    "locator",
    "graphic",
    "background_text",
    "credit",
    "other",
)

_PLACEHOLDER_TEXT = {
    "jane doe",
    "john smith",
    "jane",
    "john",
    "middle of screen",
    "studio",
    "a news anchor at a desk.",
}

_SCENE_DESCRIPTION_PATTERNS = (
    re.compile(
        r"^(a|an|the)\s+\w+(\s+\w+){0,4}\s+"
        r"(wading|standing|sitting|walking|running|holding|wearing|looking|talking|working|logging|fishing|hunting)\b",
        re.I,
    ),
    re.compile(r"^interview with\b", re.I),
    re.compile(r"^(outdoor|indoor)\s+\w+", re.I),
    re.compile(r"^(close[- ]?up|wide shot|aerial view|news anchor)\b", re.I),
    re.compile(r"\breporter\.?$", re.I),
    re.compile(r"^(a|an|the)\s+\w+.*\b(with|in|on|at)\b", re.I),
)

_STOP_WORDS = frozenset(
    {"a", "an", "the", "in", "on", "at", "with", "of", "and", "to", "is", "are"}
)


def _content_words(text: str) -> list[str]:
    return [
        w
        for w in re.sub(r"[^\w\s]", " ", text.lower()).split()
        if len(w) > 2 and w not in _STOP_WORDS
    ]


def _text_matches_scene_description(text: str, description: str) -> bool:
    t = (text or "").strip().lower().rstrip(".")
    d = (description or "").strip().lower().rstrip(".")
    if not t or not d:
        return False
    if t == d:
        return True
    if len(t) >= 8 and t in d:
        return True
    if len(d) >= 8 and d in t:
        return True
    tw = _content_words(t)
    if not tw:
        return False
    dw = set(_content_words(d))
    overlap = sum(1 for w in tw if w in dw)
    return overlap / len(tw) >= 0.65


def _looks_like_scene_description(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if re.search(r"\breporter\.?$", t, re.I):
        return True
    if any(pat.search(t) for pat in _SCENE_DESCRIPTION_PATTERNS):
        words = len(t.split())
        if 3 <= words <= 12 and not re.search(r"[?!]", t):
            return True
    return False


def _is_scene_description(text: str, frame_description: str | None = None) -> bool:
    if _looks_like_scene_description(text):
        return True
    if frame_description and _text_matches_scene_description(text, frame_description):
        return True
    return False


def _is_placeholder(text: str) -> bool:
    norm = " ".join((text or "").lower().split())
    if not norm:
        return True
    if norm in _PLACEHOLDER_TEXT:
        return True
    if norm.replace(".", "", 1).isdigit():
        return True
    if _is_scene_description(text):
        return True
    return False


def _looks_like_dialogue(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) < 8 or _is_placeholder(t):
        return False
    if len(t.split()) <= 3 and t.istitle():
        return False
    if any(ch in t for ch in ".!?"):
        return True
    return bool(
        re.match(
            r"^(I|We|You|He|She|They|It|No|Yes|What|Why|How|Don't|Can't|Won't)\b",
            t,
            re.I,
        )
    ) or len(t.split()) >= 5


def refine_text_type(text: str, text_type: str, location: str | None = None) -> str:
    base = (text_type or "other").replace(" ", "_").lower()
    if base not in ALL_TEXT_TYPES:
        base = "other"
    if base in {"lower_third", "graphic", "title", "other"} and _looks_like_dialogue(text):
        return "subtitle"
    return base


def salvage_on_screen_text(description: str) -> list[dict[str, Any]]:
    trimmed = (description or "").strip()
    if not trimmed.startswith("{"):
        return []
    start = trimmed.find("{")
    end = trimmed.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(trimmed[start : end + 1])
            items = parsed.get("on_screen_text") or []
            if isinstance(items, list):
                out: list[dict[str, Any]] = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    text = str(item.get("text") or "").strip()
                    if not text or _is_placeholder(text):
                        continue
                    out.append(item)
                if out:
                    return out
        except json.JSONDecodeError:
            pass
    out = []
    for match in re.finditer(
        r'"text"\s*:\s*"((?:\\.|[^"\\])*)"(?:\s*,\s*"text_type"\s*:\s*"([^"]*)")?',
        trimmed,
    ):
        text = match.group(1).replace('\\"', '"').strip()
        if not text or _is_placeholder(text):
            continue
        item: dict[str, Any] = {"text": text}
        if match.group(2):
            item["text_type"] = match.group(2)
        out.append(item)
    return out


def frame_on_screen_items(frame: dict[str, Any]) -> list[dict[str, Any]]:
    """Merged on_screen_text; drops scene-description hallucinations from the vision model."""
    frame_description = str(frame.get("description") or "")
    items = [
        dict(item)
        for item in (frame.get("on_screen_text") or [])
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    ]
    if not items:
        items = salvage_on_screen_text(frame_description)
    normalized: list[dict[str, Any]] = []
    for item in items:
        text = str(item.get("text") or "").strip()
        if not text or _is_placeholder(text):
            continue
        if _is_scene_description(text, frame_description):
            continue
        location = item.get("location")
        loc = str(location) if location is not None else None
        text_type = refine_text_type(text, str(item.get("text_type") or "other"), loc)
        normalized.append({**item, "text": text, "text_type": text_type})
    return normalized


def _normalized_prefix(name: str) -> str:
    stem = name.lower()
    marker = "_frame_analysis"
    if marker in stem:
        stem = stem.split(marker, 1)[0]
    return re.sub(r"[^a-z0-9]", "", stem)


def _frame_analysis_candidates(search_dir: Path) -> list[Path]:
    if not search_dir.is_dir():
        return []
    return sorted(
        (p for p in search_dir.glob("*frame_analysis*.json") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def resolve_analysis_path(
    analysis_path: str,
    manifest_path: str | None = None,
) -> Path:
    """Resolve analysis JSON on disk; recover from manifest link or fuzzy stem match."""
    direct = Path(analysis_path)
    if direct.is_file():
        return direct.resolve()

    resolved_manifest: Path | None = None
    if manifest_path:
        mp = Path(manifest_path)
        if mp.is_file():
            resolved_manifest = mp.resolve()

    search_dir = resolved_manifest.parent if resolved_manifest else direct.parent
    candidates = _frame_analysis_candidates(search_dir)
    if not candidates:
        raise FileNotFoundError(f"Analysis file not found: {analysis_path}")

    if resolved_manifest:
        for candidate in candidates:
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

    target_prefix = _normalized_prefix(direct.name)
    if target_prefix:
        for candidate in candidates:
            if _normalized_prefix(candidate.name) == target_prefix:
                return candidate.resolve()

    wrong_stem = direct.stem.split("_frame_analysis", 1)[0]
    video_hint = wrong_stem.split("_interval_frames", 1)[0].split("_shots", 1)[0]
    hint_norm = re.sub(r"[^a-z0-9]", "", video_hint.lower())
    if hint_norm:
        for candidate in candidates:
            cand_stem = candidate.stem.split("_frame_analysis", 1)[0]
            cand_hint = cand_stem.split("_interval_frames", 1)[0].split("_shots", 1)[0]
            if re.sub(r"[^a-z0-9]", "", cand_hint.lower()) == hint_norm:
                return candidate.resolve()

    raise FileNotFoundError(
        f"Analysis file not found: {analysis_path}"
        + (f" (also tried manifest_path={manifest_path})" if manifest_path else "")
    )


def load_analysis(
    analysis_path: str,
    manifest_path: str | None = None,
) -> dict[str, Any]:
    path = resolve_analysis_path(analysis_path, manifest_path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_analysis_resolved(
    analysis_path: str,
    manifest_path: str | None = None,
) -> tuple[dict[str, Any], Path]:
    path = resolve_analysis_path(analysis_path, manifest_path)
    return json.loads(path.read_text(encoding="utf-8")), path


def flatten_text_rows(
    analysis: dict[str, Any],
    include_types: set[str] | None = None,
    exclude_types: set[str] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for frame in analysis.get("frames") or []:
        items = frame_on_screen_items(frame)
        for item in items:
            text = (item.get("text") or "").strip()
            if not text:
                continue
            text_type = refine_text_type(
                text,
                str(item.get("text_type") or "other"),
                str(item.get("location")) if item.get("location") is not None else None,
            )
            if include_types is not None and text_type not in include_types:
                continue
            if exclude_types is not None and text_type in exclude_types:
                continue
            rows.append(
                {
                    "shot_index": frame.get("shot_index", frame.get("index")),
                    "start_seconds": frame.get("start_seconds"),
                    "end_seconds": frame.get("end_seconds"),
                    "start_timecode": frame.get("start_timecode"),
                    "end_timecode": frame.get("end_timecode"),
                    "time_seconds": frame.get("time_seconds"),
                    "text": text,
                    "text_type": text_type,
                    "location": item.get("location"),
                    "confidence": item.get("confidence"),
                    "frame_path": frame.get("frame_path") or frame.get("path"),
                    "description": frame.get("description"),
                    "keywords": frame.get("keywords") or [],
                }
            )
    return rows


def _norm_text(text: str) -> str:
    return " ".join((text or "").lower().split())


def texts_similar(a: str, b: str) -> bool:
    na, nb = _norm_text(a), _norm_text(b)
    if not na and not nb:
        return True
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    return False


def _row_start_seconds(row: dict[str, Any]) -> float:
    for key in ("start_seconds", "time_seconds"):
        val = row.get(key)
        if val is not None:
            return float(val)
    return 0.0


def _row_end_seconds(row: dict[str, Any]) -> float:
    end = row.get("end_seconds")
    if end is not None:
        return float(end)
    return _row_start_seconds(row)


def _infer_fps(analysis: dict[str, Any] | None) -> float:
    if not analysis:
        return 29.97
    for key in ("fps", "frame_rate"):
        val = analysis.get(key)
        if val is not None:
            try:
                fps = float(val)
                if fps > 0:
                    return fps
            except (TypeError, ValueError):
                pass
    return 29.97


def _finalize_condensed_row(row: dict[str, Any], fps: float | None) -> dict[str, Any]:
    out = dict(row)
    start = _row_start_seconds(out)
    end = _row_end_seconds(out)
    out["start_seconds"] = start
    out["end_seconds"] = end
    if fps and fps > 0:
        out["start_timecode"] = seconds_to_tc(start, fps)
        out["end_timecode"] = seconds_to_tc(end, fps)
    spans = int(out.pop("span_count", 1) or 1)
    if spans > 1:
        out["source_frame_count"] = spans
    return out


def condense_text_rows(
    rows: list[dict[str, Any]],
    *,
    max_gap_seconds: float = 2.5,
    fps: float | None = None,
) -> list[dict[str, Any]]:
    if not rows:
        return []

    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        text_type = str(row.get("text_type") or "other")
        norm = _norm_text(str(row.get("text") or ""))
        if not norm:
            continue
        groups.setdefault((text_type, norm), []).append(row)

    merged: list[dict[str, Any]] = []
    for group_rows in groups.values():
        group_rows.sort(key=_row_start_seconds)
        run: dict[str, Any] | None = None
        for row in group_rows:
            start = _row_start_seconds(row)
            end = _row_end_seconds(row)
            if run is None:
                run = dict(row)
                run["start_seconds"] = start
                run["end_seconds"] = end
                run["span_count"] = 1
                continue

            gap = start - float(run["end_seconds"])
            if gap <= max_gap_seconds:
                if end > float(run["end_seconds"]):
                    run["end_seconds"] = end
                    if row.get("end_timecode"):
                        run["end_timecode"] = row["end_timecode"]
                candidate = str(row.get("text") or "")
                current = str(run.get("text") or "")
                if len(candidate) > len(current):
                    run["text"] = candidate
                run["span_count"] = int(run.get("span_count") or 1) + 1
            else:
                merged.append(_finalize_condensed_row(run, fps))
                run = dict(row)
                run["start_seconds"] = start
                run["end_seconds"] = end
                run["span_count"] = 1

        if run is not None:
            merged.append(_finalize_condensed_row(run, fps))

    merged.sort(key=_row_start_seconds)
    return merged


def merge_adjacent_rows(
    rows: list[dict[str, Any]],
    *,
    max_gap_seconds: float = 2.5,
    fps: float | None = None,
) -> list[dict[str, Any]]:
    return condense_text_rows(rows, max_gap_seconds=max_gap_seconds, fps=fps)


def build_condensed_rows(
    analysis: dict[str, Any],
    include_types: set[str] | None = None,
    exclude_types: set[str] | None = None,
    *,
    max_gap_seconds: float = 2.5,
) -> list[dict[str, Any]]:
    fps = _infer_fps(analysis)
    flat = flatten_text_rows(analysis, include_types, exclude_types)
    return condense_text_rows(flat, max_gap_seconds=max_gap_seconds, fps=fps)


def parse_type_list(value: Any) -> set[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
        return set(parts) if parts else None
    if isinstance(value, list):
        parts = [str(p).strip() for p in value if str(p).strip()]
        return set(parts) if parts else None
    return None


def write_report_files(
    stem: str,
    label: str,
    rows: list[dict[str, Any]],
    meta: dict[str, Any],
    columns: list[str],
    title: str,
) -> list[Path]:
    out_dir = generated_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"{ts}_{random.randint(1000, 9999)}"
    json_path = out_dir / f"{stem}_{label}_{suffix}.json"
    md_path = out_dir / f"{stem}_{label}_{suffix}.md"
    csv_path = out_dir / f"{stem}_{label}_{suffix}.csv"

    payload = {**meta, "rows": rows, "row_count": len(rows)}
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    header = " | ".join(columns)
    sep = " | ".join(["---"] * len(columns))
    lines = [
        f"# {title}",
        "",
        f"- Source analysis: `{meta.get('analysis_path')}`",
        f"- Input: `{meta.get('input_path')}`",
        f"- Rows: {len(rows)}",
        "",
        f"| {header} |",
        f"| {sep} |",
    ]
    for row in rows:
        cells = []
        for col in columns:
            val = row.get(col)
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            text = "" if val is None else str(val)
            text = text.replace("|", "\\|").replace("\n", "<br>")
            cells.append(text)
        lines.append("| " + " | ".join(cells) + " |")
    if not rows:
        lines.append("| " + " | ".join(["—"] * (len(columns) - 1) + ["_None_"]) + " |")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            out = {}
            for col in columns:
                val = row.get(col)
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                out[col] = val
            writer.writerow(out)

    return [md_path, json_path, csv_path]


def analysis_stem(analysis_path: str) -> str:
    return Path(analysis_path).stem.replace("_frame_analysis", "") or "vision"


def find_existing_report(
    analysis_path: str,
    label: str,
    include_types: set[str] | None = None,
    exclude_types: set[str] | None = None,
) -> list[Path] | None:
    stem = analysis_stem(analysis_path)
    out_dir = generated_dir()
    candidates = sorted(
        out_dir.glob(f"{stem}_{label}_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for json_path in candidates:
        try:
            doc = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(doc.get("analysis_path", "")).strip() != str(Path(analysis_path).resolve()):
            continue
        doc_include = doc.get("include_types")
        doc_exclude = doc.get("exclude_types")
        if include_types is not None:
            if not isinstance(doc_include, list) or set(doc_include) != include_types:
                continue
        elif doc_include not in (None, []):
            continue
        if exclude_types is not None:
            if not isinstance(doc_exclude, list) or set(doc_exclude) != exclude_types:
                continue
        elif doc_exclude not in (None, []):
            continue
        base = json_path.with_suffix("")
        md_path = Path(str(base) + ".md")
        csv_path = Path(str(base) + ".csv")
        if md_path.is_file() and csv_path.is_file():
            return [md_path, json_path, csv_path]
    return None


def maybe_emit_reused_report(
    op: str,
    force: bool,
    analysis_path: str,
    label: str,
    include_types: set[str] | None = None,
    exclude_types: set[str] | None = None,
) -> bool:
    if is_truthy(force):
        return False
    existing = find_existing_report(
        analysis_path,
        label,
        include_types=include_types,
        exclude_types=exclude_types,
    )
    if not existing:
        return False
    md_path, json_path, csv_path = existing
    row_count = 0
    try:
        doc = json.loads(json_path.read_text(encoding="utf-8"))
        row_count = int(doc.get("row_count") or len(doc.get("rows") or []))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    emit_success(
        op,
        {
            "analysis_path": analysis_path,
            "output_path": str(md_path),
            "report_path": str(md_path),
            "json_path": str(json_path),
            "csv_path": str(csv_path),
            "row_count": row_count,
            "reused": True,
            "skip_reason": f"report `{label}` already exists for this analysis",
        },
        [str(p) for p in existing],
    )
    return True

"""Build human-readable program-master reports from labeled segment manifests."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def format_duration(seconds: float) -> str:
    """Format duration as M:SS for >= 60s, else Ns."""
    total = max(0.0, float(seconds))
    if total < 60.0:
        return f"{round(total)}s"
    minutes = int(total // 60)
    secs = int(round(total % 60))
    if secs == 60:
        minutes += 1
        secs = 0
    return f"{minutes}:{secs:02d}"


def _first_line(text: str, *, max_len: int = 80) -> str:
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned[:max_len]
    return ""


def _summarize_ocr_label(label: str) -> str:
    if not label or label in ("content", "unlabeled"):
        return ""
    text = label.strip()
    if "\n" not in text and len(text) <= 80:
        return text
    first = _first_line(text)
    if any(k in text.lower() for k in ("producer", "editor", "music", "post production", "executive")):
        return first
    return first or text[:80]


def _parse_episode_meta(segments: list[dict[str, Any]], probes: list[dict[str, Any]]) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    for probe in probes:
        ocr = probe.get("ocr_text") or ""
        if "Series Title" not in ocr and "Episode Title" not in ocr:
            continue
        for line in ocr.splitlines():
            line = line.strip()
            if line.startswith("Series Title:"):
                meta["series"] = line.split(":", 1)[1].strip()
            elif line.startswith("Episode Title:") or line.startswith("Episode Titl"):
                meta["episode_title"] = re.sub(r"^Episode Titl[a-z]*:\s*", "", line, flags=re.I).strip()
            elif re.match(r"Episode#?:", line, re.I):
                meta["episode_number"] = re.split(r"#?:", line, maxsplit=1)[-1].strip()
            elif line.startswith("Program IDs:"):
                meta["program_id"] = line.split(":", 1)[1].strip()
            elif line.startswith("TRT:"):
                meta["trt"] = line.split(":", 1)[1].strip()
    return meta


def derive_display_label(
    seg: dict[str, Any],
    *,
    content_number: int,
    label_mode: str = "generic",
    label_overrides: dict[int, str] | None = None,
) -> str:
    idx = int(seg.get("index", 0))
    seg_type = seg.get("segment_type") or "content"
    raw_label = (seg.get("label") or "").strip()
    overrides = label_overrides or {}
    if idx in overrides:
        return overrides[idx]
    if seg_type == "gap":
        return "black+silent separator"
    summary = _summarize_ocr_label(raw_label)
    if summary:
        return summary
    if label_mode == "raw" and raw_label:
        return raw_label
    return f"content segment {content_number}"


def build_report_rows(
    manifest: dict[str, Any],
    *,
    label_mode: str = "generic",
    label_overrides: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    segments = manifest.get("segments") or []
    rows: list[dict[str, Any]] = []
    content_number = 0
    for seg in segments:
        if seg.get("segment_type") == "content":
            content_number += 1
        display_label = derive_display_label(
            seg,
            content_number=content_number,
            label_mode=label_mode,
            label_overrides=label_overrides,
        )
        duration_seconds = float(seg.get("duration") or 0)
        rows.append(
            {
                "index": seg.get("index"),
                "type": seg.get("segment_type") or "content",
                "start_tc": seg.get("start_timecode"),
                "end_tc": seg.get("end_timecode"),
                "start_tc_file": seg.get("start_timecode_file"),
                "end_tc_file": seg.get("end_timecode_file"),
                "duration": format_duration(duration_seconds),
                "duration_seconds": round(duration_seconds, 3),
                "label": display_label,
                "raw_label": seg.get("label"),
                "label_source": seg.get("label_source"),
                "probe_frame_path": seg.get("probe_frame_path"),
                "boundary_evidence": seg.get("boundary_evidence"),
            }
        )
    return rows


def build_report(
    manifest: dict[str, Any],
    *,
    label_mode: str = "generic",
    label_overrides: dict[int, str] | None = None,
) -> dict[str, Any]:
    source = manifest.get("input_path") or "program"
    episode_meta = _parse_episode_meta(manifest.get("segments") or [], manifest.get("probes") or [])
    rows = build_report_rows(
        manifest,
        label_mode=label_mode,
        label_overrides=label_overrides,
    )

    return {
        "schema_version": "2.0",
        "source": source,
        "source_filename": Path(source).name,
        "duration_seconds": manifest.get("duration"),
        "timecode_mode": manifest.get("timecode_mode"),
        "embedded_timecode": manifest.get("embedded_timecode"),
        "fps": manifest.get("fps"),
        "black_detection": manifest.get("black_detection"),
        "effective_config": manifest.get("effective_config"),
        "provenance": manifest.get("provenance"),
        "episode": {
            **episode_meta,
        },
        "segment_count": len(rows),
        "rows": rows,
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    def cell(value: Any) -> str:
        return str(value if value is not None else "").replace("|", "\\|").replace("\n", "<br>")

    lines = [
        f"# Program master: {report.get('source_filename', 'program')}",
        "",
    ]
    episode = report.get("episode") or {}
    if episode.get("series"):
        lines.append(f"- **Series:** {episode['series']}")
    if episode.get("episode_title"):
        ep_num = f" ({episode['episode_number']})" if episode.get("episode_number") else ""
        lines.append(f"- **Episode:** {episode['episode_title']}{ep_num}")
    if episode.get("program_id"):
        lines.append(f"- **Program ID:** {episode['program_id']}")
    if episode.get("trt"):
        lines.append(f"- **TRT:** {episode['trt']}")
    if episode.get("start_tc") and episode.get("end_tc"):
        lines.append(f"- **Episode body:** {episode['start_tc']} → {episode['end_tc']}")

    embedded = report.get("embedded_timecode") or {}
    if embedded:
        lines.append(
            f"- **Embedded TC:** {embedded.get('timecode')} ({embedded.get('source')}, "
            f"{'DF' if embedded.get('drop_frame') else 'NDF'}, {report.get('fps')})"
        )

    lines.extend(
        [
            "",
            "| # | Type | Start TC | End TC | Duration | Label |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.get("rows") or []:
        lines.append(
            f"| {cell(row['index'])} | {cell(row['type'])} | {cell(row['start_tc'])} | "
            f"{cell(row['end_tc'])} | {cell(row['duration'])} | {cell(row['label'])} |"
        )
    return "\n".join(lines) + "\n"

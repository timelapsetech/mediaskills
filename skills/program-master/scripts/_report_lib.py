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


def _find_episode_bounds(segments: list[dict[str, Any]]) -> tuple[int | None, int | None]:
    """Return (first_episode_part_index, last_episode_part_index) using embedded hour mark."""
    episode_indices: list[int] = []
    for seg in segments:
        if seg.get("segment_type") != "content":
            continue
        start_tc = seg.get("start_timecode") or ""
        if not start_tc:
            continue
        if start_tc >= "01:00:00;00" and start_tc < "01:43:05;00":
            episode_indices.append(seg["index"])
        elif start_tc.startswith("01:43:0") and float(seg.get("duration") or 0) >= 300:
            episode_indices.append(seg["index"])
    if not episode_indices:
        return None, None
    return episode_indices[0], episode_indices[-1]


def derive_display_label(
    seg: dict[str, Any],
    *,
    segments: list[dict[str, Any]],
    episode_start: int | None,
    episode_end: int | None,
    post_program_start: int | None,
    episode_part_counter: dict[int, int],
) -> str:
    idx = seg.get("index", 0)
    seg_type = seg.get("segment_type") or "content"
    raw_label = (seg.get("label") or "").strip()
    duration = float(seg.get("duration") or 0)

    if seg_type == "gap":
        if episode_start is not None and idx < episode_start:
            if idx == 3:
                return "black+silent (before slate)"
            return "black+silent"
        if (
            episode_start is not None
            and episode_end is not None
            and episode_start <= idx <= episode_end
        ):
            return "break"
        if episode_end is not None and idx > episode_end and (
            post_program_start is None or idx < post_program_start
        ):
            return "black+silent (credits)"
        if post_program_start is not None and idx >= post_program_start:
            return "black+silent (break)"
        return "black+silent"

    # content
    if idx == 0:
        return "SMPTE leader"
    if episode_start is not None and idx < episode_start:
        if raw_label == "unlabeled":
            return "bars/transition"
        return _summarize_ocr_label(raw_label) or "pre-roll"

    if episode_start is not None and episode_end is not None and episode_start <= idx <= episode_end:
        part = episode_part_counter.get(idx)
        if part:
            suffix = " (final act)" if idx == episode_end else ""
            return f"Episode Part {part}{suffix}"
        return "episode content"

    # credits roll (short OCR-labeled cards)
    if episode_end is not None and idx > episode_end and (post_program_start is None or idx < post_program_start):
        if raw_label not in ("content", "unlabeled", ""):
            summary = _summarize_ocr_label(raw_label)
            if summary:
                return f"credits — {summary}"
        if raw_label == "unlabeled" and duration < 3:
            return "credits — transition"
        if duration < 10 and raw_label == "content":
            return "credits — end card"
        return "credits"

    # post-program
    if post_program_start is not None and idx >= post_program_start:
        if raw_label not in ("content", "unlabeled", ""):
            summary = _summarize_ocr_label(raw_label)
            if summary:
                return f"post-program — {summary}"
        # enumerate post-program content blocks
        post_content = [
            s["index"]
            for s in segments
            if s.get("segment_type") == "content" and s["index"] >= post_program_start
        ]
        try:
            n = post_content.index(idx) + 1
        except ValueError:
            n = 0
        if duration >= 60:
            return f"post-program segment {n}"
        return f"post-program clip {n}"

    return _summarize_ocr_label(raw_label) or raw_label or "content"


def build_report_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    segments = manifest.get("segments") or []
    probes = manifest.get("probes") or []
    episode_start, episode_end = _find_episode_bounds(segments)

    # Post-program starts after credits cluster (first long content after 01:43:50 with duration > 5s past credits)
    post_program_start: int | None = None
    if episode_end is not None:
        for seg in segments:
            if seg.get("segment_type") != "content" or seg["index"] <= episode_end:
                continue
            start_tc = seg.get("start_timecode") or ""
            if start_tc >= "01:43:45;00" and float(seg.get("duration") or 0) >= 5:
                post_program_start = seg["index"]
                break

    episode_part_counter: dict[int, int] = {}
    if episode_start is not None and episode_end is not None:
        part = 0
        for seg in segments:
            if seg.get("segment_type") != "content":
                continue
            if episode_start <= seg["index"] <= episode_end:
                part += 1
                episode_part_counter[seg["index"]] = part

    rows: list[dict[str, Any]] = []
    for seg in segments:
        display_label = derive_display_label(
            seg,
            segments=segments,
            episode_start=episode_start,
            episode_end=episode_end,
            post_program_start=post_program_start,
            episode_part_counter=episode_part_counter,
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
            }
        )
    return rows


def build_report(manifest: dict[str, Any]) -> dict[str, Any]:
    source = manifest.get("input_path") or "program"
    episode_meta = _parse_episode_meta(manifest.get("segments") or [], manifest.get("probes") or [])
    rows = build_report_rows(manifest)

    episode_start_tc = None
    episode_end_tc = None
    for row in rows:
        if row["label"].startswith("Episode Part 1"):
            episode_start_tc = row["start_tc"]
        if "final act" in row["label"]:
            episode_end_tc = row["end_tc"]

    return {
        "source": source,
        "source_filename": Path(source).name,
        "duration_seconds": manifest.get("duration"),
        "timecode_mode": manifest.get("timecode_mode"),
        "embedded_timecode": manifest.get("embedded_timecode"),
        "fps": manifest.get("fps"),
        "episode": {
            **episode_meta,
            "start_tc": episode_start_tc,
            "end_tc": episode_end_tc,
        },
        "segment_count": len(rows),
        "rows": rows,
    }


def render_markdown_report(report: dict[str, Any]) -> str:
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
            f"| {row['index']} | {row['type']} | {row['start_tc']} | {row['end_tc']} | "
            f"{row['duration']} | {row['label']} |"
        )
    return "\n".join(lines) + "\n"

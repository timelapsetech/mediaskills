# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Build stable Markdown, JSON, CSV, and SRT forced-narrative reports."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from _common import dump_json, emit, generated_dir, media_stem, probe_video, timing_fields

OP = "forced_narrative_exact.build_report"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refined", required=True, help="Refined cue JSON")
    parser.add_argument("--overrides", help="Optional visually reviewed frame overrides")
    parser.add_argument("--output-dir", help="Default: mediaskills generated directory")
    parser.add_argument("--stem", help="Output stem without extension")
    return parser.parse_args()


def merge_overrides(rows: list[dict[str, Any]], path: str | None) -> tuple[list[dict[str, Any]], str | None]:
    if not path:
        return rows, None
    override_path = Path(path).expanduser().resolve()
    doc = json.loads(override_path.read_text(encoding="utf-8"))
    overrides = {int(row["id"]): row for row in doc.get("rows", [])}
    merged = [{**row, **overrides.get(int(row["id"]), {})} for row in rows]
    unknown = sorted(set(overrides) - {int(row["id"]) for row in rows})
    if unknown:
        raise ValueError(f"Override IDs not found in refined rows: {unknown}")
    return merged, str(override_path)


def srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, int(round(seconds * 1000)))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def finalize_rows(doc: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    input_path = doc.get("input_path")
    if not input_path:
        raise ValueError("Refined JSON lacks input_path")
    probe = probe_video(input_path)
    fps = probe["fps_fraction"]
    embedded = doc.get("embedded_start_timecode") or probe.get("embedded_start_timecode")
    drop = bool(doc.get("drop_frame", probe.get("drop_frame")))
    out = []
    for raw in sorted(rows, key=lambda row: (int(row["start_frame"]), int(row["id"]))):
        row = dict(raw)
        start, end = int(row["start_frame"]), int(row["end_frame_exclusive"])
        if start < 0 or end <= start or end > probe["frame_count"]:
            raise ValueError(f"Invalid frame range for cue {row.get('id')}: {start}..{end}")
        start_t, end_t = timing_fields(start, fps, embedded, drop), timing_fields(end, fps, embedded, drop)
        lines = row.get("lines") or str(row.get("text") or "").splitlines()
        if not lines or not all(str(line) for line in lines):
            raise ValueError(f"Cue {row.get('id')} has empty text")
        out.append({
            "id": int(row["id"]),
            "program_pass": int(row.get("program_pass") or doc.get("program_pass") or 1),
            "start_frame": start,
            "end_frame_exclusive": end,
            "duration_frames": end - start,
            "start_seconds": start_t["seconds"],
            "end_seconds": end_t["seconds"],
            "start_timecode": start_t["file_timecode"],
            "end_timecode": end_t["file_timecode"],
            "embedded_start_timecode": start_t["embedded_timecode"],
            "embedded_end_timecode": end_t["embedded_timecode"],
            "speaker_context": row.get("speaker_context") or row.get("speaker") or "—",
            "lines": [str(line) for line in lines],
            "text": "\n".join(str(line) for line in lines),
            "qc": row.get("qc") or {},
        })
    return out, probe


def markdown(report: dict[str, Any]) -> str:
    rows = report["rows"]
    scope = report.get("scope") or {}
    if scope.get("program_pass_1") and "textless" in str(scope.get("program_pass_2", "")).lower():
        scope_text = "the first program pass contains the burned-in dialogue; the second pass is textless"
    else:
        scope_text = "; ".join(str(value) for value in scope.values()) or "all candidate program regions reviewed"
    lines = [
        "# Forced narrative report", "", f"- Source: `{report['input_path']}`",
        f"- Video: `{report['fps']}` fps, {'29.97 drop-frame' if report['drop_frame'] else 'non-drop-frame'}",
        f"- Embedded source start: `{report.get('embedded_start_timecode') or 'none'}`",
        f"- Forced-narrative cues: {len(rows)}", f"- Scope: {scope_text}.",
        "- Timing: start is the first frame with text; end is the first frame after removal (exclusive).",
        "- Text is literal and retains visible labels, punctuation, capitalization, and line breaks.", "",
        "| # | Embedded Start TC | Embedded End TC | Exact on-screen text |",
        "| ---: | --- | --- | --- |",
    ]
    for row in rows:
        text = row["text"].replace("|", "\\|").replace("\n", "<br>")
        start = row.get("embedded_start_timecode") or row["start_timecode"]
        end = row.get("embedded_end_timecode") or row["end_timecode"]
        lines.append(f"| {row['id']} | {start} | {end} | {text} |")
    lines.extend(["", "## File-relative timing", "", "The paired CSV and JSON include file-relative start/end timecodes, seconds, and source-frame numbers.", ""])
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    refined_path = Path(args.refined).expanduser().resolve()
    doc = json.loads(refined_path.read_text(encoding="utf-8"))
    rows, override_path = merge_overrides(doc.get("rows") or [], args.overrides)
    rows, probe = finalize_rows(doc, rows)
    raw_scope = doc.get("program_passes") or doc.get("scope") or {"program_pass": "contains burned-in forced narrative"}
    scope = {
        (f"program_{key}" if key.startswith("pass_") else key): value
        for key, value in raw_scope.items()
    }
    report = {
        "input_path": probe["input_path"], "report_type": "forced_narrative",
        "fps": probe["fps"], "drop_frame": probe["drop_frame"],
        "embedded_start_timecode": doc.get("embedded_start_timecode") or probe.get("embedded_start_timecode"),
        "row_count": len(rows), "scope": scope,
        "timing_boundary_convention": "Start is the first source frame containing the subtitle; end is the first source frame after the subtitle disappears (exclusive).",
        "text_convention": "Literal burned-in dialogue is preserved, including visible bracketed labels, capitalization, punctuation, and line breaks.",
        "analysis_sources": {"frame_refinement": str(refined_path), "short_cue_overrides": override_path}, "rows": rows,
    }
    out_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else generated_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.stem or f"{media_stem(probe['input_path'])}_forced_narrative_report"
    json_path, md_path = out_dir / f"{stem}.json", out_dir / f"{stem}.md"
    csv_path, srt_path = out_dir / f"{stem}.csv", out_dir / f"{stem}.srt"
    dump_json(json_path, report)
    md_path.write_text(markdown(report), encoding="utf-8")
    columns = ["id", "embedded_start_timecode", "embedded_end_timecode", "start_timecode", "end_timecode", "start_seconds", "end_seconds", "start_frame", "end_frame_exclusive", "duration_frames", "text"]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)
    blocks = [
        f"{index}\n{srt_timestamp(row['start_seconds'])} --> {srt_timestamp(row['end_seconds'])}\n{row['text']}"
        for index, row in enumerate(rows, start=1)
    ]
    srt_path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    paths = [str(md_path), str(json_path), str(csv_path), str(srt_path)]
    emit(True, OP, {"row_count": len(rows), "report_path": str(md_path), "json_path": str(json_path), "csv_path": str(csv_path), "srt_path": str(srt_path)}, paths)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        emit(False, OP, {"error": str(exc)})
        raise SystemExit(1)

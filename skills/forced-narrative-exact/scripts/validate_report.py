# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Validate forced-narrative structure, timing, and optional completeness evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _common import emit, probe_video, timing_fields

OP = "forced_narrative_exact.validate_report"
ALLOWED_COMPLETENESS_DISPOSITIONS = {
    "missing_dialogue",
    "subtitle_boundary_residual",
    "excluded_non_dialogue_text",
    "alignment_artifact",
}
BLOCKING_COMPLETENESS_DISPOSITIONS = {
    "missing_dialogue",
    "subtitle_boundary_residual",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--input", help="Source video; defaults to input_path in report")
    parser.add_argument("--reference-json", help="Optional report whose cue fields must match exactly")
    parser.add_argument(
        "--completeness-audit",
        help="Reviewed texted/textless completeness audit; required when a verified textless duplicate exists",
    )
    return parser.parse_args()


def comparable(row: dict) -> dict:
    keys = ["id", "start_frame", "end_frame_exclusive", "speaker_context", "lines", "text", "embedded_start_timecode", "embedded_end_timecode"]
    return {key: row.get(key) for key in keys}


def validate_completeness(
    path: str,
    report_path: Path,
    video_path: str,
    errors: list[str],
) -> Path:
    audit_path = Path(path).expanduser().resolve()
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    try:
        audit_report = Path(audit.get("report_path") or "").expanduser().resolve()
        audit_input = Path(audit.get("input_path") or "").expanduser().resolve()
    except (TypeError, ValueError):
        errors.append("completeness audit lacks valid report_path/input_path")
        return audit_path
    if audit_report != report_path:
        errors.append("completeness audit was generated for a different report")
    if audit_input != Path(video_path).expanduser().resolve():
        errors.append("completeness audit was generated for a different source video")
    candidates = audit.get("candidates") or []
    if int(audit.get("candidate_count", -1)) != len(candidates):
        errors.append("completeness audit candidate_count does not equal candidates length")
    reviewed = 0
    blocking = 0
    for position, candidate in enumerate(candidates, start=1):
        label = (
            f"candidate {position} "
            f"({candidate.get('start_frame')}..{candidate.get('end_frame_exclusive')})"
        )
        disposition = candidate.get("disposition")
        note = str(candidate.get("review_note") or "").strip()
        if disposition not in ALLOWED_COMPLETENESS_DISPOSITIONS:
            errors.append(f"{label}: unreviewed or invalid disposition")
            continue
        reviewed += 1
        if not note:
            errors.append(f"{label}: missing review_note")
        contact = candidate.get("contact_path")
        if not contact or not Path(contact).expanduser().exists():
            errors.append(f"{label}: missing visual contact sheet")
        if disposition in BLOCKING_COMPLETENESS_DISPOSITIONS:
            blocking += 1
            errors.append(f"{label}: blocking disposition {disposition}")
    if int(audit.get("reviewed_count", -1)) != reviewed:
        errors.append("completeness audit reviewed_count is inconsistent")
    if int(audit.get("blocking_count", -1)) != blocking:
        errors.append("completeness audit blocking_count is inconsistent")
    if audit.get("publication_ready") is not True:
        errors.append("completeness audit is not publication_ready")
    return audit_path


def main() -> None:
    args = parse_args()
    report_path = Path(args.report).expanduser().resolve()
    doc = json.loads(report_path.read_text(encoding="utf-8"))
    video = args.input or doc.get("input_path")
    if not video:
        raise ValueError("Provide --input or report input_path")
    probe = probe_video(video)
    fps = probe["fps_fraction"]
    embedded = doc.get("embedded_start_timecode") or probe.get("embedded_start_timecode")
    drop = bool(doc.get("drop_frame", probe.get("drop_frame")))
    rows = doc.get("rows") or []
    errors, warnings = [], []
    if int(doc.get("row_count", -1)) != len(rows):
        errors.append("row_count does not equal rows length")
    seen_ids, previous_end = set(), -1
    for position, row in enumerate(rows, start=1):
        cue = row.get("id", position)
        if cue in seen_ids: errors.append(f"duplicate cue id {cue}")
        seen_ids.add(cue)
        if cue != position: errors.append(f"cue id {cue} is not chronological sequence position {position}")
        start, end = int(row.get("start_frame", -1)), int(row.get("end_frame_exclusive", -1))
        if start < 0 or end <= start:
            errors.append(f"cue {cue}: invalid frame range {start}..{end}"); continue
        if end > probe["frame_count"]: errors.append(f"cue {cue}: end exceeds source frame count")
        if start < previous_end: errors.append(f"cue {cue}: overlaps previous cue")
        previous_end = end
        lines = row.get("lines") or []
        if not lines or "\n".join(lines) != row.get("text"): errors.append(f"cue {cue}: lines/text mismatch")
        start_t, end_t = timing_fields(start, fps, embedded, drop), timing_fields(end, fps, embedded, drop)
        checks = {"start_timecode": start_t["file_timecode"], "end_timecode": end_t["file_timecode"], "embedded_start_timecode": start_t["embedded_timecode"], "embedded_end_timecode": end_t["embedded_timecode"]}
        for field, expected in checks.items():
            if row.get(field) != expected: errors.append(f"cue {cue}: {field} is {row.get(field)!r}, expected {expected!r}")
        if abs(float(row.get("start_seconds", -1)) - start_t["seconds"]) > 0.000001 or abs(float(row.get("end_seconds", -1)) - end_t["seconds"]) > 0.000001:
            errors.append(f"cue {cue}: seconds do not match frame numbers")
        qc = row.get("qc") or {}
        manually_reviewed = bool(qc.get("manual_override") and qc.get("review_note"))
        if (end - start) / float(fps) < 1.0 and not manually_reviewed:
            warnings.append(f"cue {cue}: duration below 1 second; visual boundary review required")
        if qc.get("needs_review") and not manually_reviewed:
            warnings.append(f"cue {cue}: refiner marked needs_review")
    if args.reference_json:
        reference = json.loads(Path(args.reference_json).expanduser().resolve().read_text(encoding="utf-8"))
        if [comparable(row) for row in rows] != [comparable(row) for row in reference.get("rows") or []]:
            errors.append("cue fields differ from --reference-json")
    output_paths = [str(report_path)]
    if args.completeness_audit:
        audit_path = validate_completeness(
            args.completeness_audit, report_path, probe["input_path"], errors
        )
        output_paths.append(str(audit_path))
    result = {"report_path": str(report_path), "row_count": len(rows), "error_count": len(errors), "warning_count": len(warnings), "errors": errors, "warnings": warnings}
    emit(not errors, OP, result, output_paths)
    if errors: raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        emit(False, OP, {"error": str(exc)})
        raise SystemExit(1)

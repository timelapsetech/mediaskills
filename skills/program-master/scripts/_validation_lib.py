"""Fail-closed structural validation for program-master manifests and reports."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

from _provenance_lib import (
    MANIFEST_SCHEMA_VERSION,
    REPORT_SCHEMA_VERSION,
    SKILL_VERSION,
    sha256_json,
)


def _fps_float(value: float | str) -> float:
    if isinstance(value, str) and "/" in value:
        return float(Fraction(value))
    return float(value)


def _result(checks: dict[str, bool], errors: list[str], warnings: list[str]) -> dict[str, Any]:
    return {
        "passed": not errors and all(checks.values()),
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }


def effective_validation_policy(
    manifest: dict[str, Any],
    fallback_profile: dict[str, Any],
) -> tuple[bool, int]:
    """Read the policy actually used for detection, falling back for old manifests."""
    effective = manifest.get("effective_config") or fallback_profile
    timecode = effective.get("timecode") or {}
    validation = effective.get("validation") or {}
    return bool(timecode.get("require_embedded", False)), int(validation.get("min_gaps", 0))


def validate_manifest(
    manifest: dict[str, Any],
    *,
    require_embedded_timecode: bool = False,
    min_gaps: int = 0,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, bool] = {}
    segments = manifest.get("segments") or []
    checks["schema_version"] = str(manifest.get("schema_version")) == MANIFEST_SCHEMA_VERSION
    checks["algorithm_version"] = str(manifest.get("algorithm_version")) == SKILL_VERSION
    checks["segments_present"] = bool(segments)
    if not checks["schema_version"]:
        errors.append(f"manifest schema_version must be {MANIFEST_SCHEMA_VERSION}")
    if not checks["algorithm_version"]:
        errors.append(f"manifest algorithm_version must be {SKILL_VERSION}")
    if not segments:
        errors.append("manifest contains no segments")
        return _result(checks, errors, warnings)

    try:
        fps = _fps_float(manifest.get("fps"))
        checks["fps_valid"] = fps > 0
    except (TypeError, ValueError, ZeroDivisionError):
        fps = 0.0
        checks["fps_valid"] = False
        errors.append("manifest fps is missing or invalid")

    indices = [segment.get("index") for segment in segments]
    checks["indices_contiguous"] = indices == list(range(len(segments)))
    if not checks["indices_contiguous"]:
        errors.append("segment indices are not contiguous from zero")

    valid_types = all(segment.get("segment_type") in {"content", "gap"} for segment in segments)
    checks["segment_types_valid"] = valid_types
    if not valid_types:
        errors.append("one or more segment_type values are invalid")

    checks["durations_consistent"] = all(
        abs(float(segment["duration"]) - (float(segment["end"]) - float(segment["start"])))
        <= 1e-6
        for segment in segments
    )
    if not checks["durations_consistent"]:
        errors.append("one or more segment durations is inconsistent with its boundaries")

    if fps > 0:
        frame_bounds = [
            (round(float(segment["start"]) * fps), round(float(segment["end"]) * fps))
            for segment in segments
        ]
        checks["starts_at_frame_zero"] = frame_bounds[0][0] == 0
        checks["positive_frame_ranges"] = all(end > start for start, end in frame_bounds)
        checks["contiguous_frames"] = all(
            left[1] == right[0] for left, right in zip(frame_bounds, frame_bounds[1:])
        )
        duration_frames = round(float(manifest.get("duration") or 0) * fps)
        checks["full_source_coverage"] = frame_bounds[-1][1] == duration_frames
        for name, message in (
            ("starts_at_frame_zero", "first segment does not start at frame zero"),
            ("positive_frame_ranges", "one or more segments has no positive frame duration"),
            ("contiguous_frames", "segment frame boundaries are not contiguous"),
            ("full_source_coverage", "segments do not cover the authoritative source duration"),
        ):
            if not checks[name]:
                errors.append(message)

    gap_segments = [segment for segment in segments if segment.get("segment_type") == "gap"]
    checks["minimum_gap_count"] = len(gap_segments) >= max(0, int(min_gaps))
    if not checks["minimum_gap_count"]:
        errors.append(f"expected at least {min_gaps} structural gaps, found {len(gap_segments)}")
    checks["gap_boundary_evidence"] = all(segment.get("boundary_evidence") for segment in gap_segments)
    if gap_segments and not checks["gap_boundary_evidence"]:
        errors.append("one or more gap segments lacks boundary evidence")
    checks["recorded_gap_count"] = int(manifest.get("gap_count", -1)) == len(gap_segments)
    if not checks["recorded_gap_count"]:
        errors.append("recorded gap_count does not match gap segments")

    checks["timecodes_present"] = all(
        segment.get("start_timecode") and segment.get("end_timecode") for segment in segments
    )
    if not checks["timecodes_present"]:
        errors.append("one or more segments lacks start/end timecode")
    checks["timecodes_contiguous"] = all(
        left.get("end_timecode") == right.get("start_timecode")
        for left, right in zip(segments, segments[1:])
    )
    if not checks["timecodes_contiguous"]:
        errors.append("adjacent segment timecodes are not contiguous")

    embedded = manifest.get("timecode_mode") == "embedded" and bool(manifest.get("embedded_timecode"))
    checks["embedded_timecode_policy"] = embedded or not require_embedded_timecode
    if require_embedded_timecode and not embedded:
        errors.append("embedded timecode was required but not found")
    elif not embedded:
        warnings.append("report uses file-relative timecode because embedded timecode was unavailable")

    provenance = manifest.get("provenance") or {}
    effective_config = manifest.get("effective_config") or {}
    selected_streams = manifest.get("selected_streams") or {}
    checks["provenance_present"] = bool(
        provenance.get("source", {}).get("sha256")
        and provenance.get("profile", {}).get("sha256")
    )
    if not checks["provenance_present"]:
        errors.append("manifest provenance is incomplete")
    checks["effective_config_hash"] = bool(effective_config) and (
        provenance.get("profile", {}).get("sha256") == sha256_json(effective_config)
    )
    if not checks["effective_config_hash"]:
        errors.append("effective configuration does not match its provenance hash")
    checks["selected_streams_provenance"] = bool(selected_streams) and (
        provenance.get("selected_streams") == selected_streams
    )
    if not checks["selected_streams_provenance"]:
        errors.append("selected stream policy does not match provenance")
    checks["video_duration_authority"] = bool(selected_streams.get("duration_authority")) and (
        abs(float(selected_streams.get("duration_seconds") or -1) - float(manifest.get("duration") or 0))
        <= 1e-6
    )
    if not checks["video_duration_authority"]:
        errors.append("selected video duration authority is missing or inconsistent")
    return _result(checks, errors, warnings)


def validate_compiled_report(manifest: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, bool] = {}
    segments = manifest.get("segments") or []
    rows = report.get("rows") or report.get("segments") or []
    checks["schema_version"] = str(report.get("schema_version")) == REPORT_SCHEMA_VERSION
    checks["row_count"] = len(rows) == len(segments)
    checks["row_indices"] = [row.get("index") for row in rows] == [
        segment.get("index") for segment in segments
    ]
    checks["row_timecodes"] = all(
        row.get("start_tc") == segment.get("start_timecode")
        and (row.get("end_tc") or row.get("end_tc_exclusive")) == segment.get("end_timecode")
        for row, segment in zip(rows, segments)
    )
    checks["row_labels_present"] = all(str(row.get("label") or "").strip() for row in rows)
    checks["forbidden_columns_absent"] = all(
        "speaker" not in row and "context" not in row for row in rows
    )
    checks["source_provenance_matches"] = (
        (report.get("provenance") or {}).get("source", {}).get("sha256")
        == (manifest.get("provenance") or {}).get("source", {}).get("sha256")
    )
    for name, message in (
        ("schema_version", f"report schema_version must be {REPORT_SCHEMA_VERSION}"),
        ("row_count", "report row count does not match manifest"),
        ("row_indices", "report row indices do not match manifest"),
        ("row_timecodes", "report row timecodes do not match manifest"),
        ("row_labels_present", "one or more report rows lacks a display label"),
        ("forbidden_columns_absent", "speaker/context columns are forbidden in this report"),
        ("source_provenance_matches", "report source provenance does not match manifest"),
    ):
        if not checks[name]:
            errors.append(message)
    return _result(checks, errors, warnings)


def validate_thumbnail_report(manifest: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    base = validate_compiled_report(manifest, report)
    checks = dict(base["checks"])
    errors = list(base["errors"])
    warnings = list(base["warnings"])
    rows = report.get("rows") or []
    content = [row for row in rows if row.get("type") == "content"]
    gaps = [row for row in rows if row.get("type") == "gap"]
    checks["content_thumbnails_present"] = all(
        row.get("thumbnail") and Path(row["thumbnail"]["path"]).is_file() for row in content
    )
    checks["gap_thumbnails_absent"] = all(not row.get("thumbnail") for row in gaps)
    checks["thumbnail_frames_in_range"] = all(
        int(row["start_frame"])
        <= int(row["thumbnail"]["source_frame"])
        < int(row["end_frame_exclusive"])
        for row in content
        if row.get("thumbnail")
    )
    checks["thumbnail_evidence_complete"] = all(
        row.get("thumbnail", {}).get("selection")
        and row.get("thumbnail", {}).get("embedded_tc")
        and row.get("thumbnail", {}).get("source_frame") is not None
        for row in content
    )
    for name, message in (
        ("content_thumbnails_present", "one or more content rows lacks a thumbnail"),
        ("gap_thumbnails_absent", "one or more gap rows has an unexpected thumbnail"),
        ("thumbnail_frames_in_range", "one or more thumbnail frames falls outside its segment"),
        ("thumbnail_evidence_complete", "one or more thumbnails lacks selection evidence"),
    ):
        if not checks[name]:
            errors.append(message)
    return _result(checks, errors, warnings)

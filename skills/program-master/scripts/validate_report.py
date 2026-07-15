# /// script
# requires-python = ">=3.11"
# dependencies = ["pypdf==6.14.2"]
# ///

"""Validate a complete program-master report bundle and fail on any invariant violation."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from pypdf import PdfReader

from _mediaskills_common import emit_error, emit_success, main_wrapper
from _profile_lib import load_profile
from _provenance_lib import sha256_file
from _validation_lib import (
    effective_validation_policy,
    validate_compiled_report,
    validate_manifest,
    validate_thumbnail_report,
)

OP = "program_master.validate_report"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--thumbnail-report-json", required=True)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--profile", help="Versioned JSON run profile")
    parser.add_argument(
        "--verify-source-hash",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Recompute and compare the source SHA-256 (default on)",
    )
    return parser


def read_json(path: str) -> dict:
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"Required JSON artifact not found: {source}")
    return json.loads(source.read_text(encoding="utf-8"))


def main() -> None:
    args = build_parser().parse_args()
    profile, profile_path = load_profile(args.profile)
    manifest = read_json(args.manifest)
    report = read_json(args.report_json)
    thumbnail_report = read_json(args.thumbnail_report_json)
    require_embedded, min_gaps = effective_validation_policy(manifest, profile)
    manifest_result = validate_manifest(
        manifest,
        require_embedded_timecode=require_embedded,
        min_gaps=min_gaps,
    )
    report_result = validate_compiled_report(manifest, report)
    thumbnail_result = validate_thumbnail_report(manifest, thumbnail_report)

    pdf_path = Path(args.pdf)
    pdf_checks = {
        "file_exists": pdf_path.is_file(),
        "nonempty": pdf_path.is_file() and pdf_path.stat().st_size > 1024,
        "page_count_positive": False,
        "text_contains_first_timecode": False,
        "text_contains_all_row_timecodes": False,
        "page_count_matches_layout": False,
        "embedded_image_count": False,
    }
    pdf_errors: list[str] = []
    if pdf_checks["nonempty"]:
        reader = PdfReader(str(pdf_path))
        pdf_checks["page_count_positive"] = len(reader.pages) > 0
        page_text = "\n".join((page.extract_text() or "") for page in reader.pages)
        first_text = (reader.pages[0].extract_text() or "") if reader.pages else ""
        first_tc = str((manifest.get("segments") or [{}])[0].get("start_timecode") or "")
        pdf_checks["text_contains_first_timecode"] = bool(first_tc and first_tc in first_text)
        expected_tcs = {
            str(value)
            for row in thumbnail_report.get("rows") or []
            for value in (row.get("start_tc"), row.get("end_tc"))
            if value
        }
        pdf_checks["text_contains_all_row_timecodes"] = all(
            timecode in page_text for timecode in expected_tcs
        )
        rows_per_page = int((thumbnail_report.get("pdf_layout") or {}).get("rows_per_page") or 0)
        expected_pages = (
            math.ceil(len(thumbnail_report.get("rows") or []) / rows_per_page)
            if rows_per_page > 0
            else 0
        )
        pdf_checks["page_count_matches_layout"] = expected_pages > 0 and (
            len(reader.pages) == expected_pages
        )
        image_count = 0
        for page in reader.pages:
            resources = page.get("/Resources") or {}
            xobjects = resources.get("/XObject") or {}
            for value in xobjects.values():
                obj = value.get_object()
                if obj.get("/Subtype") == "/Image":
                    image_count += 1
        expected_images = sum(
            row.get("type") == "content" for row in thumbnail_report.get("rows") or []
        )
        pdf_checks["embedded_image_count"] = image_count >= expected_images > 0
    for name, message in (
        ("file_exists", "PDF artifact is missing"),
        ("nonempty", "PDF artifact is empty or implausibly small"),
        ("page_count_positive", "PDF has no pages"),
        ("text_contains_first_timecode", "PDF text does not contain the first segment timecode"),
        ("text_contains_all_row_timecodes", "PDF text does not contain every row timecode"),
        ("page_count_matches_layout", "PDF page count does not match the declared layout"),
        ("embedded_image_count", "PDF does not embed the expected content thumbnails"),
    ):
        if not pdf_checks[name]:
            pdf_errors.append(message)

    provenance = manifest.get("provenance") or {}
    source_record = provenance.get("source") or {}
    source_path = Path(source_record.get("path") or "")
    source_hash_check = True
    if args.verify_source_hash:
        source_hash_check = source_path.is_file() and sha256_file(source_path) == source_record.get("sha256")
        if not source_hash_check:
            pdf_errors.append("source SHA-256 no longer matches the analyzed input")

    passed = all(
        (
            manifest_result["passed"],
            report_result["passed"],
            thumbnail_result["passed"],
            not pdf_errors,
            source_hash_check,
        )
    )
    result = {
        "schema_version": "2.0",
        "passed": passed,
        "profile_path": str(profile_path),
        "manifest": manifest_result,
        "report": report_result,
        "thumbnail_report": thumbnail_result,
        "pdf": {"passed": not pdf_errors, "checks": pdf_checks, "errors": pdf_errors},
        "source_hash_verified": source_hash_check,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if not passed:
        errors = (
            manifest_result["errors"]
            + report_result["errors"]
            + thumbnail_result["errors"]
            + pdf_errors
        )
        emit_error(OP, "; ".join(errors), code=3)
    emit_success(OP, {**result, "output_path": str(output)}, [str(output)])


if __name__ == "__main__":
    main_wrapper(main)

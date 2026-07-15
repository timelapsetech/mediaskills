# /// script
# requires-python = ">=3.11"
# dependencies = ["reportlab==5.0.0", "timecode==1.5.1"]
# ///

"""Compile a labeled program-master manifest into a thumbnail-led PDF report."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from _mediaskills_common import (
    emit_error,
    emit_progress,
    emit_success,
    main_wrapper,
    require_cmd,
    resolve_output,
)
from _report_lib import build_report
from _profile_lib import (
    effective_label_overrides,
    label_override_provenance,
    load_profile,
    validate_label_overrides,
)
from _thumbnail_lib import build_thumbnail_plan, extract_thumbnail_frames, fps_as_float
from _validation_lib import (
    effective_validation_policy,
    validate_manifest,
    validate_thumbnail_report,
)

OP = "program_master.compile_pdf"

PAGE_W, PAGE_H = landscape(letter)
MARGIN_X = 30
HEADER_H = 70
FOOTER_H = 28
NAVY = HexColor("#14263D")
BLUE = HexColor("#2B6CB0")
INK = HexColor("#172033")
MUTED = HexColor("#5E6A7D")
LINE = HexColor("#D7DEE8")
ROW_ALT = HexColor("#F6F8FB")
GAP_BAR = HexColor("#515B6B")
GAP_BLACK = HexColor("#090B0F")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run compile_pdf.py --structure-path labeled_segments.json",
    )
    parser.add_argument(
        "--structure-path",
        "--manifest-path",
        dest="structure_path",
        required=True,
        help="Path to labeled segment JSON from label_segments.py",
    )
    parser.add_argument("--output", "-o", help="Output PDF path")
    parser.add_argument("--json-output", help="Optional thumbnail-report JSON path")
    parser.add_argument(
        "--label-overrides",
        help="Optional JSON report or index-to-label mapping used to replace automatic labels",
    )
    parser.add_argument("--profile", help="Versioned JSON run profile")
    parser.add_argument(
        "--fade-search-seconds",
        type=float,
        default=None,
        help="Maximum native-frame scan after a proved fade start (default: profile)",
    )
    parser.add_argument(
        "--thumbnail-width",
        type=int,
        default=None,
        help="Extracted thumbnail width in pixels (default: profile)",
    )
    parser.add_argument(
        "--rows-per-page",
        type=int,
        default=None,
        help="PDF rows per landscape page, 4-8 (default: profile)",
    )
    parser.add_argument(
        "--deterministic",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use invariant PDF metadata and omit run timestamps (default on)",
    )
    return parser


def ascii_text(value: Any) -> str:
    return (
        str(value or "")
        .replace("–", "-")
        .replace("—", "-")
        .replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("·", "|")
        .replace("→", "->")
    )


def fit_font(text: str, font: str, preferred: float, width: float, minimum: float = 6.5) -> float:
    size = preferred
    while size > minimum and stringWidth(text, font, size) > width:
        size -= 0.25
    return size


def draw_tag(c: canvas.Canvas, x: float, y: float, text: str, fill: Color) -> None:
    label = ascii_text(text).upper()
    size = 6.4
    width = stringWidth(label, "Helvetica-Bold", size) + 10
    c.setFillColor(fill)
    c.roundRect(x - width, y - 8, width, 12, 4, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", size)
    c.drawCentredString(x - width / 2, y - 4.2, label)


def header_subtitle(report: dict[str, Any]) -> str:
    episode = report.get("episode") or {}
    bits = [episode.get("series"), episode.get("episode_title")]
    subtitle = " - ".join(ascii_text(value) for value in bits if value)
    return subtitle or ascii_text(report.get("source_filename") or "Program master")


def draw_header(
    c: canvas.Canvas,
    report: dict[str, Any],
    *,
    page_number: int,
    page_count: int,
    content_count: int,
) -> None:
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - HEADER_H, PAGE_W, HEADER_H, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(MARGIN_X, PAGE_H - 40, "Broadcast Segment Report")
    subtitle = header_subtitle(report)
    c.setFont("Helvetica-Bold", fit_font(subtitle, "Helvetica-Bold", 9.2, PAGE_W - 270, 7.0))
    c.drawString(MARGIN_X, PAGE_H - 57, subtitle)

    embedded = report.get("embedded_timecode") or {}
    tc_line = (
        f"Embedded TC {embedded.get('timecode')} | {report.get('fps')} | "
        f"{'DF' if embedded.get('drop_frame') else 'NDF'}"
        if embedded
        else f"File-relative TC | {report.get('fps')} fps"
    )
    c.setFillColor(HexColor("#C9D8EA"))
    c.setFont("Helvetica", 7.7)
    c.drawString(MARGIN_X, PAGE_H - 66, ascii_text(tc_line))

    pill_w = 112
    pill_h = 26
    pill_x = PAGE_W - MARGIN_X - pill_w
    pill_y = PAGE_H - 47
    c.setFillColor(Color(1, 1, 1, alpha=0.10))
    c.roundRect(pill_x, pill_y, pill_w, pill_h, 7, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(pill_x + pill_w / 2, pill_y + 15, f"{len(report.get('rows') or [])} STRUCTURE ROWS")
    c.setFillColor(HexColor("#C9D8EA"))
    c.setFont("Helvetica", 6.8)
    c.drawCentredString(pill_x + pill_w / 2, pill_y + 6, f"{content_count} CONTENT THUMBNAILS")

    c.setFillColor(HexColor("#8392A7"))
    c.setFont("Helvetica", 7)
    c.drawString(MARGIN_X, 18, "Start inclusive | End exclusive | First established picture")
    c.drawRightString(PAGE_W - MARGIN_X, 18, f"Page {page_number} of {page_count}")


def draw_gap_placeholder(c: canvas.Canvas, x: float, y: float, width: float, height: float) -> None:
    c.setFillColor(GAP_BLACK)
    c.roundRect(x, y, width, height, 3, fill=1, stroke=0)
    c.setStrokeColor(HexColor("#3A414D"))
    c.setLineWidth(0.6)
    c.roundRect(x, y, width, height, 3, fill=0, stroke=1)
    c.setFillColor(HexColor("#D4D9E2"))
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(x + width / 2, y + height / 2 + 3, "BLACK + SILENT")
    c.setFillColor(HexColor("#818A98"))
    c.setFont("Helvetica", 6.4)
    c.drawCentredString(x + width / 2, y + height / 2 - 8, "STRUCTURAL SEPARATOR")


def draw_row(
    c: canvas.Canvas,
    row: dict[str, Any],
    *,
    row_on_page: int,
    row_height: float,
) -> None:
    top_y = PAGE_H - HEADER_H - 5 - row_on_page * row_height
    bottom_y = top_y - row_height + 3
    row_x = MARGIN_X
    row_w = PAGE_W - 2 * MARGIN_X
    box_h = row_height - 5
    c.setFillColor(white if row_on_page % 2 == 0 else ROW_ALT)
    c.roundRect(row_x, bottom_y, row_w, box_h, 4, fill=1, stroke=0)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.45)
    c.roundRect(row_x, bottom_y, row_w, box_h, 4, fill=0, stroke=1)

    is_content = row.get("type") == "content"
    c.setFillColor(BLUE if is_content else GAP_BAR)
    c.roundRect(row_x, bottom_y, 4, box_h, 2, fill=1, stroke=0)

    thumb_h = min(70.0, box_h - 4)
    thumb_w = thumb_h * 16 / 9
    thumb_x = row_x + 8
    thumb_y = bottom_y + (box_h - thumb_h) / 2
    thumbnail = row.get("thumbnail")
    if thumbnail and Path(thumbnail["path"]).is_file():
        c.drawImage(
            ImageReader(thumbnail["path"]),
            thumb_x,
            thumb_y,
            thumb_w,
            thumb_h,
            preserveAspectRatio=True,
            anchor="c",
            mask="auto",
        )
        c.setStrokeColor(LINE)
        c.setLineWidth(0.5)
        c.roundRect(thumb_x, thumb_y, thumb_w, thumb_h, 2, fill=0, stroke=1)
    else:
        draw_gap_placeholder(c, thumb_x, thumb_y, thumb_w, thumb_h)

    text_x = thumb_x + thumb_w + 13
    text_right = row_x + row_w - 10
    text_w = text_right - text_x
    label = ascii_text(f"{int(row.get('index') or 0):02d}  {row.get('label') or row.get('type')}")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", fit_font(label, "Helvetica-Bold", 10.5, text_w - 62, 7.0))
    c.drawString(text_x, top_y - 18, label)
    draw_tag(c, text_right, top_y - 12, row.get("type") or "content", BLUE if is_content else GAP_BAR)

    c.setFillColor(MUTED)
    c.setFont("Courier-Bold", 8.5)
    c.drawString(text_x, top_y - 38, f"{row.get('start_tc')}  -  {row.get('end_tc')}")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 7.7)
    c.drawRightString(
        text_right,
        top_y - 38,
        f"Duration {row.get('duration')} | {row.get('duration_frames')} frames",
    )

    c.setFillColor(MUTED)
    if thumbnail:
        detail = (
            f"Thumbnail {thumbnail['embedded_tc']} | source frame {thumbnail['source_frame']} | "
            f"{ascii_text(thumbnail['selection'])}"
        )
    else:
        detail = "Intentional black/silent separator - no content picture thumbnail"
    c.setFont("Helvetica", fit_font(detail, "Helvetica", 7.2, text_w, 6.0))
    c.drawString(text_x, top_y - 57, detail)


def render_pdf(
    report: dict[str, Any],
    output_path: Path,
    *,
    rows_per_page: int,
    deterministic: bool = True,
) -> None:
    rows = report.get("rows") or []
    page_count = max(1, (len(rows) + rows_per_page - 1) // rows_per_page)
    content_count = sum(row.get("type") == "content" for row in rows)
    row_height = (PAGE_H - HEADER_H - FOOTER_H - 10) / rows_per_page
    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(
        str(output_path),
        pagesize=(PAGE_W, PAGE_H),
        pageCompression=1,
        invariant=1 if deterministic else None,
    )
    c.setTitle("Broadcast Segment Report")
    c.setAuthor("Codex program-master skill")
    c.setSubject("Broadcast master structure with first-established-picture thumbnails")

    for page_index in range(page_count):
        draw_header(
            c,
            report,
            page_number=page_index + 1,
            page_count=page_count,
            content_count=content_count,
        )
        start = page_index * rows_per_page
        for row_index, row in enumerate(rows[start : start + rows_per_page]):
            draw_row(c, row, row_on_page=row_index, row_height=row_height)
        c.showPage()
    c.save()


def main() -> None:
    args = build_parser().parse_args()
    structure_path = Path(args.structure_path)
    if not structure_path.is_file():
        emit_error(OP, f"Manifest not found: {structure_path}", code=1)
    require_cmd("ffmpeg", OP)
    manifest = json.loads(structure_path.read_text(encoding="utf-8"))
    source = Path(manifest.get("input_path") or "")
    if not source.is_file():
        emit_error(OP, f"Source media not found: {source}", code=1)

    profile, profile_path = load_profile(args.profile)
    require_embedded, min_gaps = effective_validation_policy(manifest, profile)
    manifest_validation = validate_manifest(
        manifest,
        require_embedded_timecode=require_embedded,
        min_gaps=min_gaps,
    )
    if not manifest_validation["passed"]:
        emit_error(OP, "; ".join(manifest_validation["errors"]), code=3)
    pdf_cfg = profile.get("pdf") or {}
    rows_per_page = min(8, max(4, int(args.rows_per_page or pdf_cfg.get("rows_per_page", 6))))
    fade_search_seconds = max(
        0.25,
        float(args.fade_search_seconds if args.fade_search_seconds is not None else pdf_cfg.get("fade_search_seconds", 10.0)),
    )
    thumbnail_width = max(
        160,
        int(args.thumbnail_width if args.thumbnail_width is not None else pdf_cfg.get("thumbnail_width", 320)),
    )
    labels_cfg = profile.get("labels") or {}
    overrides = effective_label_overrides(profile, args.label_overrides)
    validate_label_overrides(
        manifest,
        overrides,
        require_content=bool(labels_cfg.get("require_overrides_for_content", False)),
    )
    report = build_report(
        manifest,
        label_mode=str(labels_cfg.get("mode", "generic")),
        label_overrides=overrides,
    )
    segments_by_index = {
        int(segment.get("index", position)): segment
        for position, segment in enumerate(manifest.get("segments") or [])
    }
    fps = fps_as_float(manifest.get("fps") or (manifest.get("embedded_timecode") or {}).get("fps"))
    video_stream = int(((manifest.get("effective_config") or {}).get("streams") or {}).get("video_stream", 0))
    for row in report.get("rows") or []:
        index = int(row["index"])
        segment = segments_by_index[index]
        start_frame = int(round(float(segment["start"]) * fps))
        end_frame = int(round(float(segment["end"]) * fps))
        row["start_seconds"] = round(float(segment["start"]), 6)
        row["end_seconds"] = round(float(segment["end"]), 6)
        row["start_frame"] = start_frame
        row["end_frame_exclusive"] = end_frame
        row["duration_frames"] = max(0, end_frame - start_frame)
        if index in overrides:
            row["label"] = overrides[index]

    output = resolve_output(str(source), "_program_master_thumbnail_report.pdf", args.output)
    thumbnail_dir = output.parent / f"{output.stem}_thumbnails"
    emit_progress("selecting first-established-picture frames", 20)
    plan = build_thumbnail_plan(
        manifest,
        source_path=str(source),
        fade_search_seconds=fade_search_seconds,
        video_stream=video_stream,
    )
    emit_progress("extracting content thumbnails", 45)
    extracted = extract_thumbnail_frames(
        str(source),
        plan,
        output_dir=thumbnail_dir,
        width=thumbnail_width,
        video_stream=video_stream,
    )
    rows_by_index = {int(row["index"]): row for row in report.get("rows") or []}
    for item in plan:
        frame = int(item["source_frame"])
        row = rows_by_index[int(item["segment_index"])]
        row["thumbnail"] = {**item, "path": str(extracted[frame])}
    for row in report.get("rows") or []:
        if row.get("type") != "content":
            row["thumbnail"] = None

    report["report_type"] = "broadcast_segment_thumbnail_report"
    report["generated_at"] = (
        None
        if args.deterministic
        else datetime.now().astimezone().isoformat(timespec="seconds")
    )
    report["thumbnail_policy"] = {
        "content": "segment start, or first picture after a black hold, or first sustained upper-luma plateau after a proved fade",
        "gap": "black/silent placeholder",
        "fade_search_seconds": fade_search_seconds,
    }
    report["pdf_layout"] = {"rows_per_page": rows_per_page, "page_size": "letter-landscape"}
    report["pdf_path"] = str(output)
    report["thumbnail_dir"] = str(thumbnail_dir)
    report["generation"] = {
        "profile_path": str(profile_path),
        "label_overrides": label_override_provenance(args.label_overrides),
        "deterministic": bool(args.deterministic),
    }

    thumbnail_validation = validate_thumbnail_report(manifest, report)
    report["validation"] = {
        "passed": manifest_validation["passed"] and thumbnail_validation["passed"],
        "manifest": manifest_validation,
        "thumbnail_report": thumbnail_validation,
    }
    if not report["validation"]["passed"]:
        emit_error(OP, "; ".join(thumbnail_validation["errors"]), code=3)

    emit_progress("rendering PDF", 80)
    render_pdf(
        report,
        output,
        rows_per_page=rows_per_page,
        deterministic=bool(args.deterministic),
    )
    json_output = Path(args.json_output) if args.json_output else output.with_suffix(".json")
    json_output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    emit_progress("done", 100)
    emit_success(
        OP,
        {
            "output_path": str(output),
            "json_path": str(json_output),
            "thumbnail_dir": str(thumbnail_dir),
            "segment_count": len(report.get("rows") or []),
            "content_thumbnail_count": len(plan),
        },
        [str(output), str(json_output), *[str(path) for path in extracted.values()]],
    )


if __name__ == "__main__":
    main_wrapper(main)

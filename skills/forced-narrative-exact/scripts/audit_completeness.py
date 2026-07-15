# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2", "opencv-python-headless>=4.10"]
# ///

"""Audit report coverage against frame-aligned texted/textless program regions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from _common import emit, probe_video

OP = "forced_narrative_exact.audit_completeness"
ALLOWED_DISPOSITIONS = {
    "missing_dialogue",
    "subtitle_boundary_residual",
    "excluded_non_dialogue_text",
    "alignment_artifact",
}
BLOCKING_DISPOSITIONS = {"missing_dialogue", "subtitle_boundary_residual"}


def parse_region(value: str) -> tuple[int, int, int]:
    try:
        start, end, offset = (int(part) for part in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "region must be start,end_exclusive,textless_offset"
        ) from exc
    if start < 0 or end <= start or offset <= 0:
        raise argparse.ArgumentTypeError(
            "region must be start,end_exclusive,positive_textless_offset"
        )
    return start, end, offset


def parse_crop(value: str, source_width: int, source_height: int) -> tuple[int, int, int, int]:
    try:
        x, y, width, height = (int(part) for part in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("crop must be x,y,width,height") from exc
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise ValueError("crop dimensions must be positive and inside the source")
    if x + width > source_width or y + height > source_height:
        raise ValueError("crop extends beyond the source frame")
    return x, y, width, height


def scan_region(
    input_path: str,
    region: tuple[int, int, int],
    covered: list[tuple[int, int]],
    crop: tuple[int, int, int, int],
    pixel_threshold: int,
    min_pixels: int,
) -> list[dict]:
    start, end, offset = region
    x, y, width, height = crop
    texted = cv2.VideoCapture(input_path)
    textless = cv2.VideoCapture(input_path)
    if not texted.isOpened() or not textless.isOpened():
        raise RuntimeError("Could not open input")
    texted.set(cv2.CAP_PROP_POS_FRAMES, start)
    textless.set(cv2.CAP_PROP_POS_FRAMES, start + offset)
    rows: list[dict] = []
    covered_index = 0
    for frame_number in range(start, end):
        ok_a, frame_a = texted.read()
        ok_b, frame_b = textless.read()
        if not ok_a or not ok_b:
            raise RuntimeError(f"Decode failed at texted frame {frame_number}")
        while covered_index < len(covered) and covered[covered_index][1] <= frame_number:
            covered_index += 1
        is_covered = (
            covered_index < len(covered)
            and covered[covered_index][0] <= frame_number < covered[covered_index][1]
        )
        band_a = frame_a[y:y + height, x:x + width]
        band_b = frame_b[y:y + height, x:x + width]
        gray_a = cv2.cvtColor(band_a, cv2.COLOR_BGR2GRAY)
        gray_b = cv2.cvtColor(band_b, cv2.COLOR_BGR2GRAY)
        changed = int(np.count_nonzero(cv2.absdiff(gray_a, gray_b) > pixel_threshold))
        rows.append({
            "frame": frame_number,
            "textless_frame": frame_number + offset,
            "changed_pixels": changed,
            "qualifies": changed >= min_pixels,
            "covered": is_covered,
        })
    texted.release()
    textless.release()
    return rows


def group_uncovered(rows: list[dict], max_gap: int) -> list[dict]:
    hits = [row for row in rows if row["qualifies"] and not row["covered"]]
    if not hits:
        return []
    groups: list[list[dict]] = []
    current = [hits[0]]
    for row in hits[1:]:
        if row["frame"] - current[-1]["frame"] <= max_gap + 1:
            current.append(row)
        else:
            groups.append(current)
            current = [row]
    groups.append(current)
    return [{
        "start_frame": group[0]["frame"],
        "end_frame_exclusive": group[-1]["frame"] + 1,
        "qualifying_frame_count": len(group),
        "peak_changed_pixels": max(row["changed_pixels"] for row in group),
    } for group in groups]


def save_contact(input_path: str, interval: dict, output_path: Path, sample_step: int) -> list[int]:
    start, end = interval["start_frame"], interval["end_frame_exclusive"]
    samples = sorted(set([start, end - 1, *range(start, end, sample_step)]))
    capture = cv2.VideoCapture(input_path)
    cells = []
    for frame_number in samples:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ok, image = capture.read()
        if not ok:
            raise RuntimeError(f"Could not decode contact frame {frame_number}")
        image = cv2.resize(image, (480, 270), interpolation=cv2.INTER_AREA)
        canvas = np.full((298, 480, 3), 255, np.uint8)
        canvas[28:] = image
        cv2.putText(
            canvas,
            f"frame {frame_number}",
            (8, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )
        cells.append(canvas)
    capture.release()
    blank = np.full((298, 480, 3), 255, np.uint8)
    while len(cells) % 4:
        cells.append(blank.copy())
    contact = np.vstack([
        np.hstack(cells[index:index + 4])
        for index in range(0, len(cells), 4)
    ])
    cv2.imwrite(str(output_path), contact)
    return samples


def load_reviews(path: str | None) -> dict[tuple[int, int], dict]:
    if not path:
        return {}
    doc = json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))
    reviews: dict[tuple[int, int], dict] = {}
    for row in doc.get("candidates") or []:
        key = (int(row["start_frame"]), int(row["end_frame_exclusive"]))
        if key in reviews:
            raise ValueError(f"Duplicate completeness review interval {key}")
        reviews[key] = row
    return reviews


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument(
        "--region",
        action="append",
        type=parse_region,
        required=True,
        help="Repeat start,end_exclusive,textless_offset for every texted region.",
    )
    parser.add_argument("--crop", default="0,750,1920,330")
    parser.add_argument("--pixel-threshold", type=int, default=48)
    parser.add_argument("--min-pixels", type=int, default=1000)
    parser.add_argument("--max-gap", type=int, default=2)
    parser.add_argument("--sample-step", type=int, default=12)
    parser.add_argument("--review", help="Optional visually completed review JSON")
    parser.add_argument("--output", required=True)
    parser.add_argument("--contacts-dir", required=True)
    args = parser.parse_args()

    if not 0 <= args.pixel_threshold <= 255 or args.min_pixels <= 0:
        raise ValueError("Invalid pixel threshold or minimum changed-pixel count")
    if args.max_gap < 0 or args.sample_step <= 0:
        raise ValueError("max-gap must be nonnegative and sample-step must be positive")

    probe = probe_video(args.input)
    crop = parse_crop(args.crop, probe["width"], probe["height"])
    for start, end, offset in args.region:
        if end > probe["frame_count"] or end + offset > probe["frame_count"]:
            raise ValueError("A region or its aligned textless range exceeds the source")

    report_path = Path(args.report).expanduser().resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    covered = sorted(
        (int(row["start_frame"]), int(row["end_frame_exclusive"]))
        for row in report.get("rows") or []
    )
    reviews = load_reviews(args.review)
    all_intervals = []
    for region_index, region in enumerate(args.region, start=1):
        rows = scan_region(
            probe["input_path"], region, covered, crop, args.pixel_threshold, args.min_pixels
        )
        for interval in group_uncovered(rows, args.max_gap):
            interval["region_index"] = region_index
            all_intervals.append(interval)

    contacts_dir = Path(args.contacts_dir).expanduser().resolve()
    contacts_dir.mkdir(parents=True, exist_ok=True)
    matched_review_keys = set()
    for index, interval in enumerate(all_intervals, start=1):
        path = contacts_dir / (
            f"candidate_{index:04d}_{interval['start_frame']}_"
            f"{interval['end_frame_exclusive']}.jpg"
        )
        interval["contact_path"] = str(path)
        interval["sample_frames"] = save_contact(
            probe["input_path"], interval, path, args.sample_step
        )
        key = (interval["start_frame"], interval["end_frame_exclusive"])
        review = reviews.get(key)
        if review:
            matched_review_keys.add(key)
            disposition = str(review.get("disposition") or "")
            note = str(review.get("review_note") or "").strip()
            if disposition not in ALLOWED_DISPOSITIONS:
                raise ValueError(f"Invalid disposition {disposition!r} for interval {key}")
            if not note:
                raise ValueError(f"Missing review_note for interval {key}")
            interval["disposition"] = disposition
            interval["review_note"] = note
        else:
            interval["disposition"] = None
            interval["review_note"] = None

    unmatched = sorted(set(reviews) - matched_review_keys)
    if unmatched:
        raise ValueError(f"Review intervals not present in this audit: {unmatched}")
    reviewed_count = sum(bool(row["disposition"]) for row in all_intervals)
    blocking_count = sum(
        row["disposition"] in BLOCKING_DISPOSITIONS for row in all_intervals
    )
    publication_ready = reviewed_count == len(all_intervals) and blocking_count == 0
    output_path = Path(args.output).expanduser().resolve()
    payload = {
        "input_path": probe["input_path"],
        "report_path": str(report_path),
        "regions": [
            {"start_frame": start, "end_frame_exclusive": end, "offset_frames": offset}
            for start, end, offset in args.region
        ],
        "crop": {"x": crop[0], "y": crop[1], "width": crop[2], "height": crop[3]},
        "pixel_threshold": args.pixel_threshold,
        "min_pixels": args.min_pixels,
        "max_gap": args.max_gap,
        "sample_step": args.sample_step,
        "candidate_count": len(all_intervals),
        "reviewed_count": reviewed_count,
        "blocking_count": blocking_count,
        "publication_ready": publication_ready,
        "candidates": all_intervals,
    }
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    emit(
        True,
        OP,
        {
            "output_path": str(output_path),
            "candidate_count": len(all_intervals),
            "reviewed_count": reviewed_count,
            "blocking_count": blocking_count,
            "publication_ready": publication_ready,
        },
        [str(output_path), str(contacts_dir)],
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        emit(False, OP, {"error": str(exc)})
        raise SystemExit(1)

# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2", "opencv-python-headless>=4.10", "pytesseract>=0.3.13"]
# ///

"""Refine agent-transcribed forced-narrative cues to exact source-frame boundaries."""

from __future__ import annotations

import argparse
import difflib
import json
import math
import re
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytesseract
from pytesseract import Output

from _common import dump_json, emit, generated_dir, media_stem, parse_crop, probe_video, timing_fields

OP = "forced_narrative_exact.refine_boundaries"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--crop", help="Override crop as x,y,width,height")
    parser.add_argument("--threshold", type=int, default=166, help="White-text pixel threshold")
    parser.add_argument("--match-threshold", type=float, default=0.72)
    parser.add_argument("--padding", type=float, default=1.25, help="Seconds before/after approximate window")
    parser.add_argument("--ids", help="Comma-separated cue IDs for representative testing")
    parser.add_argument("--overrides", help="Optional visually verified overrides JSON")
    parser.add_argument("--output")
    parser.add_argument("--qc-dir", help="Boundary crop directory")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def tokens(text: str) -> list[str]:
    return [token.lower().replace("’", "'") for token in re.findall(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?", text)]


def ocr_boxes(gray: np.ndarray, expected_text: str, threshold: int) -> tuple[list[tuple[int, int, int, int]], str, int]:
    binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)[1]
    data = pytesseract.image_to_data(binary, config="--psm 6", output_type=Output.DICT)
    words: list[str] = []
    boxes: list[tuple[int, int, int, int]] = []
    visible: list[str] = []
    for index, raw in enumerate(data.get("text", [])):
        word = str(raw).strip()
        if not word:
            continue
        visible.append(word)
        normalized = "".join(tokens(word))
        if not normalized:
            continue
        x = int(data["left"][index])
        y = int(data["top"][index])
        w = max(1, int(data["width"][index]))
        h = max(1, int(data["height"][index]))
        words.append(normalized)
        boxes.append((x, y, w, h))
    expected = tokens(expected_text)
    selected: set[int] = set()
    matcher = difflib.SequenceMatcher(a=expected, b=words, autojunk=False)
    for block in matcher.get_matching_blocks():
        selected.update(range(block.b, block.b + block.size))
    for index, word in enumerate(words):
        if index in selected:
            continue
        if any((len(word) >= 2 and difflib.SequenceMatcher(a=word, b=target, autojunk=False).ratio() >= 0.68) for target in expected):
            selected.add(index)
    chosen = [boxes[index] for index in sorted(selected)]
    if not chosen:
        chosen = boxes
    return chosen, " ".join(visible), len(selected)


def decode_window(input_path: str, start_frame: int, end_frame_exclusive: int, crop: dict[str, int]) -> tuple[list[int], list[np.ndarray]]:
    capture = cv2.VideoCapture(input_path)
    if not capture.isOpened():
        raise RuntimeError("OpenCV could not open input")
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    indices, frames = [], []
    x, y, w, h = crop["x"], crop["y"], crop["width"], crop["height"]
    for frame_number in range(start_frame, end_frame_exclusive):
        ok, frame = capture.read()
        if not ok:
            break
        band = frame[y:y + h, x:x + w]
        if band.shape[0] != h or band.shape[1] != w:
            break
        indices.append(frame_number)
        frames.append(cv2.cvtColor(band, cv2.COLOR_BGR2GRAY))
    capture.release()
    if not frames:
        raise RuntimeError(f"Could not decode frames {start_frame}..{end_frame_exclusive}")
    return indices, frames


def build_template(gray: np.ndarray, boxes: list[tuple[int, int, int, int]], threshold: int) -> tuple[np.ndarray, tuple[int, int, int, int], int]:
    height, width = gray.shape
    if boxes:
        x0 = max(0, min(x for x, _, _, _ in boxes) - 3)
        y0 = max(0, min(y for _, y, _, _ in boxes) - 3)
        x1 = min(width, max(x + w for x, _, w, _ in boxes) + 3)
        y1 = min(height, max(y + h for _, y, _, h in boxes) + 3)
    else:
        x0, y0, x1, y1 = 0, 0, width, height
    region_mask = np.zeros((y1 - y0, x1 - x0), dtype=bool)
    if boxes:
        for x, y, w, h in boxes:
            xa, ya = max(x0, x - 1) - x0, max(y0, y - 1) - y0
            xb, yb = min(x1, x + w + 1) - x0, min(y1, y + h + 1) - y0
            region_mask[ya:yb, xa:xb] = True
    else:
        region_mask[:] = True
    bright = gray[y0:y1, x0:x1] >= threshold
    template = np.logical_and(bright, region_mask)
    return template, (x0, y0, x1, y1), int(template.sum())


def score_frame(gray: np.ndarray, template: np.ndarray, roi: tuple[int, int, int, int], threshold: int) -> float:
    x0, y0, x1, y1 = roi
    candidate = gray[y0:y1, x0:x1] >= threshold
    intersection = int(np.logical_and(candidate, template).sum())
    template_count = int(template.sum())
    union = int(np.logical_or(candidate, template).sum())
    if template_count == 0:
        return 0.0
    coverage = intersection / template_count
    jaccard = intersection / union if union else 0.0
    return (0.65 * coverage) + (0.35 * jaccard)


def timed_row(cue: dict[str, Any], start: int, end: int, probe: dict[str, Any], qc: dict[str, Any]) -> dict[str, Any]:
    fps = probe["fps_fraction"]
    embedded = probe.get("embedded_start_timecode")
    drop = probe["drop_frame"]
    start_t, end_t = timing_fields(start, fps, embedded, drop), timing_fields(end, fps, embedded, drop)
    lines = [str(line) for line in cue.get("lines") or str(cue.get("text") or "").splitlines()]
    return {
        "id": int(cue["id"]),
        "program_pass": int(cue.get("program_pass") or 1),
        "start_frame": start,
        "end_frame_exclusive": end,
        "duration_frames": end - start,
        "start_seconds": start_t["seconds"],
        "end_seconds": end_t["seconds"],
        "start_timecode": start_t["file_timecode"],
        "end_timecode": end_t["file_timecode"],
        "embedded_start_timecode": start_t["embedded_timecode"],
        "embedded_end_timecode": end_t["embedded_timecode"],
        "speaker": cue.get("speaker") or cue.get("speaker_context") or "—",
        "lines": lines,
        "text": "\n".join(lines),
        "qc": qc,
    }


def save_qc_frames(qc_dir: Path, cue_id: int, indices: list[int], frames: list[np.ndarray], start: int, end: int) -> list[str]:
    lookup = {frame: image for frame, image in zip(indices, frames)}
    paths = []
    for label, frame in (("before", start - 1), ("start", start), ("last", end - 1), ("end", end)):
        image = lookup.get(frame)
        if image is None:
            continue
        path = qc_dir / f"cue_{cue_id:04d}_{label}_frame_{frame:08d}.jpg"
        cv2.imwrite(str(path), image)
        paths.append(str(path))
    return paths


def refine_cue(cue: dict[str, Any], input_path: str, probe: dict[str, Any], crop: dict[str, int], args: argparse.Namespace, qc_dir: Path) -> dict[str, Any]:
    fps_float = float(probe["fps_fraction"])
    approx_start, approx_end = float(cue["approx_start"]), float(cue["approx_end"])
    window_start = max(0, math.floor((approx_start - args.padding) * fps_float))
    window_end = min(probe["frame_count"], math.ceil((approx_end + args.padding) * fps_float) + 1)
    reference_frame = round(((approx_start + approx_end) / 2) * fps_float)
    indices, frames = decode_window(input_path, window_start, window_end, crop)
    if reference_frame not in indices:
        reference_frame = indices[len(indices) // 2]
    ref_index = indices.index(reference_frame)
    expected_text = "\n".join(str(line) for line in cue.get("lines") or [])
    boxes, ocr_text, matched_count = ocr_boxes(frames[ref_index], expected_text, args.threshold)
    template, roi, template_pixels = build_template(frames[ref_index], boxes, args.threshold)
    scores = [score_frame(frame, template, roi, args.threshold) for frame in frames]
    scores[ref_index] = 1.0
    active = [score >= args.match_threshold for score in scores]
    left, right = ref_index, ref_index
    while left > 0 and active[left - 1]:
        left -= 1
    while right + 1 < len(active) and active[right + 1]:
        right += 1
    start, end = indices[left], indices[right] + 1
    duration_frames = end - start
    needs_review = (
        matched_count == 0 or template_pixels < 100 or duration_frames / fps_float < 1.0
        or left == 0 or right == len(active) - 1 or max(scores) < 0.85
    )
    qc_paths = save_qc_frames(qc_dir, int(cue["id"]), indices, frames, start, end)
    qc = {
        "approx_start": approx_start,
        "approx_end": approx_end,
        "reference_frame": reference_frame,
        "ocr_text": ocr_text,
        "matched_word_boxes": matched_count,
        "template_pixels": template_pixels,
        "peak_score": round(max(scores), 6),
        "threshold": args.match_threshold,
        "scan_start_frame": window_start,
        "scan_end_frame": window_end,
        "boundary_scores": {
            "before": round(scores[left - 1], 6) if left > 0 else None,
            "start": round(scores[left], 6),
            "last": round(scores[right], 6),
            "end": round(scores[right + 1], 6) if right + 1 < len(scores) else None,
        },
        "needs_review": needs_review,
        "qc_frame_paths": qc_paths,
    }
    return timed_row(cue, start, end, probe, qc)


def apply_overrides(rows: list[dict[str, Any]], path: str | None, probe: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    if not path:
        return rows, None
    override_path = Path(path).expanduser().resolve()
    doc = json.loads(override_path.read_text(encoding="utf-8"))
    overrides = {int(row["id"]): row for row in doc.get("rows", [])}
    output = []
    for row in rows:
        override = overrides.get(int(row["id"]))
        if not override:
            output.append(row)
            continue
        merged = {**row, **override}
        merged["qc"] = {**(row.get("qc") or {}), "manual_override": True, "review_note": override.get("review_note")}
        output.append(timed_row(merged, int(merged["start_frame"]), int(merged["end_frame_exclusive"]), probe, merged["qc"]))
    unknown = sorted(set(overrides) - {int(row["id"]) for row in rows})
    if unknown:
        raise ValueError(f"Override IDs not present in selected cues: {unknown}")
    return output, str(override_path)


def main() -> None:
    args = parse_args()
    if not 0 < args.match_threshold <= 1 or not 0 <= args.threshold <= 255 or args.padding <= 0:
        raise ValueError("Invalid threshold or padding")
    seed_path = Path(args.seed).expanduser().resolve()
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    probe = probe_video(args.input)
    seed_crop = seed.get("crop") or {}
    crop_text = args.crop or (f"{seed_crop.get('x')},{seed_crop.get('y')},{seed_crop.get('width')},{seed_crop.get('height')}" if seed_crop else None)
    crop = parse_crop(crop_text, probe["width"], probe["height"])
    selected_ids = {int(value) for value in args.ids.split(",")} if args.ids else None
    cues = [cue for cue in seed.get("cues", []) if selected_ids is None or int(cue["id"]) in selected_ids]
    if not cues:
        raise ValueError("No seed cues selected")
    out_dir = generated_dir()
    stem = media_stem(probe["input_path"])
    output_path = Path(args.output).expanduser().resolve() if args.output else out_dir / f"{stem}_forced_narrative_refined.json"
    qc_dir = Path(args.qc_dir).expanduser().resolve() if args.qc_dir else out_dir / f"{stem}_forced_narrative_boundary_qc"
    if output_path.exists() and not args.force:
        raise FileExistsError("Refined output exists; pass --force to replace it")
    qc_dir.mkdir(parents=True, exist_ok=True)
    rows = [refine_cue(cue, probe["input_path"], probe, crop, args, qc_dir) for cue in cues]
    rows, override_path = apply_overrides(rows, args.overrides, probe)
    payload = {
        "input_path": probe["input_path"],
        "seed_path": str(seed_path),
        "report_type": "forced_narrative_frame_refinement",
        "fps": probe["fps"],
        "drop_frame": probe["drop_frame"],
        "embedded_start_timecode": probe.get("embedded_start_timecode"),
        "crop": crop,
        "threshold": args.threshold,
        "match_threshold": args.match_threshold,
        "program_pass": seed.get("program_pass", 1),
        "program_passes": seed.get("program_passes") or {},
        "override_path": override_path,
        "row_count": len(rows),
        "needs_review_count": sum(bool((row.get("qc") or {}).get("needs_review")) for row in rows),
        "qc_dir": str(qc_dir),
        "rows": rows,
    }
    dump_json(output_path, payload)
    emit(True, OP, {"output_path": str(output_path), "row_count": len(rows), "needs_review_count": payload["needs_review_count"], "qc_dir": str(qc_dir)}, [str(output_path), str(qc_dir)])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        emit(False, OP, {"error": str(exc)})
        raise SystemExit(1)

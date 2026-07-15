# /// script
# requires-python = ">=3.11"
# dependencies = ["Pillow>=10", "pytesseract>=0.3.13"]
# ///

"""Extract a dense subtitle-band frame scan and OCR candidate index."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
import pytesseract

from _common import dump_json, emit, generated_dir, media_stem, parse_crop, probe_video

OP = "forced_narrative_exact.scan_caption_band"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--start", type=float, default=0.0, help="File-relative start seconds")
    parser.add_argument("--end", type=float, help="File-relative exclusive end seconds")
    parser.add_argument("--interval", type=float, default=0.5, help="Sampling interval in seconds")
    parser.add_argument("--crop", help="Pixel crop x,y,width,height; default is bottom 30.56%%")
    parser.add_argument("--threshold", type=int, default=166, help="White-text threshold, 0..255")
    parser.add_argument("--psm", type=int, default=6, help="Tesseract page segmentation mode")
    parser.add_argument("--output", help="Candidate scan JSON path")
    parser.add_argument("--frames-dir", help="Directory for retained scan JPGs")
    parser.add_argument("--force", action="store_true", help="Replace an existing scan and its generated frames")
    return parser.parse_args()


def clean_ocr(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.replace("\x0c", "").splitlines()]
    return "\n".join(line for line in lines if line).strip()


def main() -> None:
    args = parse_args()
    for binary in ("ffmpeg", "ffprobe", "tesseract"):
        if shutil.which(binary) is None:
            raise RuntimeError(f"Required binary not found: {binary}")
    probe = probe_video(args.input)
    start = max(0.0, float(args.start))
    end = float(args.end) if args.end is not None else float(probe["duration_seconds"])
    if args.interval <= 0 or end <= start or end > probe["duration_seconds"] + 0.05:
        raise ValueError("Require interval > 0 and 0 <= start < end <= source duration")
    if not 0 <= args.threshold <= 255:
        raise ValueError("--threshold must be 0..255")
    crop = parse_crop(args.crop, probe["width"], probe["height"])
    out_dir = generated_dir()
    stem = media_stem(probe["input_path"])
    json_path = Path(args.output).expanduser().resolve() if args.output else out_dir / f"{stem}_forced_narrative_band_scan.json"
    frames_dir = Path(args.frames_dir).expanduser().resolve() if args.frames_dir else out_dir / f"{stem}_forced_narrative_band_frames"
    if (json_path.exists() or frames_dir.exists()) and not args.force:
        raise FileExistsError("Scan output exists; pass --force to replace it")
    if args.force and frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    duration = end - start
    filter_text = f"fps={1.0 / args.interval:.12g},crop={crop['width']}:{crop['height']}:{crop['x']}:{crop['y']}"
    pattern = frames_dir / "frame_%06d.jpg"
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{start:.9f}", "-i", probe["input_path"],
        "-t", f"{duration:.9f}", "-vf", filter_text, "-q:v", "2", str(pattern),
    ]
    subprocess.run(command, check=True)
    frame_paths = sorted(frames_dir.glob("frame_*.jpg"))
    detections = []
    all_samples = []
    for offset, frame_path in enumerate(frame_paths):
        with Image.open(frame_path) as image:
            gray = image.convert("L")
            binary = gray.point(lambda value: 255 if value >= args.threshold else 0)
            enlarged = binary.resize((binary.width * 2, binary.height * 2), Image.Resampling.LANCZOS)
            text = clean_ocr(pytesseract.image_to_string(enlarged, config=f"--psm {args.psm}"))
        seconds = round(start + offset * args.interval, 6)
        sample = {"index": offset, "seconds": seconds, "frame_path": str(frame_path), "ocr_text": text}
        all_samples.append(sample)
        if any(character.isalnum() for character in text):
            detections.append(sample)
        if (offset + 1) % 100 == 0:
            print(json.dumps({"progress": offset + 1, "total": len(frame_paths), "detections": len(detections)}), file=sys.stderr)
    payload = {
        "input_path": probe["input_path"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "start_seconds": start,
        "end_seconds": end,
        "interval_seconds": args.interval,
        "frame_count": len(frame_paths),
        "detection_count": len(detections),
        "crop": crop,
        "threshold": args.threshold,
        "fps": probe["fps"],
        "embedded_start_timecode": probe.get("embedded_start_timecode"),
        "frames_dir": str(frames_dir),
        "samples": detections,
        "all_samples": all_samples,
    }
    dump_json(json_path, payload)
    emit(True, OP, {"output_path": str(json_path), "frames_dir": str(frames_dir), "frame_count": len(frame_paths), "detection_count": len(detections), "crop": crop}, [str(json_path), str(frames_dir)])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        emit(False, OP, {"error": str(exc)})
        raise SystemExit(1)

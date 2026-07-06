# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pillow>=10.0.0",
# ]
# ///

"""Burn SRT captions into a video using Pillow overlays and ffmpeg."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from _mediaskills_common import (
    EXIT_BAD_ARGS,
    EXIT_PROCESSING,
    add_input_arg,
    add_output_arg,
    emit_error,
    emit_progress,
    emit_success,
    ffprobe_json,
    main_wrapper,
    parse_srt,
    require_cmd,
    resolve_output,
    validate_input_path,
)


def probe_size(path: str, op: str) -> tuple[int, int]:
    data = ffprobe_json(path, op)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video:
        emit_error(op, "No video stream found in input file", code=EXIT_BAD_ARGS)
    return int(video["width"]), int(video["height"])


def render_caption_png(text: str, width: int, height: int, dest: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font_size = max(18, height // 24)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", font_size)
    except OSError:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except OSError:
            font = ImageFont.load_default()

    margin = width // 20
    max_width = width - margin * 2
    words = text.replace("\n", " ").split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    if not lines:
        lines = [text]

    line_sizes = [draw.textbbox((0, 0), ln, font=font) for ln in lines]
    line_heights = [b[3] - b[1] for b in line_sizes]
    text_height = sum(line_heights) + max(0, len(lines) - 1) * 8
    pad_x, pad_y = 24, 16
    box_w = max(b[2] - b[0] for b in line_sizes) + pad_x * 2
    box_h = text_height + pad_y * 2
    box_x = (width - box_w) // 2
    box_y = height - box_h - max(24, height // 16)

    draw.rounded_rectangle(
        (box_x, box_y, box_x + box_w, box_y + box_h),
        radius=12,
        fill=(0, 0, 0, 160),
    )

    y = box_y + pad_y
    for ln, bbox, lh in zip(lines, line_sizes, line_heights):
        tw = bbox[2] - bbox[0]
        x = (width - tw) // 2
        draw.text((x, y), ln, font=font, fill=(255, 255, 255, 255))
        y += lh + 8

    img.save(dest)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run burn.py --input clip.mp4 --subtitle captions.srt",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument(
        "--subtitle",
        "-s",
        required=True,
        help="Path to an SRT subtitle file",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "subtitles.burn"
    path = validate_input_path(args.input, op)
    subtitle_path = Path(args.subtitle)
    if not subtitle_path.is_file():
        emit_error(op, f"Subtitle file not found: {args.subtitle}", code=EXIT_BAD_ARGS)

    require_cmd("ffmpeg", op)
    require_cmd("ffprobe", op)

    emit_progress("parsing captions", 5)
    cues = parse_srt(subtitle_path.read_text(encoding="utf-8"))
    if not cues:
        emit_error(op, "No cues found in subtitle file", code=EXIT_BAD_ARGS)

    width, height = probe_size(str(path), op)
    out_path = resolve_output(str(path), "_subbed.mp4", args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            pngs: list[Path] = []
            for i, cue in enumerate(cues):
                png = tmp_dir / f"cap_{i:04d}.png"
                render_caption_png(str(cue["text"]), width, height, png)
                pngs.append(png)
                emit_progress("rendering overlays", 10 + 40 * (i + 1) / len(cues))

            cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(path)]
            for png in pngs:
                cmd.extend(["-i", str(png)])

            filter_parts: list[str] = []
            last = "[0:v]"
            for i, cue in enumerate(cues):
                start = float(cue["start"])
                end = float(cue["end"])
                out_label = f"[v{i}]"
                filter_parts.append(
                    f"{last}[{i + 1}:v]overlay=0:0:enable='between(t\\,{start:.3f}\\,{end:.3f})'"
                    f"{out_label}"
                )
                last = out_label

            cmd.extend(
                [
                    "-filter_complex",
                    ";".join(filter_parts),
                    "-map",
                    last,
                    "-map",
                    "0:a?",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "20",
                    "-c:a",
                    "copy",
                    str(out_path),
                ]
            )

            emit_progress("encoding", 60)
            subprocess.run(cmd, check=True, capture_output=True)

        if not out_path.is_file() or out_path.stat().st_size == 0:
            emit_error(op, "No output written", code=EXIT_PROCESSING)

        emit_progress("done", 100)
        emit_success(
            op,
            {"output_path": str(out_path), "cue_count": len(cues)},
            [str(out_path)],
        )
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode("utf-8", errors="replace")[:800]
        emit_error(op, f"ffmpeg failed: {err}", code=EXIT_PROCESSING)


if __name__ == "__main__":
    main_wrapper(main)

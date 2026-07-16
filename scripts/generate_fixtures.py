#!/usr/bin/env python3
"""Generate ground-truth media fixtures for local semantic tests.

Usage (from repo root):
  python scripts/generate_fixtures.py
  python scripts/generate_fixtures.py --force
"""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr}"
        )


def write_meta(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def generate_cuts_3scene(force: bool) -> Path:
    out = FIXTURES / "cuts_3scene.mp4"
    meta = FIXTURES / "cuts_3scene.meta.json"
    if out.is_file() and meta.is_file() and not force:
        return out
    # Distinct synthetic patterns so ffmpeg scene scores exceed default thresholds
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=1.5:size=320x240:rate=30",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=duration=1.5:size=320x240:rate=30",
            "-f",
            "lavfi",
            "-i",
            "color=c=magenta:s=320x240:r=30:d=1.5",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=4.5",
            "-filter_complex",
            "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
            "-map",
            "[v]",
            "-map",
            "3:a",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(out),
        ]
    )
    write_meta(
        meta,
        {
            "expected_shot_count": 3,
            "expected_cut_times_seconds": [1.5, 3.0],
            "duration_seconds": 4.5,
            "notes": "Hard pattern cuts; shots.detect should report 3 shots",
        },
    )
    return out


def generate_program_gaps(force: bool) -> Path:
    out = FIXTURES / "program_gaps.mp4"
    meta = FIXTURES / "program_gaps.meta.json"
    if out.is_file() and meta.is_file() and not force:
        return out
    # content 2s + black/silent 1s + content 2s → expect ≥1 black+silent gap
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2:size=320x240:rate=30",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x240:r=30:d=1",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=duration=2:size=320x240:rate=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono:d=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=660:duration=2",
            "-filter_complex",
            "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v];[3:a][4:a][5:a]concat=n=3:v=0:a=1[a]",
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(out),
        ]
    )
    write_meta(
        meta,
        {
            "expected_min_gap_count": 1,
            "duration_seconds": 5.0,
            "notes": "Black+silent middle second; program_master.detect_black_silence gap_count >= 1",
        },
    )
    return out


def write_caption_band_png(path: Path) -> None:
    """Write a 320x80 HELLO WORLD band without ImageMagick/drawtext."""
    font = {
        "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
        "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
        "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
        "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
        "W": ["10001", "10001", "10001", "10101", "10101", "01010", "01010"],
        "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
        "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
        " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    }
    text = "HELLO WORLD"
    scale = 4
    width, height = 320, 80
    pixels = [0] * (width * height * 3)
    cursor_x, cursor_y = 20, 20

    def set_px(x: int, y: int) -> None:
        if 0 <= x < width and 0 <= y < height:
            index = (y * width + x) * 3
            pixels[index : index + 3] = [255, 255, 255]

    for char in text:
        glyph = font.get(char, font[" "])
        for gy, line in enumerate(glyph):
            for gx, bit in enumerate(line):
                if bit != "1":
                    continue
                for sy in range(scale):
                    for sx in range(scale):
                        set_px(cursor_x + gx * scale + sx, cursor_y + gy * scale + sy)
        cursor_x += 5 * scale + 2 * scale

    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw.extend(pixels[y * width * 3 : (y + 1) * width * 3])

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def generate_burned_in_captions(force: bool) -> Path:
    out = FIXTURES / "burned_in_captions.mp4"
    meta = FIXTURES / "burned_in_captions.meta.json"
    band = FIXTURES / "hello_caption_band.png"
    if out.is_file() and meta.is_file() and band.is_file() and not force:
        return out
    write_caption_band_png(band)
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x240:r=30:d=3",
            "-loop",
            "1",
            "-i",
            str(band),
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=3",
            "-filter_complex",
            "[0:v][1:v]overlay=0:160:enable='between(t,0.5,2.0)'[v]",
            "-map",
            "[v]",
            "-map",
            "2:a",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            "-t",
            "3",
            str(out),
        ]
    )
    write_meta(
        meta,
        {
            "expected_text_contains": "HELLO",
            "caption_band": {"x": 0, "y": 160, "width": 320, "height": 80},
            "text_visible_seconds": [0.5, 2.0],
            "duration_seconds": 3.0,
            "notes": "Lower-third overlay PNG; FNE/OCR paths should discover HELLO",
        },
    )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Regenerate even if files exist")
    args = parser.parse_args()
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is required on PATH")
    FIXTURES.mkdir(parents=True, exist_ok=True)
    paths = [
        generate_cuts_3scene(args.force),
        generate_program_gaps(args.force),
        generate_burned_in_captions(args.force),
    ]
    print(json.dumps({"ok": True, "generated": [str(p) for p in paths]}, indent=2))


if __name__ == "__main__":
    main()

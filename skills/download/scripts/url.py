# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Download media from a URL using yt-dlp."""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

from _mediaskills_common import (
    EXIT_PROCESSING,
    emit_error,
    emit_progress,
    emit_success,
    main_wrapper,
    require_cmd,
)


def downloads_dir() -> Path:
    data_dir = os.environ.get("MEDIASKILLS_DATA_DIR")
    if data_dir and data_dir.startswith("/"):
        out = Path(data_dir) / "downloads"
    else:
        out = Path.cwd() / ".mediaskills" / "downloads"
    out.mkdir(parents=True, exist_ok=True)
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run url.py --url 'https://www.youtube.com/watch?v=...'",
    )
    parser.add_argument("--url", "-u", required=True, help="Media URL to download")
    return parser


def newest_file(directory: Path) -> Path | None:
    files = [p for p in directory.iterdir() if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def main() -> None:
    args = build_parser().parse_args()
    op = "download.url"
    url = args.url.strip()
    if not url:
        emit_error(op, "URL is required", code=1)

    out_dir = downloads_dir()
    require_cmd("yt-dlp", op)
    output_template = str(out_dir / "%(title).200B [%(id)s].%(ext)s")

    emit_progress("downloading", 20)
    out_path: Path | None = None

    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--newline",
                "-o",
                output_template,
                "--print",
                "after_move:filepath",
                url,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            out_path = Path(result.stdout.strip().splitlines()[-1])
        else:
            fallback = subprocess.run(
                ["yt-dlp", "--newline", "-o", output_template, url],
                capture_output=True,
                text=True,
            )
            if fallback.returncode != 0:
                err = (fallback.stderr or result.stderr or "yt-dlp failed")[-400:]
                emit_error(op, f"yt-dlp failed: {err}", code=EXIT_PROCESSING)
            candidate = newest_file(out_dir)
            if candidate is not None:
                out_path = candidate
    finally:
        tmp_path.unlink(missing_ok=True)

    emit_progress("done", 100)

    if out_path is None or not out_path.is_file():
        emit_error(op, "Download finished but output file not found", code=EXIT_PROCESSING)

    emit_success(
        op,
        {"url": url, "output_path": str(out_path), "output_dir": str(out_dir)},
        [str(out_path)],
    )


if __name__ == "__main__":
    main_wrapper(main)

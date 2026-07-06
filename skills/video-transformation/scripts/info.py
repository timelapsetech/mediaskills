# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Return video-transformation skill capabilities and requirements."""

from __future__ import annotations

import argparse

from _mediaskills_common import emit_success, main_wrapper


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run info.py",
    )


def main() -> None:
    build_parser().parse_args()
    emit_success(
        "video.info",
        {
            "binaries": ["ffmpeg", "ffprobe"],
            "operations": [
                "trim",
                "trim_multi",
                "concat",
                "transcode",
                "scale",
                "proxy",
                "extract_frame",
                "extract_audio",
                "to_gif",
                "replace_audio",
            ],
            "destructive": True,
            "default_output_dir": ".mediaskills/generated/",
            "notes": (
                "Use replace_audio.py for external audio; transcode.py only re-encodes "
                "streams from a single input file."
            ),
        },
    )


if __name__ == "__main__":
    main_wrapper(main)

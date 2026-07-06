# /// script
# requires-python = ">=3.11"
# dependencies = ["timecode>=1.5.1"]
# ///

"""Return timecode format reference information."""

from __future__ import annotations

import argparse

from _mediaskills_common import emit_success, main_wrapper
from _timecode_lib import SUPPORTED_FPS


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run info.py",
    )


def main() -> None:
    build_parser().parse_args()
    emit_success(
        "timecode.info",
        {
            "supported_fps": SUPPORTED_FPS,
            "formats": {
                "non_drop_frame": "HH:MM:SS:FF",
                "drop_frame": "HH:MM:SS;FF",
                "milliseconds": "HH:MM:SS.mmm (library ms mode)",
            },
            "library": "timecode (https://github.com/eoyilmaz/timecode)",
            "notes": (
                "Drop-frame applies to NTSC nominal rates (29.97, 59.94, etc.). "
                "Semicolon in the frame field marks drop-frame display. "
                "Use detect_format.py or analyze_metadata.py to infer format from assets."
            ),
        },
    )


if __name__ == "__main__":
    main_wrapper(main)

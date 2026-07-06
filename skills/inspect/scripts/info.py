# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Return inspect skill capabilities and requirements."""

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
        "inspect.info",
        {
            "read_only": True,
            "binaries": ["ffprobe"],
            "scripts": [
                "probe.py",
                "describe.py",
                "duration.py",
                "resolution.py",
                "compare.py",
                "batch_probe.py",
                "ask.py",
            ],
            "outputs": "JSON metadata only; no file writes except optional compare tables",
            "notes": "Run before destructive video/audio/image operations.",
        },
    )


if __name__ == "__main__":
    main_wrapper(main)

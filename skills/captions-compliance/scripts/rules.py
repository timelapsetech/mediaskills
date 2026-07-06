# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Return broadcast caption compliance rules (FCC-oriented heuristics)."""

from __future__ import annotations

import argparse

from _mediaskills_common import emit_success, main_wrapper


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run rules.py",
    )


def main() -> None:
    build_parser().parse_args()
    op = "caption.rules"
    emit_success(
        op,
        {
            "rules": [
                {
                    "id": "max_chars",
                    "value": 42,
                    "description": "Prefer <= 42 characters per caption line (FCC safe-reading guidance)",
                },
                {
                    "id": "max_lines",
                    "value": 2,
                    "description": "Prefer at most 2 lines on screen",
                },
                {
                    "id": "min_duration",
                    "value": 1.0,
                    "description": "Minimum on-screen duration in seconds",
                },
                {
                    "id": "max_duration",
                    "value": 7.0,
                    "description": "Maximum on-screen duration in seconds",
                },
                {
                    "id": "reading_speed",
                    "value": 20,
                    "description": "Approximate characters per second reading speed",
                },
                {
                    "id": "safe_area",
                    "value": "10%",
                    "description": "Keep text within title-safe margins",
                },
            ]
        },
    )


if __name__ == "__main__":
    main_wrapper(main)

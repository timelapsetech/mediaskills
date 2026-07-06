# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Return probe data for an agent to answer a question about a file."""

from __future__ import annotations

import argparse

from _mediaskills_common import (
    add_input_arg,
    emit_error,
    emit_success,
    ffprobe_json,
    main_wrapper,
    validate_input_path,
    EXIT_BAD_ARGS,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="The agent reads probe data and answers --question in natural language.",
    )
    add_input_arg(parser)
    parser.add_argument("--question", required=True, help="Question about the media file")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    op = "inspect.ask"
    if not args.question.strip():
        emit_error(op, "--question must not be empty", code=EXIT_BAD_ARGS)
    path = validate_input_path(args.input, op)
    probe = ffprobe_json(str(path), op)
    emit_success(
        op,
        {
            "input_path": str(path),
            "question": args.question,
            "probe": probe,
        },
    )


if __name__ == "__main__":
    main_wrapper(main)

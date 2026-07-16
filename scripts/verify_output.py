#!/usr/bin/env python3
"""Verify mediaskills script envelopes and optional media constraints.

Agents (and local smoke) can call this after a skill step to fail closed on
path, size, and duration checks before chaining or delivery.

Examples:
  python scripts/verify_output.py --from-json /tmp/out.json
  python scripts/verify_output.py --path /tmp/clip.mp4 --min-duration 0.9 --max-duration 1.2
  echo '{"ok":true,"op":"x","data":{},"output_paths":["/tmp/a.mp4"]}' \\
    | python scripts/verify_output.py --from-stdin --require-paths
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _ffprobe_duration(path: Path) -> float | None:
    if shutil.which("ffprobe") is None:
        return None
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def _load_envelope(args: argparse.Namespace) -> dict | None:
    if args.from_stdin:
        text = sys.stdin.read().strip()
        if not text:
            raise SystemExit("empty stdin")
        return json.loads(text.splitlines()[-1])
    if args.from_json:
        text = Path(args.from_json).read_text(encoding="utf-8").strip()
        return json.loads(text.splitlines()[-1])
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-json", type=Path, help="Path to a skill JSON envelope file")
    parser.add_argument(
        "--from-stdin",
        action="store_true",
        help="Read the skill JSON envelope from stdin (last line)",
    )
    parser.add_argument(
        "--require-paths",
        action="store_true",
        default=True,
        help="Require ok:true and existing non-empty output_paths (default)",
    )
    parser.add_argument(
        "--no-require-paths",
        action="store_false",
        dest="require_paths",
        help="Skip envelope path checks",
    )
    parser.add_argument("--path", action="append", default=[], help="Extra path to verify (repeatable)")
    parser.add_argument("--min-bytes", type=int, default=1, help="Minimum file size in bytes")
    parser.add_argument("--min-duration", type=float, help="Minimum media duration in seconds")
    parser.add_argument("--max-duration", type=float, help="Maximum media duration in seconds")
    parser.add_argument(
        "--duration-tolerance",
        type=float,
        default=0.15,
        help="Unused placeholder for agent docs; bounds are strict min/max",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    errors: list[str] = []
    paths: list[Path] = [Path(p) for p in args.path]

    envelope = _load_envelope(args)
    if envelope is not None:
        if args.require_paths:
            if envelope.get("ok") is not True:
                errors.append(f"envelope ok is not true: {envelope.get('ok')!r}")
            out_paths = envelope.get("output_paths")
            if not isinstance(out_paths, list) or not out_paths:
                errors.append("envelope output_paths missing or empty")
            else:
                paths.extend(Path(p) for p in out_paths)

    for path in paths:
        if not path.is_file():
            errors.append(f"missing file: {path}")
            continue
        size = path.stat().st_size
        if size < args.min_bytes:
            errors.append(f"too small ({size} < {args.min_bytes} bytes): {path}")
            continue
        if args.min_duration is not None or args.max_duration is not None:
            duration = _ffprobe_duration(path)
            if duration is None:
                errors.append(f"could not probe duration: {path}")
                continue
            if args.min_duration is not None and duration < args.min_duration:
                errors.append(f"duration {duration:.3f}s < min {args.min_duration}: {path}")
            if args.max_duration is not None and duration > args.max_duration:
                errors.append(f"duration {duration:.3f}s > max {args.max_duration}: {path}")

    if errors:
        payload = {"ok": False, "op": "mediaskills.verify_output", "error": "; ".join(errors)}
        print(json.dumps(payload), file=sys.stderr)
        raise SystemExit(1)

    print(
        json.dumps(
            {
                "ok": True,
                "op": "mediaskills.verify_output",
                "data": {"checked_paths": [str(p) for p in paths]},
                "output_paths": [str(p) for p in paths],
            }
        )
    )


if __name__ == "__main__":
    main()

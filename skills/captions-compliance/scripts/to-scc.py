# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Export SRT cues to Scenarist SCC V1.0 (CEA-608 pop-on captions)."""

from __future__ import annotations

import argparse
import re

from _mediaskills_common import (
    add_input_arg,
    add_output_arg,
    emit_error,
    emit_success,
    main_wrapper,
    parse_srt,
    resolve_output,
    validate_input_path,
)

OP = "caption.to_scc"

# CEA-608 channel-1 control codes (without parity).
RCL = (0x14, 0x20)  # Resume Caption Loading
ENM = (0x14, 0x2E)  # Erase Non-Displayed Memory
EOC = (0x14, 0x2F)  # End Of Caption (display)
EDM = (0x14, 0x2C)  # Erase Displayed Memory

# Preamble Address Codes: (row, white, indent 0) without parity.
PAC_ROW = {
    1: (0x11, 0x40),
    2: (0x11, 0x60),
    3: (0x12, 0x40),
    4: (0x12, 0x60),
    5: (0x15, 0x40),
    6: (0x15, 0x60),
    7: (0x16, 0x40),
    8: (0x16, 0x60),
    9: (0x17, 0x40),
    10: (0x17, 0x60),
    11: (0x10, 0x40),
    12: (0x13, 0x40),
    13: (0x13, 0x60),
    14: (0x14, 0x40),
    15: (0x14, 0x60),
}

BASIC_CHARS = set(
    " !\"#$%&'()*+,-./0123456789:;<=>?"
    "@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_"
    "`abcdefghijklmnopqrstuvwxyz{|}~"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run to-scc.py --input captions.srt",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    return parser


def odd_parity(byte: int) -> int:
    b = byte & 0x7F
    if bin(b).count("1") % 2 == 0:
        return b | 0x80
    return b


def word(b1: int, b2: int) -> str:
    return f"{odd_parity(b1):02x}{odd_parity(b2):02x}"


def control_word(pair: tuple[int, int]) -> str:
    return word(pair[0], pair[1])


def seconds_to_smpte(seconds: float, fps: float = 29.97) -> str:
    if seconds < 0:
        seconds = 0.0
    total_frames = int(round(seconds * fps))
    ff = total_frames % 30
    total_seconds = total_frames // 30
    ss = total_seconds % 60
    total_minutes = total_seconds // 60
    mm = total_minutes % 60
    hh = total_minutes // 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def sanitize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    out: list[str] = []
    for ch in text:
        if ch == "\n":
            out.append("\n")
        elif ch in BASIC_CHARS:
            out.append(ch)
        elif ch in "“”":
            out.append('"')
        elif ch in "‘’":
            out.append("'")
        elif ch == "—":
            out.append("-")
        elif ch == "…":
            out.append("...")
        else:
            out.append("?")
    return "".join(out).strip()


def split_rows(text: str, max_chars: int = 32, max_rows: int = 2) -> list[str]:
    text = sanitize_text(text)
    if not text:
        return []
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if len(paragraphs) >= 2:
        return [p[:max_chars] for p in paragraphs[:max_rows]]

    words = text.split(" ")
    rows: list[str] = []
    current = ""
    for w in words:
        candidate = w if not current else f"{current} {w}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                rows.append(current[:max_chars])
            current = w[:max_chars]
            if len(rows) >= max_rows:
                break
    if current and len(rows) < max_rows:
        rows.append(current[:max_chars])
    return rows[:max_rows]


def encode_chars(s: str) -> list[str]:
    codes = [ord(c) & 0x7F for c in s]
    if len(codes) % 2 == 1:
        codes.append(0x00)
    words: list[str] = []
    for i in range(0, len(codes), 2):
        words.append(word(codes[i], codes[i + 1]))
    return words


def encode_cue(start: float, end: float, text: str) -> list[str]:
    rows = split_rows(text)
    if not rows:
        return []

    words: list[str] = [control_word(RCL), control_word(ENM)]
    start_row = 14
    for i, row_text in enumerate(rows):
        row_num = start_row + i
        pac = PAC_ROW[row_num]
        words.append(control_word(pac))
        words.extend(encode_chars(row_text))
    words.append(control_word(EOC))

    start_tc = seconds_to_smpte(start)
    end_tc = seconds_to_smpte(max(end, start + 1 / 30))
    if end_tc <= start_tc:
        end_tc = seconds_to_smpte(start + 2 / 30)

    return [
        f"{start_tc}\t{' '.join(words)}",
        f"{end_tc}\t{control_word(EDM)}",
    ]


def validate_scc(content: str) -> list[str]:
    errors: list[str] = []
    lines = content.splitlines()
    if not lines or lines[0].strip() != "Scenarist_SCC V1.0":
        errors.append("Missing or invalid header (expected 'Scenarist_SCC V1.0')")
        return errors

    tc_re = re.compile(r"^(\d{2}):(\d{2}):(\d{2}):(\d{2})$")
    word_re = re.compile(r"^[0-9a-fA-F]{4}$")
    data_lines = 0
    for i, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        if "\t" not in line:
            errors.append(f"Line {i}: expected timecode<TAB>data")
            continue
        tc, data = line.split("\t", 1)
        m = tc_re.match(tc.strip())
        if not m:
            errors.append(f"Line {i}: invalid timecode '{tc}'")
            continue
        ff = int(m.group(4))
        if ff > 29:
            errors.append(f"Line {i}: frame number {ff} out of range (0-29)")
        words = data.strip().split()
        if not words:
            errors.append(f"Line {i}: empty caption data")
            continue
        for w in words:
            if not word_re.match(w):
                errors.append(f"Line {i}: invalid hex word '{w}'")
                continue
            b1 = int(w[:2], 16)
            b2 = int(w[2:], 16)
            if odd_parity(b1 & 0x7F) != b1 or odd_parity(b2 & 0x7F) != b2:
                errors.append(f"Line {i}: word '{w}' has invalid odd parity")
        data_lines += 1

    if data_lines == 0:
        errors.append("No caption data lines found")
    return errors


def cues_to_scc(cues: list[dict]) -> str:
    lines = ["Scenarist_SCC V1.0", ""]
    for cue in cues:
        text = str(cue.get("text") or "")
        start = float(cue["start"])
        end = float(cue["end"])
        for row in encode_cue(start, end, text):
            lines.append(row)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = build_parser().parse_args()
    path = validate_input_path(args.input, OP)
    cues = parse_srt(path.read_text(encoding="utf-8", errors="replace"))
    if not cues:
        emit_error(OP, "No cues found in SRT")

    content = cues_to_scc(cues)
    errors = validate_scc(content)
    if errors:
        emit_error(OP, "Generated SCC failed validation: " + "; ".join(errors[:5]))

    out = resolve_output(str(path), ".scc", args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8", newline="\n")
    emit_success(
        OP,
        {
            "output_path": str(out),
            "cue_count": len(cues),
            "format": "Scenarist_SCC V1.0",
            "encoding": "CEA-608",
            "valid": True,
        },
        [str(out)],
    )


if __name__ == "__main__":
    main_wrapper(main)

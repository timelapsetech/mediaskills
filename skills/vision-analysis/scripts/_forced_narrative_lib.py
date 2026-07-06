"""Extract burned-in dialogue / forced narrative rows and render QC-style reports."""

from __future__ import annotations

import csv
import json
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import json
import subprocess

from _mediaskills_common import generated_dir
from _report_lib import _looks_like_dialogue, _is_placeholder, frame_on_screen_items

# Speaker label before colon (burned-in caption style).
_SPEAKER_LINE = re.compile(
    r"^(?:[\s>\-|_\\*]+)*(?P<speaker>[A-Z][A-Z0-9\s/'().\-]+?)\s*:\s*(?P<quote>.+)$"
)

# Speaker-only line; dialogue often follows on the next OCR line.
_SPEAKER_ONLY = re.compile(
    r"^(?:[\s>\-|_\\*]+)*(?P<speaker>"
    r"SQUATT(?:ER|TER)(?:\s*\([^)]+\))?|OFFICER|DISPATCH|TENANT|"
    r"CITY\.?\s*WORKER|KATRINA|ASH'S SON|SECURITY\s*/\s*SAFETY|"
    r"SQUATTER HUNTERS|SOUTER HUNTERS|SMATTE(?:R|A))\s*:?\s*$",
    re.I,
)

# Map OCR speaker labels to display names.
_SPEAKER_ALIASES = {
    "squatter": "Squatter",
    "squatter on phone": "Squatter (phone)",
    "officer": "Officer",
    "dispatch": "Dispatch",
    "tenant": "Tenant",
    "city worker": "City worker",
    "katrina": "Katrina",
    "ash's son": "Ash's son",
    "security / safety": "Security / safety",
    "squatter hunters": "Squatter Hunters",
}

# Static cards and non-dialogue overlays to drop from forced-narrative reports.
_EXCLUDE_BLOCK = re.compile(
    r"(?:Program ID#|TEXTLESS CONTENT|Snap-Ins at|Textless at|TRT\s*-|"
    r"Ch \d+\s*-\s*Stereo|Fullscreen 16x9|1080p/|Grinning Dog Productions|"
    r"The bathroom is a shared space|retain the right to access|"
    r"Despite the squatter's claim|exclusive control, lawful|"
    r"Co-Executive Producers|Executive In Charge|Production Manager|"
    r"A&E Executive Producers|Finishing Facility|Post Supervisor|"
    r"Senior Producer|Assistant Camera|Audio Supervisors|"
    r"The following program features trained|Viewer discretion is advised|"
    r"Under .+ law,|shared spaces are treated|locked bedroom remains|"
    r"PRODUCED BY GRINNING DOG|ALL RIGHTS RESERVED|Built-In Pump|"
    r"ONE-STEP INF)",
    re.I,
)

_BRAND_ONLY = re.compile(
    r"^(?:SQUATTERS?|SQUATTER HUNTERS?|SUTTER HUNTERS?|SMUTTE?R HUNTERS?|"
    r"SECURITY\s*/\s*SAFETY|SQUATTER'S[\-\s]OCCUPANCY)$",
    re.I,
)

_TIME_LOCATOR = re.compile(r"^\d{1,2}:\d{2}\s*(?:AM|PM)\s*$", re.I)


def _norm_speaker(raw: str) -> str:
    s = " ".join(raw.split()).strip(" -_|*\\")
    if not s:
        return "—"
    key = s.lower()
    if key in _SPEAKER_ALIASES:
        return _SPEAKER_ALIASES[key]
    # Title-case known roles while preserving parentheticals.
    parts = re.split(r"(\([^)]+\))", s)
    out: list[str] = []
    for part in parts:
        if part.startswith("("):
            out.append(part.lower())
        else:
            out.append(part.title())
    return "".join(out) or "—"


def _clean_quote(text: str) -> str:
    q = " ".join(text.split())
    q = q.strip(" -_|\\")
    q = re.sub(r"^[>\-|_\\]+\s*", "", q)
    return q


def is_ocr_garbage(text: str, *, allow_short: bool = False) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if len(t) < 6 and not allow_short:
        return True
    if _is_placeholder(t):
        return True
    letters = sum(ch.isalpha() for ch in t)
    if letters / max(len(t), 1) < 0.52:
        return True
    words = re.findall(r"[A-Za-z']{3,}", t)
    if len(words) < 2 and not re.search(r"[?!]", t):
        return True
    weird = len(re.findall(r"[^\w\s'\",.!?\-:;()/\[\]]", t))
    if weird > max(2, len(t) * 0.08):
        return True
    # Mostly junk tokens (very short words, random caps).
    short_tokens = sum(1 for w in t.split() if len(re.sub(r"\W", "", w)) <= 2)
    if short_tokens / max(len(t.split()), 1) > 0.45:
        return True
    return False


def is_excluded_overlay(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if _EXCLUDE_BLOCK.search(t):
        return True
    if _BRAND_ONLY.match(t):
        return True
    if _TIME_LOCATOR.match(t):
        return True
    if t.upper() in {"SQUATTERS", "SQUATTER HUNTERS", "OFFICER 4"}:
        return True
    return False


def parse_speaker_line(line: str) -> tuple[str | None, str | None]:
    m = _SPEAKER_LINE.match(line.strip())
    if not m:
        return None, None
    speaker = _norm_speaker(m.group("speaker"))
    quote = _clean_quote(m.group("quote"))
    if not quote or is_ocr_garbage(quote):
        return None, None
    if _BRAND_ONLY.match(speaker):
        return None, None
    return speaker, quote


def is_quality_dialogue(text: str, *, has_speaker: bool = False) -> bool:
    """Stricter gate for anonymous OCR lines; labeled speaker lines get a lower bar."""
    if is_ocr_garbage(text, allow_short=has_speaker):
        return False
    t = (text or "").strip()
    words = re.findall(r"[A-Za-z']{3,}", t)
    if has_speaker:
        return len(words) >= 2
    if len(words) < 4:
        return False
    letters = sum(ch.isalpha() for ch in t)
    if letters / max(len(t), 1) < 0.62:
        return False
    vowels = sum(1 for ch in t.lower() if ch in "aeiou")
    if vowels / max(letters, 1) < 0.22:
        return False
    if not re.search(r"[.!?'\"]", t) and len(words) < 6:
        return False
    return True


def _infer_speaker(text: str, current: str) -> str:
    if current != "—":
        return current
    tl = text.lower()
    if "dispatch" in tl or "bathroom" in tl or "sergeant" in tl or "lieutenant" in tl:
        return "Squatter (phone)"
    if ("property" in tl and "illegal" in tl) or "ministry" in tl:
        return "Squatter"
    if any(k in tl for k in ("ungodly", "devil", "satanic", "throne", "lock me")):
        return "Squatter"
    if "escalate" in tl or "disturbance" in tl or "obviously" in tl:
        return "Officer"
    if "satanic" in tl or "turn that off" in tl:
        return "Squatter"
    if "touch" in tl and "anything" in tl:
        return "Squatter Hunters"
    if "let him know" in tl or "other line" in tl:
        return "Dispatch"
    return "—"


def _word_looks_english(word: str) -> bool:
    w = re.sub(r"\W", "", word)
    if len(w) < 3:
        return False
    if sum(ch.isalpha() for ch in w) / max(len(w), 1) < 0.85:
        return False
    if not re.search(r"[aeiou]", w.lower()):
        return False
    if re.search(r"[bcdfghjklmnpqrstvwxyz]{4,}", w.lower()):
        return False
    return True


def _looks_like_real_sentence(text: str, *, strict: bool = False) -> bool:
    words = text.split()
    if len(words) < 4:
        return False
    english = sum(1 for w in words if _word_looks_english(w))
    ratio = 0.75 if strict else 0.65
    return english >= max(4, int(len(words) * ratio))


def filter_dialogue_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        speaker = _infer_speaker(str(row.get("text") or ""), str(row.get("speaker") or "—"))
        has_speaker = speaker != "—"
        text = str(row.get("text") or "")
        if not is_quality_dialogue(text, has_speaker=has_speaker):
            continue
        if speaker == "—":
            if not re.match(r'^[\w"\']', text):
                continue
            if not _looks_like_real_sentence(text, strict=True):
                continue
        out.append({**row, "speaker": speaker})
    return out


def extract_dialogue_from_text(text: str) -> list[dict[str, str]]:
    """Split OCR or agent text into speaker + quote pairs."""
    if is_excluded_overlay(text):
        return []

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []

    rows: list[dict[str, str]] = []
    pending_speaker: str | None = None

    for line in lines:
        if is_excluded_overlay(line) or _BRAND_ONLY.match(line):
            pending_speaker = None
            continue

        speaker, quote = parse_speaker_line(line)
        if quote:
            rows.append({"speaker": speaker or pending_speaker or "—", "text": quote})
            pending_speaker = None
            continue

        only = _SPEAKER_ONLY.match(line)
        if only:
            pending_speaker = _norm_speaker(only.group("speaker"))
            continue

        if is_ocr_garbage(line):
            continue
        if not _looks_like_dialogue(line):
            continue

        rows.append({"speaker": pending_speaker or "—", "text": _clean_quote(line)})
        pending_speaker = None

    if rows:
        return rows

    # Whole block may be one caption line without embedded newlines.
    if is_ocr_garbage(text):
        return rows
    speaker, quote = parse_speaker_line(text.replace("\n", " "))
    if quote:
        return [{"speaker": speaker or "—", "text": quote}]
    if _looks_like_dialogue(text):
        return [{"speaker": "—", "text": _clean_quote(text.replace("\n", " "))}]
    return rows


def _row_start_seconds(row: dict[str, Any]) -> float:
    for key in ("start_seconds", "time_seconds"):
        val = row.get(key)
        if val is not None:
            return float(val)
    return 0.0


def build_dialogue_rows_from_detections(
    detections: list[dict[str, Any]],
    *,
    embedded_tc_fn: Any | None = None,
) -> list[dict[str, Any]]:
    """Turn raw OCR or condensed detection rows into forced-narrative dialogue rows."""
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()

    for det in detections:
        start = _row_start_seconds(det)
        embedded_tc = None
        if embedded_tc_fn is not None:
            embedded_tc = embedded_tc_fn(start)
        start_file_tc = det.get("start_timecode")

        for item in extract_dialogue_from_text(str(det.get("text") or "")):
            speaker = item["speaker"]
            text = item["text"]
            key = (speaker, text.lower(), int(round(start)))
            if key in seen:
                continue
            seen.add(key)
            row: dict[str, Any] = {
                "embedded_tc": embedded_tc,
                "start_timecode": start_file_tc,
                "end_timecode": det.get("end_timecode"),
                "start_seconds": start,
                "end_seconds": det.get("end_seconds"),
                "speaker": speaker,
                "text": text,
            }
            out.append(row)

    out.sort(key=lambda r: float(r.get("start_seconds") or 0))
    return filter_dialogue_rows(out)


def build_dialogue_rows_from_analysis(
    analysis: dict[str, Any],
    *,
    embedded_tc_fn: Any | None = None,
) -> list[dict[str, Any]]:
    detections: list[dict[str, Any]] = []
    for frame in analysis.get("frames") or []:
        start = _row_start_seconds(frame)
        for item in frame_on_screen_items(frame):
            if str(item.get("text_type") or "") != "subtitle":
                continue
            detections.append(
                {
                    "start_seconds": start,
                    "end_seconds": frame.get("end_seconds", start),
                    "start_timecode": frame.get("start_timecode"),
                    "end_timecode": frame.get("end_timecode"),
                    "text": item.get("text"),
                }
            )
    return build_dialogue_rows_from_detections(detections, embedded_tc_fn=embedded_tc_fn)


def _embedded_tc_from_probe(input_path: str) -> tuple[Any | None, dict[str, Any] | None]:
    try:
        from timecode import Timecode
    except ImportError:
        return None, None

    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", input_path],
        text=True,
    )
    probe = json.loads(out)
    tmcd_tc: str | None = None
    fps = "29.97"
    for stream in probe.get("streams") or []:
        if stream.get("codec_type") == "video":
            fps = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or fps
        if stream.get("codec_tag_string") == "tmcd":
            tc = (stream.get("tags") or {}).get("timecode")
            if tc:
                tmcd_tc = str(tc)
    if not tmcd_tc:
        for stream in probe.get("streams") or []:
            tc = (stream.get("tags") or {}).get("timecode")
            if tc and stream.get("codec_type") == "video":
                tmcd_tc = str(tc)
                break
    if not tmcd_tc:
        return None, None

    if isinstance(fps, str) and "/" in fps:
        num, den = fps.split("/", 1)
        rate = float(num) / float(den)
    else:
        rate = float(fps)

    base = Timecode(str(fps), tmcd_tc)
    meta = {"timecode": tmcd_tc, "fps": fps, "source": "tmcd"}

    def at_seconds(seconds: float) -> str:
        return str(base + int(round(seconds * rate)))

    return at_seconds, meta


def render_forced_narrative_markdown(
    title: str,
    meta: dict[str, Any],
    rows: list[dict[str, Any]],
) -> str:
    lines = [
        f"# {title}",
        "",
        f"- Source: `{meta.get('input_path')}`",
    ]
    if meta.get("embedded_timecode"):
        emb = meta["embedded_timecode"]
        lines.append(
            f"- **Embedded TC:** `{emb.get('timecode')}` ({emb.get('source', 'tmcd')}, {emb.get('fps')})"
        )
    if meta.get("analysis_path"):
        lines.append(f"- Analysis: `{meta.get('analysis_path')}`")
    if meta.get("onscreen_json_path"):
        lines.append(f"- OCR source: `{meta.get('onscreen_json_path')}`")
    lines.extend(
        [
            f"- Dialogue lines: {len(rows)}",
            "",
            "### Notable dialogue captions",
            "",
            "| Embedded TC | Speaker / context | Text (OCR) |",
            "| --- | --- | --- |",
        ]
    )
    for row in rows:
        tc = row.get("embedded_tc") or row.get("start_timecode") or "—"
        speaker = str(row.get("speaker") or "—").replace("|", "\\|")
        text = str(row.get("text") or "").replace("|", "\\|")
        lines.append(f"| {tc} | {speaker} | {text} |")
    if not rows:
        lines.append("| — | — | _No burned-in dialogue detected_ |")
    lines.append("")
    return "\n".join(lines)


def write_forced_narrative_report_files(
    stem: str,
    rows: list[dict[str, Any]],
    meta: dict[str, Any],
    *,
    title: str | None = None,
) -> list[Path]:
    out_dir = generated_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"{ts}_{random.randint(1000, 9999)}"
    json_path = out_dir / f"{stem}_forced_narrative_{suffix}.json"
    md_path = out_dir / f"{stem}_forced_narrative_{suffix}.md"
    csv_path = out_dir / f"{stem}_forced_narrative_{suffix}.csv"

    report_title = title or f"Forced narrative report: {meta.get('input_name', stem)}"
    payload = {**meta, "report_type": "forced_narrative", "rows": rows, "row_count": len(rows)}
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(render_forced_narrative_markdown(report_title, meta, rows), encoding="utf-8")

    columns = [
        "embedded_tc",
        "speaker",
        "text",
        "start_timecode",
        "end_timecode",
        "start_seconds",
        "end_seconds",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return [md_path, json_path, csv_path]

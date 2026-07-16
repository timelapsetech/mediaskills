---
name: captions-compliance
description: Broadcast caption compliance — validate and format SRT, export CEA-608 SCC and SMPTE-TT, flag busy-zone collisions, and transcribe speech to captions. Use when delivering FCC-aligned captions or handoff to linear/broadcast workflows.
license: MIT
compatibility: Requires Python 3.11+. `to-captions-pipeline.py` needs ffmpeg and faster-whisper (via `uv run`). Run scripts via `uv run`.
metadata:
  mediaskills-category: captions
  mediaskills-binaries: ffmpeg
---

# Captions Compliance

Validate, normalize, and export captions for broadcast and streaming delivery. Scripts follow **FCC-oriented readability heuristics** (line length, duration, overlap) and produce **CEA-608 SCC** (Scenarist V1.0) and **SMPTE-TT / TTML** for downstream systems.

## When to use

- **This skill** — compliance checks, SRT cleanup, SCC/SMPTE-TT export, busy-zone review, speech → SRT pipeline.
- **`timecode`** — frame-accurate timecode math when aligning captions to 29.97/30fps sequences.
- **`subtitles`** — burn-in, shift timing, or convert between subtitle formats after you have a compliant SRT.

## Broadcast context

### FCC (U.S. closed captioning)

The FCC requires accurate, synchronous, and readable captions for most television and IP-delivered video. Practical heuristics used here:

| Rule | Typical target | Script |
| --- | --- | --- |
| Characters per line | ≤ 32 (608) / ≤ 42 (reading comfort) | `rules.py`, `validate.py`, `format.py` |
| Lines on screen | ≤ 2 | `rules.py`, `validate.py` |
| On-screen duration | ~1–7 seconds | `rules.py`, `validate.py` |
| Reading speed | ~15–20 chars/sec | `rules.py` |
| Safe area | Title-safe (~10% margin) | `rules.py`, `apply-busy-zones.py` |

These are **guidelines**, not legal certification. Always verify against your distributor's spec (e.g. Netflix, PBS, local station).

### CEA-608 / Scenarist SCC

- **SCC** (Scenarist Closed Caption V1.0) encodes **CEA-608** line-21 captions as hex word pairs with odd parity.
- Pop-on style: load to non-displayed memory (RCL/ENM), position with PAC codes, display (EOC), clear (EDM).
- Character set is limited to basic North American ASCII; unsupported glyphs are replaced.
- `to-scc.py` places captions on rows 14–15 (bottom of the 15-row 608 grid).

### SMPTE-TT (TTML)

- **SMPTE ST 2052** / TTML is the common interchange for file-based and OTT caption delivery.
- `to-smpte-tt.py` emits a minimal TTML document with `<p begin="…" end="…">` cues.
- Timestamps use VTT-style `HH:MM:SS.mmm` (comma in SRT is normalized).

## Gotchas

- **608 vs 708** — SCC export is **CEA-608** only. CEA-708 (DTVCC) requires a different encoder.
- **29.97 SCC timebase** — SCC output uses a 30-frame grid (non-drop) common in Scenarist files; verify against your NLE's import settings.
- **Overlap detection** — `validate.py` flags overlapping cues; fix timing before SCC export.
- **Long lines in 608** — `to-scc.py` hard-wraps at 32 characters per row; run `format.py` first for cleaner breaks.
- **Busy lower thirds** — `apply-busy-zones.py` is a heuristic flagger, not vision-based detection.
- **Whisper accuracy** — `to-captions-pipeline.py` uses the `tiny` model by default; use larger models for accuracy at the cost of speed.

## Recipes

### Check compliance rules

```bash
uv run scripts/rules.py
```

### Validate an SRT file

```bash
uv run scripts/validate.py --input captions.srt
```

### Normalize whitespace and wrap long lines

```bash
uv run scripts/format.py --input captions.srt
```

### Export for broadcast (SCC / CEA-608)

```bash
uv run scripts/to-scc.py --input captions.srt --output deliverable.scc
```

### Export SMPTE-TT / TTML

```bash
uv run scripts/to-smpte-tt.py --input captions.srt --output captions.xml
```

### Flag cues that may hit lower-thirds

```bash
uv run scripts/apply-busy-zones.py --input captions.srt
```

### Speech → SRT (full pipeline)

```bash
uv run scripts/to-captions-pipeline.py --input clip.mp4 --model tiny
```

## Troubleshooting

| Symptom | Cause | Action |
| --- | --- | --- |
| `valid: false` with overlaps | Cues share time ranges | Edit timing or re-run transcription |
| SCC import fails in NLE | Invalid parity or timecode | Re-export; check `validate_scc` errors in stderr |
| `?` characters in SCC | Unsupported Unicode in source | Replace in SRT before export |
| Empty SCC / no cues | Malformed SRT | Run `validate.py` first |
| `ffmpeg not found` | Missing binary | Install via `install-media-tools` skill |
| Whisper slow or inaccurate | Model size | Try `--model base` or `small` |

## Available scripts

| Script | Op | Purpose |
| --- | --- | --- |
| `scripts/rules.py` | `caption.rules` | FCC-oriented compliance rule set |
| `scripts/validate.py` | `caption.validate` | Timing, overlap, and readability checks |
| `scripts/format.py` | `caption.format` | Normalize and soft-wrap SRT |
| `scripts/to-scc.py` | `caption.to_scc` | SRT → Scenarist SCC V1.0 (CEA-608) |
| `scripts/to-smpte-tt.py` | `caption.to_smpte_tt` | SRT → SMPTE-TT / TTML XML |
| `scripts/apply-busy-zones.py` | `caption.apply_busy_zones` | Flag long/multiline lower-screen cues |
| `scripts/to-captions-pipeline.py` | `caption.to_captions_pipeline` | Media → SRT via faster-whisper |

See [references/BROADCAST_GUIDELINES.md](references/BROADCAST_GUIDELINES.md) for context.

## Acceptance checks (agent must pass before delivery)

1. Contract: exit 0, `ok: true`, every `output_paths` entry exists and is non-empty.
2. Skill gate: run `validate.py` before SCC/SMPTE-TT export; resolve blocking overlaps and timing issues (or document intentional residuals).
3. Spot-check: first/last cues readable; SCC/TTML open in target NLE or viewer when available.
4. Distributor specs still override heuristics — never claim legal certification from this skill alone.
5. On failure: fix or escalate; do not export SCC from invalid timing.

## Do not use for

- Legal caption certification
- Burning subtitles (use `subtitles/burn.py`)
- General video editing (use `video-transformation`)

## Related skills

- `timecode` — timecode conversion for frame-accurate alignment
- `subtitles` — burn-in, shift, and format conversion
- `install-media-tools` — ffmpeg for the transcription pipeline

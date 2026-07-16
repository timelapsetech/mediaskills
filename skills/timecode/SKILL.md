---
name: timecode
description: SMPTE timecode arithmetic with drop-frame and non-drop-frame support — convert between timecode and seconds, add/subtract offsets, retime between frame rates, convert DF↔NDF, and infer format from strings or ffprobe/MediaInfo metadata. Use when edit decisions are expressed as HH:MM:SS:FF or HH:MM:SS;FF or when aligning clips at NTSC rates.
license: MIT
compatibility: Requires Python 3.11+. Scripts use the `timecode` PyPI package (eoyilmaz/timecode). `extract.py` also needs ffprobe on PATH. Run scripts via `uv run`.
metadata:
  mediaskills-category: timecode
  mediaskills-binaries: ffprobe
---

# Timecode

Frame-accurate SMPTE timecode math using the [eoyilmaz/timecode](https://github.com/eoyilmaz/timecode) library. Supports **drop-frame (DF)** and **non-drop-frame (NDF)** counting, DF↔NDF conversion, cross-fps retiming, and format detection from delimiters and metadata.

## When to use

- **This skill** — timecode ↔ seconds, offsets, fps conversion, DF/NDF conversion, format detection, read file timecode tags.
- **`video-transformation`** — once you have seconds-based trim points from timecode math.
- **`inspect`** — container duration and stream frame rates before assuming fps.

## Drop-frame vs non-drop-frame

| Signal | Meaning |
| --- | --- |
| `HH:MM:SS;FF` (semicolon) | Drop-frame display — standard for 29.97 / 59.94 NTSC |
| `HH:MM:SS:FF` (colon) | Non-drop-frame display |
| NTSC nominal rate (29.97, 59.94, `30000/1001`) | Library defaults to **drop-frame** unless `--non-drop-frame` |
| MediaInfo `Time code settings` | `Drop frame` or `Non drop frame` |

Drop-frame timecode skips frame numbers 00 and 01 at the start of each minute **except** every tenth minute, so the counter stays aligned with wall-clock time at 29.97 fps. At `01:00:00;00` DF, the NDF equivalent at the same wall-clock is roughly `00:59:56;12` when preserving frame index — use `convert_df.py` with `--preserve realtime` to match wall-clock instead.

## Gotchas

- **Semicolon matters** — do not normalize `;` to `:` before parsing; it changes DF vs NDF meaning.
- **Two “seconds” values** — scripts return `seconds` (linear from frame index), `seconds_system` (video system grid), and `seconds_realtime` (wall clock). For ffmpeg `-ss` on NTSC DF material, prefer `seconds_realtime`.
- **29.97 is not 30** — use `29.97` or `30000/1001`, not rounded `30`, when DF is intended. When mapping **file seconds → embedded TC**, multiply by the exact rational fps from ffprobe (`30000/1001`), not the library's integer `_int_framerate` (30).
- **Embedded start TC** — masters often start at embedded timecodes e.g. `00:58:40;00` with episode at `01:00:00;00`. Run `extract.py` to read the tmcd start; use `calculate.py` or `program-master` to offset segment boundaries.
- **Missing file timecode** — many MP4/H.264 files have no timecode tag; `extract.py` returns `timecode: null` — derive from fps + duration instead.
- **Cross-fps retiming** — default `convert.py` preserves **wall-clock** duration (`--preserve realtime`). Use `--preserve frames` only when you need the same frame index at a new rate.

## Recipes

### Timecode to seconds (29.97 drop-frame)

```bash
uv run scripts/to_seconds.py --timecode 00:01:30;15 --fps 29.97
```

### Seconds to drop-frame timecode

```bash
uv run scripts/from_seconds.py --seconds 90.5 --fps 29.97
```

### Add a 5-second slate (wall-clock)

```bash
uv run scripts/calculate.py --timecode 01:00:00;00 --op add --offset-seconds 5 --fps 29.97
```

### Convert 24fps edit point to 29.97 DF sequence

```bash
uv run scripts/convert.py --timecode 00:10:00:00 --from-fps 24 --to-fps 29.97
```

### Convert drop-frame to non-drop-frame (same wall-clock)

```bash
uv run scripts/convert_df.py --timecode 01:00:00;00 --fps 29.97 --to non-drop-frame
```

### Detect format from a timecode string

```bash
uv run scripts/detect_format.py --timecode 01:00:00;00 --fps 29.97
```

### Analyze ffprobe or MediaInfo JSON

```bash
uv run scripts/analyze_metadata.py --input /path/to/ffprobe.json
```

### Read embedded timecode from a file

```bash
uv run scripts/extract.py --input /path/to/clip.mov
```

### Map file seconds to embedded SMPTE (broadcast master)

After `extract.py` reports e.g. start `00:58:40;00` at `30000/1001`:

```bash
uv run scripts/calculate.py --timecode 00:58:40;00 --op add --offset-seconds 80.013 --fps 30000/1001
```

For full segment manifests with labels, prefer **`program-master`** `label_segments.py` (auto-detects tmcd).

## Troubleshooting

| Symptom | Cause | Action |
| --- | --- | --- |
| Off by ~3.6s per hour | DF treated as NDF (or vice versa) | Check delimiter; run `detect_format.py` |
| Frame count off by 1–2 | 0-based vs 1-based frames | Use `frames` (0-based) from script output |
| `Invalid timecode` | Wrong field count | Use four fields `HH:MM:SS:FF` or `HH:MM:SS;FF` |
| `timecode` null in extract | No tag in file | Use `from_seconds` with known fps |
| 24→29.97 mismatch | Used frame index instead of wall-clock | `convert.py` defaults to `--preserve realtime` |

## Available scripts

| Script | Purpose |
| --- | --- |
| `scripts/info.py` | Supported fps, formats, library reference |
| `scripts/to_seconds.py` | Timecode → seconds + frames |
| `scripts/from_seconds.py` | Seconds → timecode |
| `scripts/calculate.py` | Add/subtract offset (wall-clock) |
| `scripts/convert.py` | Retime timecode between fps values |
| `scripts/convert_df.py` | Convert DF ↔ NDF |
| `scripts/detect_format.py` | Infer DF/NDF from string + fps |
| `scripts/analyze_metadata.py` | Infer format from ffprobe/MediaInfo JSON |
| `scripts/extract.py` | Read timecode tags via ffprobe |

See [references/DF_NDF.md](references/DF_NDF.md) for drop-frame background.

## Acceptance checks (agent must pass before delivery)

1. Contract: exit 0, `ok: true`, and `data.seconds_realtime` / timecode fields present when converting for edits.
2. Spot-check: DF vs NDF matches source (semicolon vs colon); seconds feed into trim and output duration ≈ (end − start).
3. On failure: recalculate; do not trim on guessed seconds.

## Do not use for

- Actual video trimming (convert to seconds, then use `video-transformation`)
- Legal frame-rate standards beyond SMPTE timecode display math

## Related skills

- `video-transformation` — apply trim points in seconds
- `inspect` — probe frame rates and duration

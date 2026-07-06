---
name: inspect
description: Probe, describe, compare, and batch-inspect video, audio, and image files using ffprobe. Use when you need metadata (duration, resolution, codecs, size), want to compare two files before/after processing, or need structured probe data to answer questions about a media file without modifying it.
license: MIT
compatibility: Requires ffprobe on PATH. Scripts are Python 3.11+, run via `uv run` (no separate install step).
metadata:
  mediaskills-category: inspect
  mediaskills-binaries: ffprobe
---

# Inspect

Read-only media inspection. Use this skill when you need **metadata without changing files**.

## When to use

- **This skill** — ffprobe metadata, duration, resolution, batch comparison tables, structured JSON for agent reasoning.
- **`audio` / `image` / `video-transformation`** — when you need to **transform** media (trim, transcode, resize). Run `inspect` first to confirm codecs and duration before destructive operations.
- **Raw ffprobe** — fine for one-off queries, but these scripts return consistent JSON the agent can parse reliably.

## Gotchas

- **Container vs stream duration** — ffprobe `format.duration` is authoritative for most files; individual stream durations can differ when audio/video lengths don't match (bad mux, trailing silence). Prefer `format.duration` for edit boundaries.
- **No video stream** — audio-only files return empty resolution; `resolution.py` reports `width`/`height` as null, not an error.
- **Variable frame rate (VFR)** — `avg_frame_rate` in probe JSON may differ from `r_frame_rate`. For frame-accurate edits, inspect both before assuming CFR.
- **Corrupt or partial files** — `moov atom not found` means an incomplete MP4 (common with interrupted downloads). Re-download or remux; probing cannot recover metadata.
- **Image "video" streams** — some still formats appear as a single-frame video stream; duration may be `N/A` or `0.04` seconds.

## Recipes

### Quick metadata check

```bash
uv run scripts/describe.py --input /path/to/clip.mp4
```

Example result:

```json
{"ok": true, "op": "inspect.describe", "data": {"format": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "12.500000", "size": "1048576", "video": {"codec": "h264", "width": 1920, "height": 1080}, "audio_codecs": ["aac"]}, "output_paths": []}
```

### Full structured probe (for programmatic use)

```bash
uv run scripts/probe.py --input /path/to/clip.mp4
```

Returns complete ffprobe JSON in `data` — all streams, tags, bit rates.

### Compare before/after a transcode

```bash
uv run scripts/compare.py --input-a original.mp4 --input-b transcoded.mp4
```

Check `data.a` vs `data.b` for duration drift, resolution change, or size reduction.

### Batch inventory a folder

```bash
uv run scripts/batch_probe.py --paths clip1.mp4 clip2.mp4 clip3.wav
```

Use `data.rows` for a table. Rows with `error` indicate unreadable paths.

### Answer a specific question (agent workflow)

```bash
uv run scripts/ask.py --input clip.mp4 --question "Does this file have an audio track?"
```

Returns full probe JSON plus your question — the agent reads `data.probe.streams` and answers.

## Troubleshooting

| Error / symptom | Likely cause | Action |
| --- | --- | --- |
| `ffprobe not found` | Binary missing | Run `install-media-tools` doctor/install |
| `Invalid data found when processing input` | Not a media file or corrupt | Verify file type with `file` command |
| `width`/`height` null | Audio-only or subtitle-only | Use `probe.py` to list streams |
| Duration `N/A` | Still image or broken header | Try `ffprobe -show_format` manually |

## Available scripts

| Script | Purpose |
| --- | --- |
| `scripts/probe.py` | Full ffprobe JSON |
| `scripts/describe.py` | Compact human/agent summary |
| `scripts/duration.py` | Duration in seconds |
| `scripts/resolution.py` | Video width × height |
| `scripts/compare.py` | Side-by-side summary of two files |
| `scripts/batch_probe.py` | Table of metadata for many files |
| `scripts/ask.py` | Probe + question for agent reasoning |

## Do not use for

- Modifying or transcoding media (use `audio`, `image`, or `video-transformation`)
- Downloading from URLs (use `download`)
- Generating captions from speech (use `speech-captions`)

## Related skills

- `install-media-tools` — install ffprobe/ffmpeg
- `audio`, `video-transformation`, `image` — processing after inspection

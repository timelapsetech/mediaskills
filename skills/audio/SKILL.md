---
name: audio
description: Extract, convert, trim, concatenate, normalize, fade, resample, and silence-detect audio using ffmpeg. Use when you need to modify audio tracks, change format or sample rate, edit timeline segments, or prepare audio for muxing back onto video.
license: MIT
compatibility: Requires ffmpeg and ffprobe on PATH. Scripts are Python 3.11+, run via `uv run` (no separate install step).
metadata:
  mediaskills-category: audio
  mediaskills-binaries: ffmpeg, ffprobe
---

# Audio

Audio processing with ffmpeg. Use this skill when you need to **change** audio — not just read metadata (use `inspect` for that).

## When to use

- **This skill** — extract audio from video, convert formats, trim/concat timeline edits, loudness normalize, fade, resample, find silence.
- **`inspect`** — read-only metadata before editing (duration, codecs, sample rate). Always probe first when unsure about input format.
- **`video-transformation`** — mux normalized or extracted audio back onto video (`replace_audio.py` and similar ops).
- **Raw ffmpeg** — fine for one-off filter chains, but these scripts return consistent JSON and auto-generate output paths.

## Gotchas

- **Trim with `-c copy`** — `trim.py` stream-copies for speed. Works for WAV and many containers; can fail or produce glitches on MP3/AAC with frame boundaries. Re-encode with ffmpeg manually if copy fails.
- **Concat requires matching codecs** — `concat.py` uses the concat demuxer with `-c copy`. All inputs must share codec, sample rate, and channel layout. Convert/resample first if needed.
- **Normalize outputs WAV** — `loudnorm` writes PCM WAV. Mux back to video with `video-transformation` `replace_audio.py`, or convert with `convert.py`.
- **Fade is fixed 1 s in** — `fade.py` applies `afade=t=in:st=0:d=1` only. Custom fade curves need raw ffmpeg.
- **Silence threshold is fixed** — `silence_detect.py` uses `noise=-30dB:d=0.5`. Pure tones (e.g. test fixtures) may report no silence; real speech/podcast material works best.
- **Extract vs video extract** — `extract.py` strips video (`-vn`) to WAV. For video-specific workflows, check `video-transformation` `extract_audio.py` too.

## Recipes

### Normalize then put audio back on video

1. Run `inspect` on the source to confirm duration and audio codec.
2. Normalize:

```bash
uv run scripts/normalize.py --input clip.mp4
```

3. Mux the normalized WAV onto the original video with `video-transformation` `replace_audio.py`.
4. Optional: specify bitrate/codec on replace for a smaller proxy encode.

### Extract clean audio only

```bash
uv run scripts/extract.py --input clip.mp4 --output dialogue.wav
```

Use `output_path` from JSON for downstream transcription or editing.

### Convert for 48 kHz AAC for delivery

```bash
uv run scripts/resample.py --input master.wav --sample-rate 48000 --output master_48k.wav
uv run scripts/convert.py --input master_48k.wav --format aac --output master.m4a
```

### Trim a segment and join clips

```bash
uv run scripts/trim.py --input intro.wav --start 0 --end 30 --output intro_trim.wav
uv run scripts/trim.py --input outro.wav --start 5 --end 60 --output outro_trim.wav
uv run scripts/concat.py --paths intro_trim.wav outro_trim.wav --output final.wav
```

### Find silence for auto-editing

```bash
uv run scripts/silence_detect.py --input podcast.wav
```

Read `data.silence_starts` / `data.silence_ends` (seconds) to split on pauses or detect dead air.

## Troubleshooting

| Error / symptom | Likely cause | Action |
| --- | --- | --- |
| `ffmpeg not found` | Binary missing | Run `install-media-tools` doctor/install |
| Concat fails / corrupt output | Mismatched codecs or sample rates | Resample/convert inputs to identical format first |
| Trim produces empty or tiny file | Start ≥ end or beyond duration | Check duration with `inspect`; verify `--start` / `--end` |
| `-c copy` trim fails | Codec doesn't support arbitrary cut points | Re-encode: `ffmpeg -ss START -to END -i IN -c:a pcm_s16le OUT.wav` |
| Normalize sounds wrong | Already heavily compressed source | Inspect peaks; consider manual `loudnorm` params via raw ffmpeg |
| No silence regions detected | Threshold too strict or continuous tone | Expected on sine test tones; try real speech audio |

## Available scripts

| Script | Purpose | Key flags |
| --- | --- | --- |
| `scripts/probe.py` | Full ffprobe JSON for an audio file | `--input` |
| `scripts/extract.py` | Strip video, write WAV | `--input`, `--output` |
| `scripts/convert.py` | Change format (mp3, aac, flac, …) | `--input`, `--format`, `--output` |
| `scripts/trim.py` | Cut a time range | `--input`, `--start`, `--end`, `--output` |
| `scripts/concat.py` | Join multiple files | `--paths`, `--output` |
| `scripts/normalize.py` | EBU-style loudness normalize | `--input`, `--output` |
| `scripts/fade.py` | 1-second fade-in | `--input`, `--output` |
| `scripts/resample.py` | Change sample rate | `--input`, `--sample-rate`, `--output` |
| `scripts/silence_detect.py` | List silence regions | `--input` |

Outputs default to `.mediaskills/generated/` unless `--output` is set.

## Do not use for

- Probing media metadata (use `inspect`)
- Video transforms (use `video-transformation`)
- Speech-to-text (use `speech-captions`)

## Related skills

- `install-media-tools` — install ffmpeg/ffprobe
- `inspect` — read-only metadata before processing
- `video-transformation` — mux/replace audio on video

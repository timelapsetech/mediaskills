---
name: video-transformation
description: Transform video with ffmpeg — trim, concatenate, transcode, scale, proxy, extract frames and audio, create GIFs, replace audio tracks, and other stream manipulation. Use when changing video files through editing cuts, codec conversion, resizing, muxing, or derivative exports.
license: MIT
compatibility: Requires ffmpeg and ffprobe on PATH. Scripts are Python 3.11+, run via `uv run` (no separate install step).
metadata:
  mediaskills-category: video
  mediaskills-binaries: ffmpeg, ffprobe
---

# Video Transformation

ffmpeg-based video operations: editorial cuts, transcoding, scaling, muxing, and derivative exports. Outputs land in the **workspace root** `.mediaskills/generated/` unless you pass `--output`. Override base path with `$MEDIASKILLS_DATA_DIR`.

## When to use

- **This skill** — trim, concat, transcode, scale, proxy, frame/audio extraction, GIF, replace audio, and similar ffmpeg transformations.
- **`inspect`** — read metadata first (duration, codecs) before choosing trim boundaries or transcode settings.
- **`timecode`** — frame-accurate timecode math when working in HH:MM:SS:FF or HH:MM:SS;FF instead of seconds.
- **`audio`** — normalize or process audio before `replace_audio.py`.
- **`subtitles`** — mux soft subtitles without burning; use this skill when the container needs re-wrapping.

## Choosing an operation

| Goal | Script |
| --- | --- |
| Cut a time range | `trim.py` |
| Pull several ranges as separate files | `trim_multi.py` |
| Join clips end-to-end | `concat.py` |
| Change codec, bitrate, or container | `transcode.py` |
| Resize for delivery or downstream processing | `scale.py` |
| Fast low-res copy for review | `proxy.py` |
| Still at a timestamp | `extract_frame.py` |
| Audio-only export | `extract_audio.py` |
| Short animated preview | `to_gif.py` |
| Swap in external audio (e.g. after loudnorm) | `replace_audio.py` |

Transcoding and editorial trims share the same toolchain — probe first, then pick copy vs re-encode based on whether you need frame-accurate cuts or a new codec.

## Gotchas

- **Stream copy vs re-encode** — `trim.py` and `trim_multi.py` try `-c copy` first (fast, lossless cuts on keyframes). If that fails, they fall back to H.264/AAC re-encode. Cuts may snap to nearest keyframe when copying.
- **Concat codec mismatch** — `concat.py` also tries copy first; mixed codecs/resolutions trigger a re-encode fallback.
- **Replace audio length** — `-shortest` ends when the shorter of video or audio ends. Trim or pad audio first if lengths must match exactly.
- **GIF size** — `to_gif.py` caps width at 480px and 10 fps; long clips produce large files. Trim first for previews.
- **Transcode codec strings** — pass `codec` and `bitrate` separately (`--codec libx264 --bitrate 1M`). The script normalizes common agent mistakes like `h264@1M`.
- **Transcode vs replace audio** — `transcode.py` re-encodes streams from a single input. Use `replace_audio.py` when audio comes from a separate file.

## Recipes

### Trim a section

```bash
uv run scripts/trim.py --input /path/to/clip.mp4 --start 5 --end 12.5
```

Use `output_path` from the JSON result for the next step.

### Cut several segments then join

1. `trim_multi.py` with segments → returns `segment_paths` (real files like `clip_segment_0.mp4`).
2. `concat.py --paths` with **those exact paths** from step 1. Never invent filenames.
3. Report the concat `output_path` from the result.

```bash
uv run scripts/trim_multi.py --input clip.mp4 --segment 0:3 --segment 5:8
uv run scripts/concat.py --paths .mediaskills/generated/clip_segment_0.mp4 .mediaskills/generated/clip_segment_1.mp4
```

### Transcode for delivery

```bash
uv run scripts/transcode.py --input master.mov --codec libx264 --bitrate 5M --output deliverable.mp4
```

### Replace audio track

When video and audio live in different files (e.g. after audio normalization):

```bash
uv run scripts/replace_audio.py --input video.mp4 --audio normalized.wav --copy-video
```

Do **not** use `transcode.py` for external audio — it only re-encodes a single file's streams.

### Trim then transcode

1. `trim.py` → note `output_path`.
2. `transcode.py --input <trim output> --codec libx264 --bitrate 2M`.

### Low-res proxy for review

```bash
uv run scripts/proxy.py --input master.mp4
```

640px wide, ultrafast x264, CRF 28.

## Troubleshooting

| Error / symptom | Likely cause | Action |
| --- | --- | --- |
| `ffmpeg not found` | Binary missing | Run `install-media-tools` |
| Trim has frozen frame at start | Cut between keyframes with stream copy | Re-run with `--reencode` |
| Concat fails then succeeds | Codec/resolution mismatch | Fallback re-encode ran; check quality |
| Empty GIF | Very short or corrupt input | Probe with `inspect` first |
| Replace audio too short | Audio shorter than video | `-shortest` trimmed video; extend audio |
| Transcode larger than source | High bitrate or lossless settings | Lower `--bitrate` or raise `--crf` |

## Available scripts

| Script | Purpose |
| --- | --- |
| `scripts/trim.py` | Cut a single time range |
| `scripts/trim_multi.py` | Extract multiple ranges to separate files |
| `scripts/concat.py` | Join files end-to-end |
| `scripts/transcode.py` | Re-encode video + its own audio |
| `scripts/replace_audio.py` | Mux video from one file with audio from another |
| `scripts/scale.py` | Resize (`--height -2` keeps aspect) |
| `scripts/proxy.py` | Fast low-res review copy |
| `scripts/extract_frame.py` | Still image at timestamp |
| `scripts/extract_audio.py` | Audio track to MP3 |
| `scripts/to_gif.py` | Short animated GIF |

## Do not use for

- Read-only metadata (use `inspect`)
- Audio-only pipelines (use `audio`)
- Caption/subtitle authoring (use `speech-captions` / `subtitles`)

## Related skills

- `inspect` — probe before transforming
- `timecode` — timecode conversions
- `audio` — process audio before muxing
- `subtitles` — soft-subtitle mux workflows
- `install-media-tools` — install ffmpeg

---
name: subtitles
description: Convert, shift, extract, and burn subtitle files (SRT/WebVTT). Use when you already have caption text or embedded subtitle tracks and need format conversion, sync adjustment, extraction from containers, or hardcoded captions on video.
license: MIT
compatibility: Requires ffmpeg and ffprobe on PATH. `burn.py` also needs Pillow (installed via `uv run`). Scripts are Python 3.11+.
metadata:
  mediaskills-category: captions
  mediaskills-binaries: ffmpeg, ffprobe
---

# Subtitles

Subtitle file operations and burn-in. Use this skill when you need to **work with caption files or embedded tracks** — not automatic speech recognition (use `speech-captions` for that).

## When to use

- **This skill** — SRT ↔ VTT conversion, sync offset, extract `0:s:0` subtitle stream, burn SRT into video.
- **`speech-captions`** — generate captions from spoken audio when no subtitle track exists.
- **`video-transformation`** — mux soft subtitles into a container, transcode, or re-wrap streams without burning.
- **`inspect`** — list streams and confirm a subtitle track exists before `extract.py`.

## Gotchas

- **Extract maps first subtitle stream only** — `extract.py` uses `-map 0:s:0`. Multi-language containers may need manual ffmpeg maps for other indices.
- **Burn re-encodes video** — `burn.py` overlays PNG captions and outputs H.264 (`libx264`, CRF 20). Audio is stream-copied when present. Expect generation time to scale with cue count.
- **Burn expects SRT** — WebVTT must be converted with `convert.py` first. VTT timing and styling tags are not preserved on burn.
- **Shift clamps to zero** — negative offsets clamp cue starts at `0.0`; very negative shifts can collapse short cues to a 0.1 s minimum duration.
- **No libass dependency** — burn uses Pillow text rendering with a simple bottom-centered box. Complex ASS styling (fonts, positioning, karaoke) is not supported.
- **SRT vs VTT on shift** — output format follows input extension (`.srt` or `.vtt`). Convert first if you need a different target format.

## Recipes

### Convert SRT to WebVTT for HTML5 players

```bash
uv run scripts/convert.py --input captions.srt --format vtt --output captions.vtt
```

### Fix captions that start 1.5 seconds early

```bash
uv run scripts/shift.py --input captions.srt --offset-seconds 1.5
```

Use negative values if captions are late relative to dialogue.

### Extract embedded subtitles from MKV/MP4

```bash
uv run scripts/extract.py --input movie.mkv --output extracted.srt
```

Fails clearly when no subtitle stream exists — fall back to `speech-captions transcribe`.

### Hardcode captions for social delivery

```bash
uv run scripts/burn.py --input clip.mp4 --subtitle captions.srt --output clip_subbed.mp4
```

Each cue becomes a timed full-frame PNG overlay; plan for longer encodes on caption-heavy videos.

### Typical workflow after ASR

1. `speech-captions transcribe` → SRT
2. `subtitles shift` — fix sync
3. `subtitles convert` — VTT for web, keep SRT for editors
4. `subtitles burn` — optional deliverable without player subtitle support

## Troubleshooting

| Error / symptom | Likely cause | Action |
| --- | --- | --- |
| `No embedded subtitle track found` | Container has no `s:` stream | Use `speech-captions transcribe` or mux subs first |
| `No subtitle cues found` | Empty or malformed file | Validate SRT/VTT structure; re-export from editor |
| `ffmpeg failed` on burn | Overlay filter error, corrupt video | Probe with `inspect`; test shorter clip |
| Wrong language track extracted | Not stream `0:s:0` | Extract manually with ffmpeg `-map 0:s:N` |
| Blurry burned text | Small output resolution | Use higher-res source; burn scales font to frame height |

## Available scripts

| Script | Purpose |
| --- | --- |
| `scripts/convert.py` | SRT ↔ WebVTT |
| `scripts/shift.py` | Offset all cue timings |
| `scripts/extract.py` | Pull embedded subtitle track to SRT |
| `scripts/burn.py` | Hardcode SRT captions into video |

## Do not use for

- Automatic speech recognition (use `speech-captions`)
- FCC/SCC compliance validation (use `captions-compliance`)
- On-screen text / graphics QC (use `vision-analysis`)

## Related skills

- `speech-captions` — automatic transcription to SRT/VTT
- `video-transformation` — trim, transcode, mux without burning
- `inspect` — stream and duration metadata
- `install-media-tools` — install ffmpeg/ffprobe

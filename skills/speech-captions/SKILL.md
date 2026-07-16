---
name: speech-captions
description: Transcribe speech to timed captions with faster-whisper, detect spoken language, and build SRT/VTT from text or segments. Use when you need automatic captions from audio/video, language detection before transcription, or subtitle files from transcript JSON.
license: MIT
compatibility: Requires ffmpeg on PATH. Transcription scripts need Python 3.11+ with faster-whisper (installed automatically via `uv run`). CPU-friendly `tiny` model is the default.
metadata:
  mediaskills-category: captions
  mediaskills-binaries: ffmpeg
---

# Speech Captions

Automatic speech-to-text and caption file generation. Use this skill when you need **spoken content turned into subtitles** — not when muxing or burning captions (see `subtitles`).

## When to use

- **This skill** — transcribe dialogue, detect language, convert transcript text/segments to SRT or WebVTT.
- **`subtitles`** — convert/shift/extract/burn existing subtitle files after you have captions.
- **`audio`** — extract or normalize audio before transcription when the source is noisy or the wrong sample rate.
- **`inspect`** — confirm duration, audio codec, and that an audio stream exists before running whisper.

## Gotchas

- **First run downloads a model** — `faster-whisper` caches models under `~/.cache/huggingface`. `tiny` is fast but less accurate; use `small` or `medium` for production dialogue.
- **CPU-only by default** — scripts use `device="cpu"` and `compute_type="int8"`. GPU setups can edit the script or run whisper elsewhere; these CLIs target portable agent use.
- **Plain text → cues is approximate** — `to-srt.py` / `to-vtt.py` split on sentence boundaries and spread cues evenly. For accurate timing, use `transcribe.py` or pass `--segments-json` from a real ASR pass.
- **Music and silence** — whisper may hallucinate text on instrumentals or long silence. Inspect output; trim leading/trailing silence with `audio` first if needed.
- **Language auto-detection** — `detect-language.py` samples the first 60 seconds. Short clips or multilingual content may misreport; pass an explicit language to whisper in a custom workflow if you know the locale.
- **Video inputs** — transcription extracts mono 16 kHz WAV via ffmpeg. Very long files take proportionally longer; there is no chunking in the default transcribe script.

## Recipes

### Transcribe a clip to SRT + JSON

```bash
uv run scripts/transcribe.py --input interview.mp4 --model tiny
```

Returns `data.srt_path`, `data.json_path`, full `text`, and per-segment timings in `data.segments`.

### Detect language before choosing a model

```bash
uv run scripts/detect-language.py --input interview.mp4
```

Check `data.language` and `data.probability` before committing to a larger whisper model.

### Build SRT from transcript text (no ASR)

```bash
uv run scripts/to-srt.py --text "Hello world. This is a test." --duration 6 --output captions.srt
```

### Build VTT from transcribe JSON

```bash
uv run scripts/to-vtt.py --segments-json interview_transcript.json --output captions.vtt
```

The JSON file can be the `json_path` from `transcribe.py` (it includes a top-level `segments` array).

### End-to-end caption pipeline

1. `inspect` — confirm audio stream and duration.
2. `speech-captions transcribe` — produce SRT + JSON.
3. `subtitles shift` — fix sync offset if captions lead/lag video.
4. `subtitles burn` — hardcode for players without subtitle support.

## Troubleshooting

| Error / symptom | Likely cause | Action |
| --- | --- | --- |
| `ffmpeg not found` | Binary missing | Run `install-media-tools` doctor/install |
| Empty or nonsense transcript | Music-only, very quiet audio, wrong language | Normalize/extract audio; try larger model |
| `faster_whisper` import error | uv deps not installed | Run via `uv run scripts/...` not plain `python3` |
| Cues too short/long from `--text` | Heuristic timing | Pass `--duration` or use real segments JSON |
| Slow first transcription | Model download | Subsequent runs reuse cached weights |

## Available scripts

| Script | Purpose |
| --- | --- |
| `scripts/transcribe.py` | ASR to SRT + JSON segments |
| `scripts/detect-language.py` | Spoken language detection |
| `scripts/to-srt.py` | Text or segments → SRT |
| `scripts/to-vtt.py` | Text or segments → WebVTT |

## Acceptance checks (agent must pass before delivery)

1. Contract: exit 0, `ok: true`, SRT/JSON paths exist and are non-empty.
2. Skill gate: hand off to `captions-compliance` `validate.py` before broadcast export.
3. Spot-check: read first/last cues; language matches request; duration coverage roughly matches source audio (not a 2-second stub on a long file).
4. ASR is imperfect — never claim verbatim accuracy without human/agent review of critical lines.
5. On failure: re-transcribe with a clearer extract or escalate; do not deliver empty SRT.

## Do not use for

- Burning subtitles into video (use `subtitles/burn.py`)
- Broadcast SCC/SMPTE-TT export (use `captions-compliance`)
- Video or audio transforms (use `video-transformation` / `audio`)

## Related skills

- `subtitles` — format conversion, timing shift, extract embedded tracks, burn-in
- `audio` — extract/normalize audio before ASR
- `inspect` — probe source media before transcription
- `install-media-tools` — install ffmpeg

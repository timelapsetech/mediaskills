---
name: vision-analysis
description: Interval-based and shot-level visual analysis — extract frame sequences, guide agent vision analysis of stills, classified on-screen text, and QC-style reports. Use for burned-in subtitles, graphics, title cards, and timecoded text inventories. Does not bundle a vision model; the agent analyzes images with its own capabilities.
license: MIT
compatibility: Requires Python 3.11+, ffmpeg/ffprobe. compile_report.py also needs tesseract. No local vision model or Ollama required — frame image analysis is performed by the agent using the skill. Run scripts via `uv run`.
metadata:
  mediaskills-category: vision
  mediaskills-binaries: ffmpeg,ffprobe
---

# Vision Analysis

Interval-based and shot-level visual analysis: frame extraction, **agent-driven** image analysis, and timecoded text reports.

## When to use

- **This skill** — extract frame sequences, inventory on-screen text with timecodes, forced-narrative QC.
- **`shots`** — cut detection and midpoint stills when the unit of analysis is a **shot**.
- **`image`** — `image.ocr` for a single still without a sequence pipeline.
- **`captions-compliance`** — validate separate caption sidecar files (SRT/VTT), not burned-in text.

## Agent vs scripts

| Step | Who | Tool |
| --- | --- | --- |
| Extract frames from video | Script | `extract_interval_frames.py` or `shots` skill |
| **View and analyze frame images** | **Agent** (your vision/multimodal tools) | See [references/AGENT_FRAME_ANALYSIS.md](references/AGENT_FRAME_ANALYSIS.md) |
| Merge agent JSON into analysis doc | Script | `merge_analysis.py` |
| Validate analysis JSON | Script | `validate_analysis.py` |
| Generate reports | Script | `text_on_screen_report.py`, etc. |
| OCR without vision model | Script | `compile_report.py` (tesseract) |

**This skill does not call Ollama, OpenAI, or any local vision server.** If you cannot view images, use the legacy OCR path or tell the user that vision analysis requires an agent with image understanding.

## Text types (`text_type`)

| Value | Meaning |
|-------|---------|
| `title` | Title card / show open / episode title |
| `lower_third` | Name/title bar in the lower third |
| `subtitle` | Burned-in dialogue / forced narrative |
| `locator` | Location/time bugs, network bugs, timecode |
| `graphic` | Charts, maps, scoreboards, graphic packages |
| `background_text` | Text physically in the scene |
| `credit` | End credits / copyright |
| `other` | Anything else |

Reports condense repeated identical text into single rows. Scene-description hallucinations in `on_screen_text` are filtered at report time. Use `--force` to regenerate reports after re-analysis.

## Recipe: interval frames for text / forced narrative

```bash
# 1. Extract 1 frame per second
uv run scripts/extract_interval_frames.py --input program.mp4

# 2. For each batch: get paths, analyze images yourself, write batch JSON
uv run scripts/get_frame_batch.py --manifest-path .mediaskills/generated/program_interval_frames.json --batch-index 0

# 3. After analyzing images in batch 0, merge your JSON
uv run scripts/merge_analysis.py \
  --manifest-path .mediaskills/generated/program_interval_frames.json \
  --frames-json batch0_analysis.json

# 4. Repeat step 2–3 for batch-index 1, 2, ... until all frames analyzed

# 5. Optional validation
uv run scripts/validate_analysis.py --analysis-path .mediaskills/generated/program_frame_analysis_....json

# 6. Reports
uv run scripts/text_on_screen_report.py --analysis-path .mediaskills/generated/program_frame_analysis_....json
uv run scripts/forced_narrative_report.py --analysis-path .mediaskills/generated/program_frame_analysis_....json
```

Read [references/AGENT_FRAME_ANALYSIS.md](references/AGENT_FRAME_ANALYSIS.md) for the exact per-frame JSON schema and classification rules.

## Recipe: shot-based analysis (graphics, title cards)

```bash
# 1–2. From shots skill: detect cuts, extract midpoint frames
# uv run ../shots/scripts/detect.py --input program.mp4
# uv run ../shots/scripts/extract-frames.py --shots-path .mediaskills/generated/program_shots_....json

# 3. Batch + agent-analyze + merge (same loop as above)
uv run scripts/get_frame_batch.py --manifest-path .mediaskills/generated/program_shots_....json --batch-index 0
uv run scripts/merge_analysis.py --manifest-path ... --frames-json batch0_analysis.json

# 4. Graphics reports
uv run scripts/graphics_on_screen_report.py --analysis-path .mediaskills/generated/program_frame_analysis_....json
uv run scripts/extract_title_text.py --analysis-path .mediaskills/generated/program_frame_analysis_....json
```

## Legacy OCR path (no agent vision)

`tesseract` only — no text-type classification:

```bash
uv run scripts/compile_report.py --input program.mp4
```

## Gotchas

- **Agent vision required** for classified on-screen text — scripts extract frames and merge JSON; they do not interpret images.
- **Long programs** — 1s interval on a 1-hour show = 3600 frames; use `--interval 2` or `--max-frames` on extract, or analyze a subset.
- **Incremental merge** — `merge_analysis.py` appends batches; re-run with `--force` to replace all frame entries.
- **Report reuse** — report scripts skip regeneration unless `--force` when a matching report exists.

## Available scripts

| Script | Purpose |
|--------|---------|
| `extract_interval_frames.py` | Still every N seconds → manifest + JPGs |
| `get_frame_batch.py` | Slice of frames from manifest for agent batches |
| `merge_analysis.py` | Merge agent-written frame JSON into analysis doc |
| `validate_analysis.py` | Check analysis JSON before reports |
| `analysis_schema.py` | JSON schema for analysis documents |
| `text_on_screen_report.py` | All text types, timecoded |
| `forced_narrative_report.py` | Burned-in subtitles only |
| `graphics_on_screen_report.py` | Graphics/titles (excludes subtitles) |
| `extract_title_text.py` | Title cards and graphics text |
| `compile_report.py` | Legacy tesseract OCR |
| `prepare_manifest.py` | Legacy interval manifests |
| `list_extractions.py` / `compile_all_reports.py` | Inventory helpers |

## Do not use for

- Built-in vision/LLM calls (agent analyzes frames; scripts merge JSON only)
- Replacing `speech-captions` for dialogue transcription
- Real-time stream analysis

## Related skills

- `shots` — cut detection and midpoint stills
- `image` — single-still OCR
- `video-transformation` — frame extraction at arbitrary timestamps

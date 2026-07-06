---
name: program-master
description: TV program segmentation — detect black+silent break separators, probe boundary frames, and label content segments (including slate-driven labels). Use when finding commercial breaks, naming episodes/parts, or mapping broadcast master structure — not hard cuts inside content.
license: MIT
compatibility: Requires ffmpeg and ffprobe on PATH. Optional tesseract for OCR slate text. Scripts are Python 3.11+, run via `uv run`.
metadata:
  mediaskills-category: video
  mediaskills-binaries: ffmpeg, ffprobe, tesseract
---

# Program Master

TV program segmentation: detect black+silent break separators, probe boundary frames, and label content segments (including slate-driven labels).

## Shots vs program-master

| Question | Use **program-master** | Use **shots** |
| --- | --- | --- |
| What are you finding? | Structural gaps between programs/parts (black + silent breaks) | Hard cuts inside content (camera angle changes, edits) |
| Typical source | TV master with black+silent separators | Any edited video |
| Output unit | Content segments with labels (episode, commercial, slate text) | Shot list with timecodes |
| Detection method | ffmpeg `blackdetect` + `silencedetect` overlap | ffmpeg `select=gt(scene,N)` |

Use **program-master** when the user asks to **label segments**, **identify program structure**, **find commercial breaks**, or **name episodes/parts** in a TV master — especially when breaks are marked by **black video with silence**. Do **not** use shot detection for this; shots find hard cuts inside content, not broadcast separators.

## When to use

- Label TV segments from a broadcast master
- Find commercial breaks or part boundaries
- Name episodes from slate cards before/after black gaps
- QC black levels and silence at program boundaries

## Scripts

| Script | Purpose |
| --- | --- |
| `label_segments.py` | **Primary.** Black+silence detect → probe frame before each gap → OCR slate text → labeled segment manifest |
| `detect_black_silence.py` | Black **and** silent overlap regions only (no frames/labels) |
| `detect_blacks.py` | Black video regions (ffmpeg `blackdetect`) |
| `detect_silence.py` | Silent audio regions (ffmpeg `silencedetect`) |
| `analyze_structure.py` | Legacy: silence-based cuts without labeling |
| `compile.py` | Markdown + JSON report from a labeled manifest |
| `schema.py` | Segment manifest JSON schema |

## Preferred recipe: label TV segments

```bash
uv run scripts/label_segments.py --input /path/to/program.mp4
uv run scripts/compile.py --structure-path .mediaskills/generated/program_labeled_segments_*.json
```

`label_segments.py`:

1. Detects gaps where **black video and silent audio overlap** (default min 0.5s).
2. For each gap, extracts a still **`--probe-offset-seconds` before gap start** (default **1.0s**).
3. Runs **tesseract OCR** on each probe frame (when installed).
4. Classifies each probe as:
   - **`content`** — no slate-like text; labels the **segment ending at the gap** as `content`.
   - **`slate`** — readable title-card text; labels the **segment after the gap** with the extracted text.
5. Writes `*_labeled_segments.json` plus probe JPGs under `.mediaskills/generated/<stem>_segment_probes/`.

Present a table from `compile.py`: index, timecode range, duration, label, label_source.

### Optional: refine slates with agent vision

When tesseract misses stylized slates or misclassifies graphics:

1. Build a frame list from `probes[].frame_path` in the labeled JSON.
2. Use the **vision-analysis** skill: the agent analyzes those stills, or run `image.ocr.py` per frame if vision is unavailable.
3. Re-read title/graphic text; update segment labels in the JSON and re-run `compile.py`.

## Parameters (`label_segments.py` / `detect_black_silence.py`)

| Flag | Default | Meaning |
| --- | --- | --- |
| `--noise` | `-30dB` | Silence threshold for `silencedetect` |
| `--min-duration` | `0.5` | Minimum gap length (seconds) |
| `--pixel-threshold` | `0.10` | Black pixel ratio for `blackdetect` |
| `--min-overlap` | `0.25` | Min seconds black **and** silence must overlap |
| `--probe-offset-seconds` | `1.0` | How far before each gap to grab the boundary still |
| `--fps` | `29.97` | Timecode display fps |

## Segment manifest fields

Each **content** segment may include:

- `label` — `content`, slate text, or `unlabeled`
- `label_source` — `probe_before_gap`, `slate_before_gap`, or `none`
- `segment_type` — `content` or `gap`
- `probe_frame_path` / `slate_text` — evidence for the label
- `start_timecode` / `end_timecode` — SMPTE strings

**Gap** segments (`segment_type: gap`) are the black+silent separators themselves.

## Gotchas

- Broadcast masters without black+silent breaks (e.g. streaming with embedded SCTE markers only) may need different tooling.
- Short flashes of black without matching silence are filtered out by `--min-overlap`.
- OCR quality depends on slate contrast and tesseract language packs.
- `analyze_structure.py` is legacy — prefer `label_segments.py` for TV masters with black gaps.

## Do not use for

- Per-shot creative editing decisions (use `video-transformation` with shot times)
- Automatic transcription or captions

## Related skills

- `image` — `ocr.py` on a single probe still
- `video-transformation` — `extract_frame.py` at a custom offset
- `shots` — hard-cut detection inside a labeled content segment (different axis)
- `timecode` — frame-accurate timecode math

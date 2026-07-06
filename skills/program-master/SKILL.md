---
name: program-master
description: TV program segmentation — detect black+silent break separators, probe boundary frames, and label content segments (including slate-driven labels). Use when finding commercial breaks, naming episodes/parts, or mapping broadcast master structure — not hard cuts inside content.
license: MIT
compatibility: Requires ffmpeg and ffprobe on PATH. Optional tesseract for OCR slate text. Scripts are Python 3.11+, run via `uv run` (`timecode` PyPI package for embedded SMPTE mapping).
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

## Output paths

Manifests, probe JPGs, and compiled reports write to the **workspace root** `.mediaskills/generated/` (not inside this skill folder). Override with `$MEDIASKILLS_DATA_DIR/generated/` when set.

## Scripts

| Script | Purpose |
| --- | --- |
| `label_segments.py` | **Primary.** Black+silence detect → probe frame before each gap → OCR slate text → labeled segment manifest |
| `detect_black_silence.py` | Black **and** silent overlap regions only (no frames/labels) |
| `detect_blacks.py` | Black video regions (ffmpeg `blackdetect`) |
| `detect_silence.py` | Silent audio regions (ffmpeg `silencedetect`) |
| `analyze_structure.py` | Legacy: silence-based cuts without labeling |
| `compile.py` | **Deliverable.** Human-readable Markdown table + structured JSON report |
| `schema.py` | Segment manifest JSON schema |

## Preferred recipe: label TV segments

```bash
uv run scripts/label_segments.py --input /path/to/master.mov
uv run scripts/compile.py --structure-path .mediaskills/generated/*_labeled_segments.json
```

**Always run both steps.** Present the compiled Markdown table to the user and cite the companion `*_program_master_report.json`.

## Agent deliverable format

After `compile.py`, present **all segments** (pre-roll through tail black) in this table — never truncate at episode end:

| # | Type | Start TC | End TC | Duration | Label |
| --- | --- | --- | --- | --- | --- |
| 0 | content | 00:58:40;00 | 00:59:40;00 | 60s | SMPTE leader |
| 1 | gap | 00:59:40;00 | 00:59:45;00 | 5s | black+silent |
| 4 | content | 01:00:00;00 | 01:10:08;00 | 10:08 | Episode Part 1 |
| … | … | … | … | … | … |
| 86 | content | 02:05:32;08 | 02:06:01;02 | 29s | post-program clip 32 |

Rules for the agent:

1. **Timecodes** — use embedded DF SMPTE from the manifest (`start_tc` / `end_tc` in report JSON). Frame-accurate; never file-relative `00:00:00:00` on broadcast masters.
2. **Duration** — human format from `compile.py`: `M:SS` when ≥ 60s, else `Ns` (e.g. `10:08`, `5s`).
3. **Labels** — use `compile.py` display labels. Episode parts, credits OCR summaries, and numbered post-program clips. Refine with **vision-analysis** on probe frames when OCR is thin.
4. **Full coverage** — include every row through the final tail gap; post-credit promos/breaks get `post-program segment N` or `post-program clip N` labels at minimum.
5. **JSON** — the paired `*_program_master_report.json` has the same `rows` array plus `episode` metadata (series, title, TRT, body TC range).

Example outputs ship with the skill run under `.mediaskills/generated/*_program_master.md` and `*_program_master_report.json`. Reference example: `.mediaskills/generated/examples/AEN_SWRS_program_master_example.md` (and `.json`).

1. Detects gaps where **black video and silent audio overlap** (default min 0.5s).
2. For each gap, extracts a still **`--probe-offset-seconds` before gap start** (default **1.0s**).
3. Runs **tesseract OCR** on each probe frame (when installed).
4. Classifies each probe as:
   - **`content`** — no slate-like text; labels the **segment ending at the gap** as `content`.
   - **`slate`** — readable title-card text; labels the **segment after the gap** with the extracted text.
5. Writes `*_labeled_segments.json` plus probe JPGs under `.mediaskills/generated/<stem>_segment_probes/`.
6. When a **tmcd** embedded timecode track is present, maps segment boundaries to **drop-frame SMPTE** (`HH:MM:SS;FF`) using the file's start TC and exact video frame rate (`30000/1001`, not rounded 30).

Present the **full** compiled table (see Agent deliverable format above) — not the raw manifest with OCR dumps.

### Embedded timecode (broadcast masters)

For `.mov` / ProRes masters with a **tmcd** track, `label_segments.py` defaults to `--timecode-mode embedded`:

1. Read start TC from the **tmcd stream** (fallback: container `timecode` tag) via ffprobe.
2. Read exact fps from the video stream (`avg_frame_rate` / `r_frame_rate`, e.g. `30000/1001`).
3. Convert each segment's file-relative seconds to frames: `round(seconds × fps_exact)`.
4. Add that frame offset to the embedded start TC (DF arithmetic via the `timecode` library).

Manifest fields:

- `start_timecode` / `end_timecode` — **embedded** SMPTE (authoritative for edit decisions)
- `start_timecode_file` / `end_timecode_file` — file-relative TC from 00:00:00:00 (for ffmpeg `-ss`)
- `embedded_timecode` — `{ timecode, fps, drop_frame, source, stream_index }`
- `timecode_mode` — `embedded` or `file`

Use **`timecode.extract`** first on unknown masters to confirm start TC and fps before trusting segment labels.

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
| `--fps` | `29.97` | File-relative TC fps when no embedded track (or override) |
| `--timecode-mode` | `embedded` | `embedded` (use tmcd when present) or `file` (00:00:00:00 origin) |

## Segment manifest fields

Each **content** segment may include:

- `label` — `content`, slate text, or `unlabeled`
- `label_source` — `probe_before_gap`, `slate_before_gap`, or `none`
- `segment_type` — `content` or `gap`
- `probe_frame_path` / `slate_text` — evidence for the label
- `start_timecode` / `end_timecode` — embedded SMPTE when `timecode_mode: embedded`
- `start_timecode_file` / `end_timecode_file` — file-origin SMPTE (ffmpeg trim points)

**Gap** segments (`segment_type: gap`) are the black+silent separators themselves.

## Gotchas

- **Do not use 30 fps for 29.97 DF masters** — always use the exact rational from ffprobe (`30000/1001`). Rounding to 30 drifts ~4 seconds per hour and misaligns episode boundaries vs slate TRT.
- **Proxies lack tmcd** — a re-encoded proxy has no embedded TC track; run `label_segments.py` on the **source master** for authoritative SMPTE, or pass `--timecode-mode file` on proxies.
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

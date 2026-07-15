---
name: forced-narrative-exact
description: Generate exhaustive, literal, frame-accurate forced-narrative reports from video masters containing burned-in dialogue subtitles. Use when a user requests a forced-narrative inventory, burned-in subtitle report, exact on-screen dialogue transcription, or start/end SMPTE timecodes for every subtitle, especially when embedded tmcd timecode, multiple program passes, textless duplicates, and exclusive frame boundaries must be handled consistently.
license: MIT
compatibility: Requires Python 3.11+, uv, ffmpeg, ffprobe, and tesseract on PATH. An image-capable agent must approve every cue; scripts only discover candidates and refine frame boundaries. Run scripts via `uv run`.
metadata:
  mediaskills-category: vision
  mediaskills-binaries: ffmpeg, ffprobe, tesseract
---

# Forced Narrative Exact

Produce a complete forced-narrative inventory whose text is literal and whose start/end boundaries are source-frame accurate. Use OCR only to discover candidates; the agent must inspect the pictures and approve every cue.

Prefer this skill over `vision-analysis` when the deliverable is an exhaustive, frame-accurate burned-in dialogue inventory (Markdown/JSON/CSV/SRT) with exclusive-end frame QC. Use `vision-analysis` for broader on-screen text/graphics inventories from interval or shot frames.

## Required reading

Before analyzing frames or publishing a report, read:

- [references/report-contract.md](references/report-contract.md) for inclusion, transcription, timing, and QC rules.
- [references/formats.md](references/formats.md) before creating a seed or override JSON.

## Inputs and dependencies

- Accept a local video readable by `ffmpeg` and `ffprobe`.
- Require `tesseract`; the scripts use `uv run` to provide Python packages.
- Require an image-capable agent for final transcription and visual QC. If image viewing is unavailable, stop after the candidate scan and state that the result is not publication-ready.
- Write outputs beneath `$MEDIASKILLS_DATA_DIR/generated/` when set, otherwise `.mediaskills/generated/` in the current workspace.

## Workflow

### 1. Establish source timing and scope

Probe the video before scanning. Record exact FPS as a fraction, frame count, dimensions, duration, and embedded `tmcd` start. Preserve drop-frame punctuation (`;`).

Identify the program regions in master order. Inspect slates and separators. If a second pass is explicitly textless or is a verified textless duplicate, scan it to confirm absence but do not duplicate cues. Record the pass decision in the seed and final scope.

Do not assume the full file is one program pass. Do not infer forced narrative from audio transcription.

### 2. Run dense candidate discovery

Scan the subtitle band at 2 fps (`--interval 0.5`) over every pass that may contain burned-in dialogue. Use the bottom 30.56% of the picture by default; adjust after viewing representative frames.

```bash
uv run scripts/scan_caption_band.py \
  --input /path/to/master.mp4 \
  --start 80 --end 793 \
  --interval 0.5
```

For a 1280×720 source whose subtitles occupy the same zone as the reference report, use `--crop 0,500,1280,220`.

The scan JSON and retained JPGs are discovery material, not the report. OCR false positives and punctuation errors are expected. OCR can also return no useful text for a real subtitle, especially for a thin, single-line white cue over a bright or textured background, so OCR silence is never evidence that a frame is textless.

### 3. Build the agent-verified seed

Review all scan frames in chronological batches. Inspect frames around every OCR cluster, plus transition frames between clusters. Write one seed cue for each distinct visible subtitle state.

Transcribe directly from the image. Preserve visible speaker labels, brackets, capitalization, punctuation, apostrophes, numerals, and line breaks. Split successive subtitle states even when they form one grammatical sentence. Speaker/context metadata is internal only and must not become a separate Markdown or CSV report column.

Write the seed JSON described in [references/formats.md](references/formats.md). Approximate windows should bracket the full cue with roughly 0.5 seconds of tolerance; they are not final timings.

### 4. Refine every cue to source frames

```bash
uv run scripts/refine_boundaries.py \
  --input /path/to/master.mp4 \
  --seed /path/to/forced_narrative_seed.json
```

The refiner constructs a white-text template from a midpoint frame, scans a padded source-frame window, and selects the contiguous matching run containing the reference frame. It records the first matching frame as `start_frame` and the first nonmatching frame after it as `end_frame_exclusive`.

Treat low-confidence, very short, OCR-thin, or transition-adjacent cues as mandatory visual-review items. Inspect the frame immediately before start, the start frame, the last included frame, and the exclusive end frame. Supply corrections with `--overrides` using the override schema; never widen timings by guesswork.

### 5. Build the four report artifacts

```bash
uv run scripts/build_report.py \
  --refined /path/to/forced_narrative_refined.json \
  --overrides /path/to/forced_narrative_overrides.json
```

This writes stable, paired `.md`, `.json`, `.csv`, and `.srt` artifacts. Embedded source TC is primary in Markdown and JSON. File-relative TC, seconds, and frame numbers remain in JSON/CSV. Markdown and CSV omit a separate speaker/context column; visible labels remain literal cue text. SRT uses file-relative elapsed time.

### 6. Run the completeness backstop

When the master contains a verified, frame-aligned textless duplicate, compare every texted source frame with its aligned textless frame after building the draft report. This is mandatory because it can find real subtitles that OCR never recognized.

Determine the texted-to-textless frame offset separately for every act or snap-in region. Then run:

```bash
uv run scripts/audit_completeness.py \
  --input /path/to/master.mp4 \
  --report /path/to/forced_narrative_report.json \
  --region 1925,11313,36019 \
  --region 11337,20049,36019 \
  --output /path/to/completeness_audit.json \
  --contacts-dir /path/to/completeness_contacts
```

The audit subtracts frames already covered by report cues and retains every remaining difference interval. It samples the first frame, last frame, and every 12 frames within each interval. Inspect every contact sheet; do not collapse a long activity cluster to one maximum-difference representative. A brief blank gap or a visible text change creates a distinct subtitle state even when nearby differences belong to the same scene.

Record every candidate in a review JSON using the schema in [references/formats.md](references/formats.md), then rerun the audit with `--review`. Use `missing_dialogue` for an omitted cue and `subtitle_boundary_residual` for clipped cue frames. Both dispositions block publication: correct the seed/refinement, rebuild the report, and rerun the audit. Delivery requires a final audit with every remaining interval classified as `excluded_non_dialogue_text` or `alignment_artifact` and `publication_ready: true`.

If no verified textless duplicate exists, state that this backstop was unavailable and compensate with full chronological frame review around every discovery cluster and transition; do not invent a textless alignment.

### 7. Validate before delivery

```bash
uv run scripts/validate_report.py \
  --report /path/to/video_forced_narrative_report.json \
  --input /path/to/master.mp4 \
  --completeness-audit /path/to/completeness_audit_reviewed.json
```

Pass `--completeness-audit` whenever a verified textless duplicate exists. Do not deliver when validation reports an error. Also complete the visual gates in the report contract; structural validation cannot prove transcription completeness when a textless backstop is unavailable.

## Mandatory delivery

Present the complete Markdown table, not a sample. State the cue count, source FPS/drop-frame mode, embedded source start, pass scope, and exclusive-end convention. Link the Markdown report and paired JSON, CSV, and SRT.

Never label OCR output as exact until every cue has passed agent transcription review and boundary-frame QC. When a verified textless duplicate exists, also require a reviewed, publication-ready completeness audit.

## Do not use for

- speech-to-text captions from audio (use `speech-captions`)
- sidecar SRT/VTT compliance or format conversion (use `captions-compliance` / `subtitles`)
- broad graphics/title/lower-third inventories without exclusive frame-accurate dialogue delivery (use `vision-analysis`)
- program act/commercial structure (use `program-master`)

Related skills: `inspect`, `program-master`, `timecode`, and `vision-analysis`.

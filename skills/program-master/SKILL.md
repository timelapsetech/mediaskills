---
name: program-master
description: TV program segmentation — detect fade-aware black+silent break separators, preserve frame-accurate fade anchors, label content segments, and generate validated thumbnail-led broadcast segment PDF reports. Use when finding commercial breaks, naming episodes/parts, mapping broadcast master structure, or delivering a visual segment report — not hard cuts inside content.
license: MIT
compatibility: Requires Python 3.11+, uv, ffmpeg, and ffprobe on PATH. Tesseract is governed by the selected OCR policy. Scripts use exact pinned PEP 723 dependencies via `uv run`.
metadata:
  mediaskills-category: video
  mediaskills-binaries: ffmpeg, ffprobe, tesseract
---

# Program Master

Build a full-coverage broadcast-master structure report from black+silent separators. The canonical workflow produces a labeled manifest, Markdown, structured JSON, a thumbnail-led PDF, and a machine-readable QC result in one run.

Requires Python 3.11+, `uv`, ffmpeg, and ffprobe. Tesseract is governed by the selected OCR policy. Python dependencies are exactly pinned in the executable scripts.

Run the bundled doctor before first use on a new system:

```bash
uv run scripts/doctor.py --profile profiles/broadcast-default.json
```

## Shots vs program-master

| Question | Use **program-master** | Use **shots** |
| --- | --- | --- |
| What are you finding? | Structural gaps between programs/parts (black + silent breaks) | Hard cuts inside content (camera angle changes, edits) |
| Typical source | TV master with black+silent separators | Any edited video |
| Output unit | Content segments with labels (episode, commercial, slate text) | Shot list with timecodes |
| Detection method | ffmpeg `blackdetect` + `silencedetect` overlap + fade refinement | ffmpeg `select=gt(scene,N)` |

## Use the canonical workflow

Run this command for normal delivery work:

```bash
uv run scripts/run_report.py \
  --input /absolute/path/master.mov \
  --output-dir /absolute/path/report_bundle \
  --profile profiles/broadcast-default.json
```

Add `--label-overrides /absolute/path/labels.json` when editorial names are known. Do not assemble a final delivery by calling the detector and compiler scripts independently; those scripts are diagnostic components of `run_report.py`.

The one-command workflow must finish with `passed: true`. It writes stable names under the requested output directory:

- `*_labeled_segments.json` — authoritative structural manifest and evidence
- `*_program_master.md` — complete user-readable table
- `*_program_master_report.json` — table data and provenance
- `*_broadcast_segment_report.pdf` — thumbnail-led visual report
- `*_broadcast_segment_report.json` — thumbnail selections and evidence
- `*_qc.json` — all structural, timecode, thumbnail, PDF, and source-hash checks
- `*_run.json` — bundle index and effective configuration
- `*_segment_probes/` and `*_broadcast_segment_report_thumbnails/` — visual evidence

Present the Markdown table and link the PDF, JSON report, manifest, and QC artifact. Never present a bundle whose QC did not pass.

## Repeatability contract

Every run must make these choices explicit in the profile or command:

- selected relative video stream
- either one selected audio stream or `all` audio streams
- embedded or file-relative timecode policy, including whether embedded timecode is mandatory
- OCR mode: `off`, `optional`, or `required`, plus language and PSM
- detector thresholds, fade policy, minimum overlap, and probe offset
- generic/raw label policy and whether every content row requires an editorial override
- expected minimum gap count and PDF layout policy

The manifest records the effective configuration, selected streams, authoritative video duration source, source SHA-256, profile SHA-256, tool versions, command, algorithm version, and schema version. Preserve these fields. Do not hand-edit detected timecodes or segment boundaries; rerun from a versioned profile.

The selected video stream is the duration authority. Segment intervals are start-inclusive and end-exclusive, begin at source frame zero, are contiguous, and cover the selected video through its exclusive final frame. The workflow fails closed on detector errors, missing required streams, a missing required tmcd, incomplete coverage, invalid overrides, missing thumbnails, or an invalid PDF.

## Profile and policy

Start with [`profiles/broadcast-default.json`](profiles/broadcast-default.json). Copy it into the report bundle when a project needs custom thresholds or policies; give the copy a descriptive `name` and keep `profile_version: "1.0"`.

Important examples:

```json
{
  "streams": {"video_stream": 0, "audio_policy": "all", "audio_stream": 0},
  "timecode": {"mode": "embedded", "require_embedded": true, "file_fps": 29.97},
  "ocr": {"mode": "required", "language": "eng", "psm": 6},
  "labels": {"mode": "generic", "overrides": {}, "require_overrides_for_content": true},
  "validation": {"min_gaps": 3}
}
```

Use `audio_policy: "single"` only when that program mix is the declared structure authority. Use `all` when every audio track must be silent before a region is considered a separator. `optional` OCR permits a run without Tesseract and records availability; `required` fails instead of silently degrading.

For broadcast delivery, prefer embedded tmcd and set `require_embedded: true` when the source is expected to carry it. File-relative timecode is permitted only when the policy explicitly allows it. Never substitute nominal 30 fps for 30000/1001.

## Editorial labels

Detection does not infer show-specific labels from segment numbers or hardcoded timecodes. Without overrides, content rows receive deterministic generic labels; readable OCR may supply a slate label. Gap rows are `black+silent separator`.

`--label-overrides` accepts any of:

```json
{"0": "Color bars / reference tone", "4": "Program Act 1 (texted)"}
```

```json
{"labels": {"0": "Color bars / reference tone", "4": "Program Act 1 (texted)"}}
```

It also accepts an existing report containing `rows` or `segments` with `index` and `label`. Unknown indices and empty labels fail. Set `labels.require_overrides_for_content` to `true` when all content names must be editorially approved. The report records the override file path and SHA-256.

## Boundary and fade policy

The detector finds overlap between strict black picture and silence, then refines black edges at native-frame luma resolution:

1. ffmpeg `blackdetect` uses strict black (`pix_th: 0.01`, `pic_th: 0.98` by default).
2. `silencedetect` runs on the declared audio stream policy.
3. Only overlaps meeting `min_overlap` become structural gaps.
4. Hard cuts stay on the detected cut.
5. A sustained luma ramp proves a fade; the mathematical black anchor is assigned to the adjoining content using `fade_handle_frames`.
6. A terminal gap within two frames of the selected video end is extended to that exclusive end.

Silence gates structural gaps but does not erase a picture fade. This preserves the true start of content even when its first included fade frame is visually black. Keep boundary timecodes distinct from thumbnail selection.

## Thumbnail PDF policy

Every content row has one source thumbnail at the start of the row. Gap rows use an intentional black+silent placeholder.

- Clean cut or intentional card: segment-start frame.
- Audio resumes while picture remains black: first picture after the proven black hold.
- Proven fade-up: first sustained upper-luma plateau within the configured search window.

The companion JSON records the chosen source frame, SMPTE timecode, offset from segment start, selection reason, and thumbnail path. Thus a faded content segment can correctly start at `01:00:00:00` while its report thumbnail shows the first fully established picture.

After generation, visually inspect every PDF page for clipped text, missing images, wrong row order, or illegible layout. Machine QC is mandatory but does not replace visual PDF QA.

## Report format

The Markdown report contains every structural row through tail black:

| # | Type | Start TC | End TC | Duration | Label |
| --- | --- | --- | --- | --- | --- |
| 0 | content | 00:58:40:00 | 00:59:40:00 | 1:00 | Color bars / reference tone |
| 1 | gap | 00:59:40:00 | 00:59:45:00 | 5s | black+silent separator |

Use the report’s timecodes exactly. Do not add a speaker/context column. Do not omit pre-roll, slates, gaps, credits, post-program material, or tail black.

## Diagnostic scripts

| Script | Purpose |
| --- | --- |
| `run_report.py` | Canonical orchestration and final delivery bundle |
| `label_segments.py` | Detect, refine, probe, label, timecode, provenance, manifest validation |
| `compile.py` | Markdown and structured JSON from a validated manifest |
| `compile_pdf.py` | Deterministic thumbnail-led PDF and companion JSON |
| `validate_report.py` | Fail-closed final bundle QC |
| `self_test.py` | Self-contained synthetic golden test, including deterministic PDF comparison |
| `doctor.py` | Runtime readiness: binaries, profile, OCR policy, pinned dependencies |
| `detect_black_silence.py` | Diagnostic black+silence overlap intervals |
| `detect_blacks.py` | Diagnostic black intervals |
| `detect_silence.py` | Diagnostic silence intervals |
| `schema.py` | Manifest JSON schema |
| `analyze_structure.py` | Legacy diagnostic; not a delivery workflow |

Run the golden test after changing code, thresholds, dependencies, schema, timecode, or rendering:

```bash
uv run scripts/self_test.py --work-dir /absolute/path/program-master-self-test
```

It synthesizes a tmcd MOV with hard cuts, black+silent gaps, a fade-up, and tail black; runs the complete workflow twice; verifies structure, embedded start timecode, fade thumbnail selection, source provenance, QC, PDF readability, and byte-identical deterministic PDFs.

## Acceptance checks (agent must pass before delivery)

Same fail-closed bar as **Human QC before delivery** below. Minimum automated gates:

1. Contract: exit 0, `ok: true`, delivery paths exist.
2. Skill gate: `*_qc.json` has `passed: true` and no errors; never present a failing bundle.
3. Spot-check: first segment at frame zero, final row at video duration, review fade edges and every PDF page.
4. On failure: fix overrides/thresholds and re-run `run_report.py`.

## Human QC before delivery

1. Read `*_qc.json`; require top-level `passed: true` and no errors.
2. Confirm the source SHA-256 and selected stream policy match the requested master.
3. Review every detected boundary and every `fade_in_detected` / `fade_out_detected` edge against nearby source frames when the edit decision is consequential.
4. Confirm labels cover the intended content rows and come from the approved override file when required.
5. Inspect every PDF page visually.
6. Confirm the first segment begins at source frame zero and the final row ends at the authoritative video duration.

## Do not use for

- hard cuts or camera shots inside content (use `shots`)
- subtitle or caption transcription (use `forced-narrative-exact` or `vision-analysis`)
- SCTE-only segmentation without black+silent structural evidence

Related skills: `inspect`, `timecode`, `forced-narrative-exact`, `vision-analysis`, and `shots`.

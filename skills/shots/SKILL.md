---
name: shots
description: Detect hard cuts (shot boundaries) in video via ffmpeg scene detection and extract midpoint stills per shot. Use when the unit of analysis is a shot — cataloging cuts, QC, or feeding shot-level frames to vision/OCR — not TV program structure or commercial breaks.
license: MIT
compatibility: Requires ffmpeg and ffprobe on PATH. Scripts are Python 3.11+, run via `uv run` (no separate install step).
metadata:
  mediaskills-category: video
  mediaskills-binaries: ffmpeg, ffprobe
---

# Shots

Detect hard cuts (shot boundaries) in video and extract a representative still from the middle of each shot.

## Shots vs program-master

| Question | Use **shots** | Use **program-master** |
| --- | --- | --- |
| What are you finding? | Hard cuts inside content (camera angle changes, edits) | Structural gaps between programs/parts (black + silent breaks) |
| Typical source | Any edited video | TV master with black+silent separators |
| Output unit | Shot list with timecodes | Content segments with labels (episode, commercial, slate text) |
| Detection method | ffmpeg `select=gt(scene,N)` | ffmpeg `blackdetect` + `silencedetect` overlap |

Use **shots** when you need every edit point or shot-level stills for vision analysis. Use **program-master** when the user asks to label segments, find commercial breaks, or name episodes/parts in a broadcast master. Do not use shot detection for TV structure — a single "shot" may span an entire scene, and program breaks are often fades, not hard cuts.

## When to use

- Cataloging a program into shots for review or QC
- Feeding shot-level stills into vision analysis or OCR
- Building on-screen text reports at shot granularity

Prefer shot detection over fixed-interval frame sampling when the unit of analysis is a **shot**, not a time grid. For uniform time sampling (e.g. every 1s for forced-narrative sweeps), extract frames at fixed intervals instead.

## Output paths

Shot manifests and extracted stills write to the **workspace root** `.mediaskills/generated/` (not inside this skill folder). Override with `$MEDIASKILLS_DATA_DIR/generated/` when set.

## Scripts

| Script | Purpose |
| --- | --- |
| `detect.py` | Scene-cut detection via ffmpeg `select=gt(scene,N)` |
| `extract-frames.py` | Extract midpoint stills for every shot |

## Recipes

### Shot catalog (cuts only)

```bash
uv run scripts/detect.py --input /path/to/clip.mp4
```

Read `shot_count` and `shots` from the JSON result. The manifest path is in `manifest_path` (auto-generated `*_shots.json` under `.mediaskills/generated/`).

### Shot stills for vision analysis

```bash
uv run scripts/detect.py --input clip.mp4
uv run scripts/extract-frames.py --shots-path .mediaskills/generated/clip_shots_*.json
```

Or detect inline:

```bash
uv run scripts/extract-frames.py --input clip.mp4
```

The updated manifest lists every `frame_path` with per-frame technical metadata (width/height). JPGs land in `.mediaskills/generated/<stem>_shot_frames/`.

### Threshold tuning

- Default `--threshold` is `0.35` (ffmpeg scene score 0–1). Lower (e.g. `0.25`) finds more cuts; higher (e.g. `0.5`) is stricter.
- `--min-shot-seconds` (default `0.5`) merges shots shorter than that into neighbors — reduces flicker from flash frames.
- Hard cuts are reliable; slow dissolves/fades may be missed (ffmpeg scene filter limitation).

## Outputs

- `detect.py` → JSON manifest (`*_shots.json`) with `shots[]` array: index, start/end seconds, timecodes, scene_score
- `extract-frames.py` → updates the manifest with `frames[]` and writes JPG stills to `frames_dir`

Always use the `manifest_path` / `shots_path` from the JSON result for downstream steps — do not invent filenames.

## Do not use for

- Full program structure / act breaks (use `program-master`)
- Vision-based scene understanding (use `vision-analysis`)

## Related skills

- `image` — `ocr.py` on a single extracted still
- `program-master` — black/silence TV structure (different segmentation axis)
- `video-transformation` — `extract_frame.py` for a single timestamp
- `timecode` — frame-accurate timecode math

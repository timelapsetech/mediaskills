# Workflow: QC on-screen text

Extract frames, agent analyzes, compile reports.

## Steps

```bash
# 1. Extract interval frames + manifest
cd skills/vision-analysis
uv run scripts/extract_interval_frames.py --input clip.mp4 --interval 2

# 2. Agent analyzes frames (see references/AGENT_FRAME_ANALYSIS.md)
#    Write per-batch JSON; merge:
uv run scripts/merge_analysis.py \
  --manifest-path .mediaskills/generated/clip_interval_frames.json \
  --frames-json batch0.json \
  --analysis-path analysis.json

# 3. Validate (required) and report
uv run scripts/validate_analysis.py --analysis-path analysis.json
uv run scripts/text_on_screen_report.py --analysis-path analysis.json --force
uv run scripts/forced_narrative_report.py --analysis-path analysis.json --force
```

## OCR-only shortcut (no agent)

```bash
uv run scripts/compile_report.py --input clip.mp4 --interval 2
uv run scripts/compile_forced_narrative_report.py \
  --onscreen-json .mediaskills/generated/clip_onscreen_text_*.json \
  --input clip.mp4
```

Requires `tesseract` on PATH.

## Agent notes

- Vision analysis is **agent-guided** for `merge_analysis` path; scripts do not call vision APIs.
- Use `get_frame_batch.py` to paginate large manifests.
- Never skip `validate_analysis.py` before delivering reports.

## Verification gate

- `validate_analysis.py` exits 0 with `ok: true`
- `analyzed_count` equals `frame_count` in the analysis / merge payload
- Spot-check first, middle, and last frame rows in the report against source stills

## Related skills

`inspect` → `vision-analysis`

For exhaustive frame-accurate burned-in dialogue delivery, use [forced-narrative-exact](forced-narrative-exact.md) instead.

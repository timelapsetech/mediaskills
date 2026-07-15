# Workflow: Exact forced-narrative inventory

Produce an exhaustive, frame-accurate burned-in dialogue report with exclusive-end SMPTE boundaries.

## Steps

```bash
# 1. Probe source (duration, FPS fraction, tmcd, drop-frame punctuation)
cd skills/inspect
uv run scripts/probe.py --input /absolute/path/master.mov

# 2. Scope program passes (optional but recommended for multi-pass masters)
cd ../program-master
uv run scripts/run_report.py \
  --input /absolute/path/master.mov \
  --output-dir /absolute/path/structure_bundle \
  --profile profiles/broadcast-default.json

# 3. Dense caption-band candidate discovery
cd ../forced-narrative-exact
uv run scripts/scan_caption_band.py \
  --input /absolute/path/master.mov \
  --start 80 --end 793 \
  --interval 0.5

# 4. Agent reviews scan frames and writes forced_narrative_seed.json
#    (see references/formats.md and references/report-contract.md)

# 5. Refine every cue to source frames
uv run scripts/refine_boundaries.py \
  --input /absolute/path/master.mov \
  --seed /absolute/path/forced_narrative_seed.json

# 6. Build paired Markdown / JSON / CSV / SRT
uv run scripts/build_report.py \
  --refined /absolute/path/forced_narrative_refined.json \
  --overrides /absolute/path/forced_narrative_overrides.json

# 7. Completeness audit when a verified textless duplicate exists
uv run scripts/audit_completeness.py \
  --input /absolute/path/master.mov \
  --report /absolute/path/forced_narrative_report.json \
  --region 1925,11313,36019 \
  --output /absolute/path/completeness_audit.json

# 8. Validate before delivery
uv run scripts/validate_report.py \
  --report /absolute/path/forced_narrative_report.json \
  --input /absolute/path/master.mov \
  --completeness-audit /absolute/path/completeness_audit_reviewed.json
```

## Agent notes

- OCR discovers candidates only; the agent must approve every cue from pictures.
- Exclusive end frames are mandatory; never widen timings by guesswork.
- Do not deliver when validation fails or completeness is not publication-ready.

## Related skills

`inspect` → `program-master` → `forced-narrative-exact`

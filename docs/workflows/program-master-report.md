# Workflow: Program master segment report

Build a validated broadcast structure report (Markdown, JSON, thumbnail PDF, QC) from black+silent separators.

## Steps

```bash
# 1. Confirm tools and skill layout
cd skills/program-master
uv run scripts/doctor.py --profile profiles/broadcast-default.json

# 2. Canonical delivery bundle
uv run scripts/run_report.py \
  --input /absolute/path/master.mov \
  --output-dir /absolute/path/report_bundle \
  --profile profiles/broadcast-default.json \
  --label-overrides /absolute/path/labels.json
```

Require `passed: true` in the JSON result and in `*_qc.json` before presenting the Markdown table or PDF.

## Optional golden self-test

```bash
uv run scripts/self_test.py --work-dir /absolute/path/program-master-self-test
```

## Agent notes

- Use a versioned profile; do not hand-edit detected boundaries.
- Prefer embedded tmcd when the source carries it (`timecode.require_embedded`).
- For burned-in dialogue inventories inside program acts, chain into `forced-narrative-exact` using the labeled segment ranges.

## Related skills

`inspect` → `program-master` → (`forced-narrative-exact` | `vision-analysis`)

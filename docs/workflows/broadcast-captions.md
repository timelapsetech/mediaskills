# Workflow: Broadcast captions package

Speech to SRT, compliance pass, export SCC/SMPTE-TT.

## Steps

```bash
# 1. Transcribe (or use existing SRT)
cd skills/speech-captions
uv run scripts/transcribe.py --input clip.mp4 --model small --output captions.srt

# 2. Validate and format
cd ../captions-compliance
uv run scripts/validate.py --input captions.srt
uv run scripts/format.py --input captions.srt --output captions_fmt.srt

# 3. Export broadcast formats
uv run scripts/to-scc.py --input captions_fmt.srt --output captions.scc
uv run scripts/to-smpte-tt.py --input captions_fmt.srt --output captions.xml
```

## One-shot pipeline

```bash
cd skills/captions-compliance
uv run scripts/to-captions-pipeline.py --input clip.mp4 --model tiny
```

## Agent notes

- Align 29.97 DF sequences with `timecode` skill before frame-critical exports.
- `validate.py` returns issues — fix with `format.py` before SCC export.
- Compliance scripts are heuristics, not legal certification.

## Related skills

`speech-captions` → `captions-compliance` → (`subtitles` for burn-in if needed)

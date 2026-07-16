# Workflow: Podcast audio cleanup

Extract/normalize audio, optionally mux back to video.

## Steps

```bash
# 1. Probe
cd skills/inspect
uv run scripts/describe.py --input episode.mp4

# 2. Normalize loudness
cd ../audio
uv run scripts/normalize.py --input episode.mp4
# Note output_path from JSON

# 3. Mux normalized audio back (if video podcast)
cd ../video-transformation
uv run scripts/replace_audio.py \
  --input episode.mp4 \
  --audio .mediaskills/generated/episode_normalized.wav \
  --copy-video
```

## Optional

- `audio/silence_detect.py` — find dead air for manual cuts
- `audio/trim.py` + `concat.py` — remove segments

## Agent notes

- `normalize.py` outputs WAV; do not use `transcode.py` for external audio.
- `replace_audio.py` uses `-shortest` — pad audio if video must run full length.

## Verification gate

```bash
# After mux: duration of muxed output should approximate source video duration
cd ../inspect
uv run scripts/describe.py --input .mediaskills/generated/<muxed>.mp4
uv run scripts/compare.py --input-a episode.mp4 --input-b .mediaskills/generated/<muxed>.mp4
```

If muxed duration is much shorter than source, audio was truncated (`-shortest`) — pad/extend audio and remux. Do not deliver without this check.

## Related skills

`inspect` → `audio` → `video-transformation` → `inspect`

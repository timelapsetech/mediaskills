# Workflow: Deliver H.264 + AAC MP4

Probe first, then transcode for delivery.

## Steps

```bash
# 1. Inspect source
cd skills/inspect
uv run scripts/describe.py --input /path/to/master.mov

# 2. Transcode (use output from inspect to confirm duration/codecs)
cd ../video-transformation
uv run scripts/transcode.py \
  --input /path/to/master.mov \
  --codec libx264 \
  --bitrate 5M \
  --output /path/to/deliverable.mp4
```

## Agent notes

- Parse `inspect.describe` → `data.duration` before setting trim bounds.
- Use `transcode.py` output `output_paths[0]` as the deliverable path.
- For web, consider `--crf 23` instead of bitrate (see script `--help`).

## Verification gate

```bash
# 3. Re-probe the deliverable (require H.264 + AAC; duration ≈ source)
cd ../inspect
uv run scripts/describe.py --input /path/to/deliverable.mp4
uv run scripts/compare.py --input-a /path/to/master.mov --input-b /path/to/deliverable.mp4
```

Do not present the file as delivered until `ok: true`, the output exists, and codecs/duration match the request.

## Related skills

`inspect` → `video-transformation` → `inspect`

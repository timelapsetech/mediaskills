# Workflow: 29.97 drop-frame edit from timecode

Convert timecode to seconds for ffmpeg trim points.

## Steps

```bash
# 1. Detect format if unknown
cd skills/timecode
uv run scripts/detect_format.py --timecode 01:00:00;00 --fps 29.97

# 2. Convert in/out points to seconds (wall-clock for ffmpeg -ss)
uv run scripts/to_seconds.py --timecode 00:10:00;00 --fps 29.97
uv run scripts/to_seconds.py --timecode 00:12:30;00 --fps 29.97

# 3. Trim using seconds_realtime from JSON
cd ../video-transformation
uv run scripts/trim.py --input clip.mov --start <in_seconds> --end <out_seconds>
```

## Cross-fps sequence

```bash
cd skills/timecode
uv run scripts/convert.py \
  --timecode 00:10:00:00 \
  --from-fps 24 \
  --to-fps 29.97
```

## DF ↔ NDF

```bash
uv run scripts/convert_df.py \
  --timecode 01:00:00;00 \
  --fps 29.97 \
  --to non-drop-frame
```

## Agent notes

- Semicolon (`;`) in frame field = drop-frame display.
- Prefer `seconds_realtime` for ffmpeg on NTSC DF material.
- See `skills/timecode/references/DF_NDF.md` for background.

## Related skills

`timecode` → `video-transformation`

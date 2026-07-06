# Drop-frame vs non-drop-frame (NTSC)

Quick reference for agents working with `timecode` skill scripts.

## Display formats

| Format | Example | Meaning |
| --- | --- | --- |
| Non-drop-frame (NDF) | `01:00:00:00` | Colon before frames |
| Drop-frame (DF) | `01:00:00;00` | Semicolon before frames |

## When drop-frame applies

NTSC nominal rates: **29.97**, **59.94**, `30000/1001`, `60000/1001`.

At these rates, drop-frame timecode skips frame numbers 00 and 01 at the start of each minute (except every 10th minute) so the counter stays aligned with wall-clock time.

## Which seconds value to use

Scripts return multiple second values:

| Field | Use when |
| --- | --- |
| `seconds` | Linear elapsed from frame index |
| `seconds_system` | Video system grid |
| `seconds_realtime` | **Wall-clock** — prefer for ffmpeg `-ss` on DF material |

## Conversion

```bash
uv run scripts/convert_df.py --timecode 01:00:00;00 --fps 29.97 --to non-drop-frame
uv run scripts/detect_format.py --timecode 01:00:00;00 --fps 29.97
```

## Library

Calculations use [eoyilmaz/timecode](https://github.com/eoyilmaz/timecode) (PyPI: `timecode`).

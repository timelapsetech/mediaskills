# Golden test fixtures

Committed under `tests/fixtures/` for reproducible integration and snapshot tests.

| File | Purpose |
| --- | --- |
| `sample.mp4` | 1 s H.264 + AAC, 320×240 — video probe, trim, transcode |
| `sample.wav` | 1 s sine tone — audio extract, whisper tests |
| `sample.png` | 160×120 test pattern — image ops |
| `sample.srt` | Two-cue subtitle — convert, validate, SCC |
| `sample.vtt` | WebVTT variant — subtitle convert |
| `ffprobe_drop_frame.json` | Synthetic ffprobe tags — `timecode/analyze_metadata.py` |

## Regenerating media fixtures

```bash
ffmpeg -y -f lavfi -i testsrc=duration=1:size=320x240:rate=30 \
  -f lavfi -i sine=frequency=440:duration=1 \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest tests/fixtures/sample.mp4

ffmpeg -y -f lavfi -i sine=frequency=440:duration=1 tests/fixtures/sample.wav

ffmpeg -y -f lavfi -i testsrc=duration=1:size=160x120:rate=1 \
  -frames:v 1 tests/fixtures/sample.png
```

Text fixtures (`*.srt`, `*.vtt`, `*.json`) are edited directly.

## Using in tests

```python
from pathlib import Path
FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
video = FIXTURES / "sample.mp4"
```

Root `tests/conftest.py` may expose shared fixture paths in future; skill tests currently use lavfi-generated media or these files via `tests/test_fixtures.py`.

## .gitignore

Loose `*.mp4` / `*.wav` / `*.png` in the repo are ignored except `!tests/fixtures/**`.

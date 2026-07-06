# Comparison: mediaskills vs alternatives

| Approach | Best for | Trade-offs |
| --- | --- | --- |
| **mediaskills** | Agents and humans needing repeatable media workflows with JSON outputs | Requires local ffmpeg/uv; not a hosted API |
| **Raw ffmpeg CLI** | One-off expert commands | No stable JSON contract; agents invent flags |
| **Custom MCP server** | Tight product integration | Maintenance burden; not portable across agents |
| **Cloud transcoding APIs** | Scale, managed codecs | Cost, upload latency, less offline control |

## When to use mediaskills

- Cursor / Claude Code / Codex skills workflows
- Offline or privacy-sensitive media on disk
- Chained steps (probe → trim → transcode → captions)
- Teaching agents broadcast-adjacent concepts (timecode, SCC)

## When not to use

- Frame-accurate finishing in Avid/Resolve (use NLE tools)
- Legal caption certification (heuristics only here)
- Real-time streaming transcoding
- Heavy ML beyond faster-whisper (no built-in vision model)

## Demo walkthrough (~2 minutes)

```bash
# 1. Install skill into your agent environment
npx skills add timelapsetech/mediaskills@v0.1.0 --skill install-media-tools
npx skills add timelapsetech/mediaskills@v0.1.0 --skill inspect

# 2. Verify tools
bash skills/install-media-tools/scripts/doctor.sh

# 3. Probe a file (use tests/fixtures/sample.mp4 in this repo)
cd skills/inspect
uv run scripts/describe.py --input ../../tests/fixtures/sample.mp4

# 4. Trim (video-transformation skill)
cd ../video-transformation
uv run scripts/trim.py --input ../../tests/fixtures/sample.mp4 --start 0 --end 0.5

# 5. Timecode check
cd ../timecode
uv run scripts/to_seconds.py --timecode 00:00:01;00 --fps 29.97
```

Each step prints JSON with `ok`, `op`, and `data` — agents parse the last stdout line.

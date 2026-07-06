# Agent frame analysis guide

Vision analysis in this skill does **not** call a local model, Ollama, or any bundled vision API. The **agent using the skill** must inspect frame images with whatever vision capabilities it has (multimodal chat, image tools, browser, etc.) and write structured JSON. Scripts then merge that JSON and generate reports.

If the agent cannot view images, use the **legacy OCR path** (`compile_report.py` with tesseract) or `image.ocr` on individual stills.

## Workflow

1. **Extract frames** (script) — `extract_interval_frames.py` or `shots` skill + `extract-frames.py`
2. **Batch frames** (script) — `get_frame_batch.py --manifest-path ... --batch-index N`
3. **Analyze images** (agent) — read each `frame_path` image; produce JSON per frame (see below)
4. **Merge results** (script) — `merge_analysis.py --manifest-path ... --frames-json batchN.json`
5. **Validate** (script, optional) — `validate_analysis.py --analysis-path ...`
6. **Reports** (script) — `text_on_screen_report.py`, `forced_narrative_report.py`, etc.

Repeat steps 2–4 until `analyzed_count` equals `frame_count`.

## Forced narrative report format

When the user asks for burned-in subtitles, forced narrative, or dialogue on screen, run `forced_narrative_report.py` and present **every dialogue line** in this table:

| Embedded TC | Speaker / context | Text (OCR) |
| --- | --- | --- |
| 01:01:27:00 | Squatter | I want you to go before the throne of God! |
| 01:03:24:00 | Officer | Yeah, obviously we're here to make sure that there's no sort of disturbance... |

- Classify spoken dialogue burned into the picture as `text_type: subtitle`.
- Put speaker names from caption labels in the `text` field as `SPEAKER: dialogue` when visible (e.g. `"text": "SQUATTER: Can you get off the property?"`).
- The report script parses speaker labels and maps file seconds to embedded SMPTE when tmcd is present.
- Do **not** include title cards, slates, credits, legal disclaimers, or lower-third show logos in subtitle entries.

## Per-frame JSON (agent output)

Each analyzed frame should include timing fields copied from the manifest plus vision fields:

```json
{
  "index": 0,
  "frame_path": "/path/to/frame_000000.jpg",
  "description": "Wide shot of a forest road.",
  "keywords": ["forest", "road", "outdoors"],
  "on_screen_text": [
    {
      "text": "Shelby Smith",
      "text_type": "lower_third",
      "location": "bottom",
      "confidence": 0.9
    }
  ]
}
```

Batch file format for `merge_analysis.py`:

```json
{
  "frames": [
    { "...": "..." }
  ]
}
```

## `text_type` values

| Value | Use for |
| --- | --- |
| `title` | Title card, show open, episode title |
| `lower_third` | Name/title chyron (not spoken dialogue) |
| `subtitle` | Burned-in dialogue / forced narrative |
| `locator` | Location/time/network bugs |
| `graphic` | Charts, maps, scoreboards |
| `background_text` | Signs, posters, text physically in scene |
| `credit` | End credits, copyright |
| `other` | Anything else |

## Rules the agent must follow

- `on_screen_text` must be **literal readable overlay text** in the image — not scene summaries, not guessed dialogue unless burned in as captions.
- Do not copy `description` wording into `on_screen_text`.
- Prefer empty `on_screen_text` over guesses.
- Use `analysis_schema.py` output or `references/AGENT_FRAME_ANALYSIS.md` for the full schema.

## When scripts are not enough

| Task | Agent | Script |
| --- | --- | --- |
| Extract JPGs from video | — | `extract_interval_frames.py` |
| View/analyze images | **Required** (if agent has vision) | — |
| Merge agent JSON | — | `merge_analysis.py` |
| Tesseract OCR only | — | `compile_report.py` |
| Generate timecoded reports | — | `*_report.py` |

If the agent lacks vision, say so explicitly and use OCR or ask the user to analyze frames manually.

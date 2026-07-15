# Forced-narrative report contract

## Inclusion

Include every burned-in line that represents dialogue, radio/dispatch speech, translated speech, inaudible-dialogue clarification, or a bracketed speaker/context label attached to dialogue.

Exclude program slates, textless slates, titles, lower thirds, location/time bugs, logos, credits, legal cards, recaps, story exposition cards, background signs, and ordinary English captions that are part of a full closed-caption track rather than forced narrative. If the source uses burned-in subtitles for all dialogue and the user explicitly wants all of them, include the full burned-in track.

Inspect the picture, not just OCR. Speech recognition may help identify a questionable word but must never invent text that is not visible.

## Cue identity and transcription

- Treat each distinct on-screen text state as one cue.
- Split a sentence when the visible lines change; do not merge successive cards into one row.
- Preserve the exact visible line order and line breaks.
- Preserve labels such as `[Trooper Stephens]`, `[Dispatch]`, and `Radio:` in the cue text.
- Preserve visible capitalization, punctuation, apostrophes, numerals, and bracket substitutions.
- Use straight apostrophes and quotation marks unless the picture clearly uses a different character.
- Set internal `speaker`/`speaker_context` metadata to the visible label without brackets. Use `—` when absent. Do not render this metadata as a separate report column.
- Do not silently “correct” grammar. Retain visible wording even when unconventional.

## Timing

- Use source video frames, never rounded OCR sample times, for final boundaries.
- `start_frame` is the first frame containing any pixel of the intended subtitle state.
- `end_frame_exclusive` is the first frame after that state is completely gone or replaced.
- For a direct subtitle replacement, the outgoing exclusive end may equal the incoming start.
- Derive seconds from frame number and exact FPS: `seconds = frame × denominator / numerator`.
- Derive file-relative and embedded SMPTE from frame counts, not floating-point wall-clock addition.
- Use semicolons for 29.97/59.94 drop-frame timecode.

## Master-pass scope

Inspect slates and program structure before inventorying text. A master may contain a texted pass followed by a textless duplicate. Confirm the duplicate visually at representative matching points and scan it for unexpected dialogue overlays. Include no duplicate rows when it is genuinely textless. Record the scope decision in the final JSON and Markdown.

## Required visual QC

For every cue, verify these four frames:

1. `start_frame - 1`: intended state absent.
2. `start_frame`: intended state present.
3. `end_frame_exclusive - 1`: intended state present.
4. `end_frame_exclusive`: intended state absent or replaced.

Always inspect all cues with any of these conditions:

- duration below 1.0 second;
- zero matched OCR word boxes;
- template peak below 0.85;
- a boundary within two frames of another cue;
- punctuation, numerals, speaker labels, or bracketed substitutions;
- mismatched OCR and visible text;
- a subtitle over a bright or rapidly changing background.

Inspect at least the first cue, final cue, shortest cue, every manual override, and ten evenly spaced cues at full frame resolution even when automated confidence is high.

## Required completeness QC

When a verified frame-aligned textless duplicate exists, compare every frame in each texted program region against its aligned textless frame after subtracting all report cue intervals.

- Preserve every uncovered difference interval; never retain only one representative for a broad activity cluster.
- Review the first frame, last frame, and samples no more than 12 frames apart throughout every interval.
- Split and investigate every visible text-state change, including states separated by short blank gaps.
- Classify every interval as `missing_dialogue`, `subtitle_boundary_residual`, `excluded_non_dialogue_text`, or `alignment_artifact`, with a specific review note.
- `missing_dialogue` and `subtitle_boundary_residual` block publication. Correct the report, rerun the audit against the corrected report, and review the new residual set.
- Delivery requires no unreviewed intervals and no blocking dispositions.

This coverage audit is a backstop, not a substitute for literal transcription or four-frame boundary QC. Picture misalignment, transitions, lower thirds, titles, time bugs, and credits can produce legitimate non-dialogue candidates that still require visual disposition.

## Output contract

Produce four stable siblings named `<source_stem>_forced_narrative_report`:

- `.md`: complete human-readable report and all cues.
- `.json`: authoritative structured report.
- `.csv`: one cue per row, with embedded/file TC, seconds, and frames.
- `.srt`: file-relative playback sidecar.

The Markdown cue table columns are:

| # | Embedded Start TC | Embedded End TC | Exact on-screen text |
| ---: | --- | --- | --- |

Do not include a separate speaker/context column in Markdown or CSV. Preserve any speaker or context label that is visibly part of the subtitle inside `Exact on-screen text`. Render line breaks as `<br>` in Markdown. Do not truncate the table.

The JSON must state the pass scope, timing-boundary convention, and literal-text convention. The report is incomplete if any cue lacks exact text, a start frame, or an exclusive end frame. When a verified textless duplicate exists, it is also incomplete without a publication-ready completeness audit.

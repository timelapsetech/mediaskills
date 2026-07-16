# Workflow index

End-to-end command sequences for agents and humans.

| Workflow | Skills |
| --- | --- |
| [Deliver H.264 + AAC MP4](deliver-h264-aac.md) | inspect → video-transformation |
| [Podcast audio cleanup](podcast-cleanup.md) | inspect → audio → video-transformation |
| [Broadcast captions package](broadcast-captions.md) | speech-captions → captions-compliance |
| [QC on-screen text](qc-on-screen-text.md) | vision-analysis |
| [Program master segment report](program-master-report.md) | program-master |
| [Exact forced-narrative inventory](forced-narrative-exact.md) | inspect → program-master → forced-narrative-exact |
| [29.97 DF edit from timecode](timecode-df-edit.md) | timecode → video-transformation |

Start with [AGENTS.md](../../AGENTS.md) for routing. Every workflow ends with a verification gate — do not deliver until it passes.

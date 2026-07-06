"""Normalize ffmpeg encode options from CLI flags."""

from __future__ import annotations

import re
from typing import Any

ALLOWED_VIDEO_CODECS = {
    "libx264",
    "libx265",
    "libvpx-vp9",
    "libsvtav1",
    "copy",
    "h264_videotoolbox",
    "hevc_videotoolbox",
}

CODEC_ALIASES = {
    "h264": "libx264",
    "x264": "libx264",
    "avc": "libx264",
    "avc1": "libx264",
    "h265": "libx265",
    "hevc": "libx265",
    "x265": "libx265",
    "vp9": "libvpx-vp9",
    "av1": "libsvtav1",
    "copy": "copy",
}

AUDIO_ALLOWED = {"aac", "libmp3lame", "copy", "ac3", "flac", "pcm_s16le"}

PRESETS = {
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
}


def _normalize_bitrate(value: str) -> str:
    b = value.lower().replace(" ", "")
    b = b.replace("mbps", "M").replace("mbit", "M").replace("mb/s", "M")
    b = b.replace("kbps", "k").replace("kbit", "k").replace("kb/s", "k")
    if re.fullmatch(r"\d+(\.\d+)?", b):
        n = float(b)
        return f"{int(n)}k" if n >= 100 else f"{b}M"
    if re.fullmatch(r"\d+(\.\d+)?m", b):
        return b[:-1] + "M"
    return b


def normalize_encode_options(
    *,
    codec: str = "libx264",
    bitrate: str | None = None,
    crf: float | None = None,
    preset: str = "fast",
    audio_codec: str = "aac",
    copy_video: bool = False,
) -> dict[str, Any]:
    raw_codec = codec.strip()
    br = (bitrate or "").strip()

    m = re.match(r"^(.+?)@(.+)$", raw_codec)
    if m:
        raw_codec, embedded = m.group(1).strip(), m.group(2).strip()
        if not br:
            br = embedded

    if not br:
        br_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(mbps|mbit|mb/s|kbps|kbit|kb/s)(?![a-z])",
            codec,
            re.I,
        )
        if not br_match:
            br_match = re.search(r"(?:^|_|-)(\d+(?:\.\d+)?)([mk])(?:_|-|$)", codec, re.I)
        if br_match:
            br = f"{br_match.group(1)}{br_match.group(2)}"

    if copy_video:
        video_codec = "copy"
    else:
        lower = raw_codec.lower().replace("-", "_")
        if lower in CODEC_ALIASES:
            video_codec = CODEC_ALIASES[lower]
        elif raw_codec in ALLOWED_VIDEO_CODECS:
            video_codec = raw_codec
        elif "265" in lower or "hevc" in lower:
            video_codec = "libx265"
        elif "vp9" in lower:
            video_codec = "libvpx-vp9"
        elif "av1" in lower or "svt" in lower:
            video_codec = "libsvtav1"
        elif "264" in lower or "avc" in lower or "x264" in lower:
            video_codec = "libx264"
        elif "videotoolbox" in lower and "265" in lower:
            video_codec = "hevc_videotoolbox"
        elif "videotoolbox" in lower:
            video_codec = "h264_videotoolbox"
        elif "copy" in lower:
            video_codec = "copy"
        else:
            video_codec = "libx264"

        if video_codec not in ALLOWED_VIDEO_CODECS:
            video_codec = "libx264"

    if br:
        br = _normalize_bitrate(br)

    audio_lower = audio_codec.lower()
    if audio_lower in ("mp3", "lame"):
        audio_out = "libmp3lame"
    elif audio_lower in AUDIO_ALLOWED:
        audio_out = audio_lower
    else:
        audio_out = "aac"

    preset_out = preset if preset.lower() in PRESETS else "fast"

    crf_out: str | None = None
    if crf is not None:
        try:
            crf_out = str(int(float(crf)))
        except (TypeError, ValueError):
            crf_out = None

    return {
        "codec": video_codec,
        "bitrate": br or None,
        "crf": crf_out,
        "preset": preset_out,
        "audio_codec": audio_out,
    }


def video_encode_args(opts: dict[str, Any]) -> list[str]:
    args: list[str] = []
    codec = opts["codec"]
    if codec == "copy":
        args.extend(["-c:v", "copy"])
        return args
    args.extend(["-c:v", codec, "-preset", opts["preset"]])
    if opts.get("bitrate"):
        args.extend(["-b:v", opts["bitrate"]])
    elif opts.get("crf"):
        args.extend(["-crf", opts["crf"]])
    else:
        args.extend(["-crf", "23"])
    return args


def ffmpeg_error_tail(stderr_path: str) -> str:
    from pathlib import Path

    lines = Path(stderr_path).read_text(errors="replace").splitlines()
    useful = [s.strip() for s in lines if s.strip() and not s.strip().startswith("{")]
    return (" | ".join(useful[-6:]) if useful else "ffmpeg failed")[:800]

# /// script
# requires-python = ">=3.11"
# dependencies = ["timecode==1.5.1"]
# ///

"""
Label TV program segments using black+silent gaps and probe frames.

For each black+silent separator, extracts a still before the gap start,
classifies it as content vs slate (OCR), and assigns labels to adjacent segments.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from shutil import which

from _embedded_timecode import (
    _fps_as_float,
    apply_embedded_timecodes,
    extract_embedded_timecode,
)
from _mediaskills_common import (
    add_input_arg,
    add_output_arg,
    emit_error,
    emit_progress,
    emit_success,
    ffprobe_json,
    generated_dir,
    main_wrapper,
    require_cmd,
    resolve_output,
    seconds_to_tc,
    validate_input_path,
)
from _segment_lib import (
    apply_probe_labels,
    build_content_segments,
    classify_probe_frame,
    detect_blacks,
    detect_silences,
    extract_frame,
    intersect_black_silence,
    normalize_terminal_gap,
    ocr_image,
    probe_audio_stream_count,
    probe_video_fps,
)
from _profile_lib import load_profile
from _provenance_lib import MANIFEST_SCHEMA_VERSION, SKILL_VERSION, build_provenance
from _validation_lib import validate_manifest

OP = "program_master.label_segments"


def selected_video_duration(
    stream: dict,
    *,
    format_duration: float,
    fps: float,
) -> tuple[float, str]:
    """Return the selected video stream's exclusive end with an auditable source."""
    nb_frames = stream.get("nb_frames")
    if nb_frames not in (None, "", "N/A"):
        try:
            count = int(nb_frames)
            if count > 0 and fps > 0:
                return count / fps, "video_stream.nb_frames/fps"
        except (TypeError, ValueError):
            pass
    duration_ts = stream.get("duration_ts")
    time_base = stream.get("time_base")
    if duration_ts not in (None, "", "N/A") and time_base and "/" in str(time_base):
        try:
            numerator, denominator = str(time_base).split("/", 1)
            duration = int(duration_ts) * int(numerator) / int(denominator)
            if duration > 0:
                return duration, "video_stream.duration_ts*time_base"
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    try:
        duration = float(stream.get("duration"))
        if duration > 0:
            return duration, "video_stream.duration"
    except (TypeError, ValueError):
        pass
    if format_duration <= 0:
        raise RuntimeError("Selected video stream has no usable duration")
    return format_duration, "container.duration_fallback"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: uv run label_segments.py --input program.mp4",
    )
    add_input_arg(parser)
    add_output_arg(parser)
    parser.add_argument("--profile", help="Versioned JSON run profile")
    parser.add_argument("--frames-dir", help="Explicit probe-frame directory")
    parser.add_argument("--noise", default=None, help="Silence threshold (default: profile)")
    parser.add_argument(
        "--min-duration",
        type=float,
        default=None,
        help="Minimum gap length in seconds (default: profile)",
    )
    parser.add_argument(
        "--pixel-threshold",
        type=float,
        default=None,
        help="Per-pixel black luma threshold (default: profile)",
    )
    parser.add_argument(
        "--picture-threshold",
        type=float,
        default=None,
        help="Fraction of pixels that must be black (default: profile)",
    )
    parser.add_argument(
        "--fade-refine",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Refine gradual black transitions to mathematical anchor frames (default: profile)",
    )
    parser.add_argument(
        "--fade-handle-frames",
        type=int,
        default=None,
        help="Black anchor frames assigned to detected fades (default: profile)",
    )
    parser.add_argument(
        "--min-overlap",
        type=float,
        default=None,
        help="Min seconds black and silence must overlap (default: profile)",
    )
    parser.add_argument(
        "--probe-offset-seconds",
        type=float,
        default=None,
        help="How far before each gap to grab the boundary still (default: profile)",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=None,
        help="Timecode display fps for file-relative TC (default: profile)",
    )
    parser.add_argument(
        "--timecode-mode",
        choices=["embedded", "file"],
        default=None,
        help="Use embedded SMPTE tmcd track or file-relative TC (default: profile)",
    )
    parser.add_argument("--video-stream", type=int, default=None, help="Relative video stream index")
    parser.add_argument("--audio-stream", type=int, default=None, help="Relative audio stream index")
    parser.add_argument(
        "--audio-policy",
        choices=["single", "all"],
        default=None,
        help="Analyze one audio stream or require silence across all streams",
    )
    parser.add_argument(
        "--require-embedded-timecode",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Fail if embedded tmcd/container timecode is unavailable",
    )
    parser.add_argument(
        "--ocr-mode",
        choices=["off", "optional", "required"],
        default=None,
        help="OCR availability policy (default: profile)",
    )
    parser.add_argument("--ocr-lang", default=None, help="Tesseract language (default: profile)")
    parser.add_argument("--ocr-psm", type=int, default=None, help="Tesseract page segmentation mode")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    path = validate_input_path(args.input, OP)
    require_cmd("ffmpeg", OP)
    require_cmd("ffprobe", OP)

    profile, profile_path = load_profile(args.profile)
    stream_cfg = profile.get("streams") or {}
    detection_cfg = profile.get("detection") or {}
    timecode_cfg = profile.get("timecode") or {}
    ocr_cfg = profile.get("ocr") or {}
    validation_cfg = profile.get("validation") or {}

    noise = str(args.noise if args.noise is not None else detection_cfg.get("noise", "-30dB"))
    min_duration = float(args.min_duration if args.min_duration is not None else detection_cfg.get("min_duration", 0.5))
    pixel_threshold = float(args.pixel_threshold if args.pixel_threshold is not None else detection_cfg.get("pixel_threshold", 0.01))
    picture_threshold = float(args.picture_threshold if args.picture_threshold is not None else detection_cfg.get("picture_threshold", 0.98))
    fade_refine = bool(args.fade_refine if args.fade_refine is not None else detection_cfg.get("fade_refine", True))
    fade_handle_frames = max(0, int(args.fade_handle_frames if args.fade_handle_frames is not None else detection_cfg.get("fade_handle_frames", 1)))
    min_overlap = float(args.min_overlap if args.min_overlap is not None else detection_cfg.get("min_overlap", 0.25))
    probe_offset = float(args.probe_offset_seconds if args.probe_offset_seconds is not None else detection_cfg.get("probe_offset_seconds", 1.0))
    fps = float(args.fps if args.fps is not None else timecode_cfg.get("file_fps", 29.97))
    timecode_mode = str(args.timecode_mode or timecode_cfg.get("mode", "embedded"))
    require_embedded = bool(
        args.require_embedded_timecode
        if args.require_embedded_timecode is not None
        else timecode_cfg.get("require_embedded", False)
    )
    video_stream = int(args.video_stream if args.video_stream is not None else stream_cfg.get("video_stream", 0))
    audio_stream = int(args.audio_stream if args.audio_stream is not None else stream_cfg.get("audio_stream", 0))
    audio_policy = str(args.audio_policy or stream_cfg.get("audio_policy", "single"))
    ocr_mode = str(args.ocr_mode or ocr_cfg.get("mode", "optional"))
    ocr_lang = str(args.ocr_lang or ocr_cfg.get("language", "eng"))
    ocr_psm = int(args.ocr_psm if args.ocr_psm is not None else ocr_cfg.get("psm", 6))

    probe_meta = ffprobe_json(str(path), OP)
    videos = [stream for stream in probe_meta.get("streams") or [] if stream.get("codec_type") == "video"]
    audios = [stream for stream in probe_meta.get("streams") or [] if stream.get("codec_type") == "audio"]
    if video_stream < 0 or video_stream >= len(videos):
        emit_error(OP, f"video stream {video_stream} is unavailable", code=1)
    audio_count = probe_audio_stream_count(str(path))
    if audio_count != len(audios):
        emit_error(OP, "ffprobe audio stream inventory was inconsistent", code=3)

    video_fps = probe_video_fps(str(path), video_stream=video_stream)
    try:
        format_duration = float((probe_meta.get("format") or {}).get("duration") or 0)
    except (TypeError, ValueError):
        format_duration = 0.0
    duration, duration_source = selected_video_duration(
        videos[video_stream],
        format_duration=format_duration,
        fps=video_fps,
    )

    emit_progress("detecting black+silence gaps", 15)
    silences = detect_silences(
        str(path),
        noise=noise,
        min_duration=min_duration,
        audio_stream=audio_stream,
        audio_policy=audio_policy,
    )
    blacks = detect_blacks(
        str(path),
        min_duration=min_duration,
        pixel_threshold=pixel_threshold,
        picture_threshold=picture_threshold,
        refine_fades=fade_refine,
        fade_handle_frames=fade_handle_frames,
        video_stream=video_stream,
    )
    gaps = intersect_black_silence(blacks, silences, min_overlap=min_overlap)
    normalize_terminal_gap(
        gaps,
        duration=duration,
        fps=video_fps,
    )

    frames_dir = Path(args.frames_dir) if args.frames_dir else generated_dir() / f"{path.stem}_segment_probes"
    frames_dir.mkdir(parents=True, exist_ok=True)

    emit_progress("extracting probe frames", 40)
    probes: list[dict] = []
    for i, gap in enumerate(gaps):
        requested_time = max(0.0, gap["start"] - probe_offset)
        probe_frame = int(round(requested_time * video_fps))
        probe_time = probe_frame / video_fps
        frame_path = frames_dir / f"probe_gap_{i:04d}_{probe_time:.3f}s.jpg"
        extract_frame(str(path), probe_time, frame_path, video_stream=video_stream)
        ocr_text = ocr_image(
            frame_path,
            mode=ocr_mode,
            language=ocr_lang,
            psm=ocr_psm,
        )
        classification = classify_probe_frame(frame_path, ocr_text)
        probes.append(
            {
                "gap_index": i,
                "gap_start": gap["start"],
                "gap_end": gap["end"],
                "probe_time": probe_time,
                "probe_frame": probe_frame,
                "probe_offset_seconds": probe_offset,
                "frame_path": str(frame_path),
                "ocr_text": ocr_text,
                "classification": classification,
            }
        )

    emit_progress("building labeled segments", 75)
    segments = build_content_segments(gaps, duration)
    apply_probe_labels(segments, probes)

    embedded_tc = (
        extract_embedded_timecode(probe_meta, video_stream=video_stream)
        if timecode_mode == "embedded"
        else None
    )
    if require_embedded and not embedded_tc:
        emit_error(OP, "embedded timecode was required but no tmcd/container timecode was found", code=3)
    tc_fps = embedded_tc["fps"] if embedded_tc else str(fps)
    tc_fps_float = _fps_as_float(tc_fps)

    for seg in segments:
        seg["start_timecode"] = seconds_to_tc(seg["start"], tc_fps_float)
        seg["end_timecode"] = seconds_to_tc(seg["end"], tc_fps_float)
        if seg.get("segment_type") == "content" and not seg.get("label"):
            seg["label"] = "unlabeled"
            seg["label_source"] = "none"

    if embedded_tc:
        apply_embedded_timecodes(segments, embedded_tc)

    manifest_path = resolve_output(str(path), "_labeled_segments.json", args.output)
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "algorithm_version": SKILL_VERSION,
        "input_path": str(path.resolve()),
        "duration": duration,
        "fps": tc_fps if embedded_tc else fps,
        "timecode_mode": "embedded" if embedded_tc else "file",
        "embedded_timecode": embedded_tc,
        "probe_offset_seconds": probe_offset,
        "black_detection": {
            "pixel_threshold": pixel_threshold,
            "picture_threshold": picture_threshold,
            "fade_refine": fade_refine,
            "fade_handle_frames": fade_handle_frames,
            "boundary_policy": (
                "strict black plateau intersected with silence; gradual fades use "
                "their mathematical black anchor frame"
            ),
        },
        "black_silence_gaps": gaps,
        "silences": silences,
        "blacks": blacks,
        "probes": probes,
        "segments": segments,
        "frames_dir": str(frames_dir),
        "labeled_count": sum(
            1
            for s in segments
            if s.get("segment_type") == "content" and s.get("label") not in (None, "unlabeled")
        ),
        "content_segment_count": sum(1 for s in segments if s.get("segment_type") == "content"),
        "gap_count": len(gaps),
    }
    selected_streams = {
        "video_relative_index": video_stream,
        "video_stream_index": videos[video_stream].get("index"),
        "audio_policy": audio_policy,
        "audio_relative_indices": list(range(audio_count)) if audio_policy == "all" else [audio_stream],
        "audio_stream_indices": (
            [stream.get("index") for stream in audios]
            if audio_policy == "all"
            else [audios[audio_stream].get("index")]
        ),
        "duration_authority": duration_source,
        "duration_seconds": duration,
    }
    effective_config = json.loads(json.dumps(profile))
    effective_config["streams"] = {
        "video_stream": video_stream,
        "audio_policy": audio_policy,
        "audio_stream": audio_stream,
    }
    effective_config["detection"] = {
        "noise": noise,
        "min_duration": min_duration,
        "pixel_threshold": pixel_threshold,
        "picture_threshold": picture_threshold,
        "fade_refine": fade_refine,
        "fade_handle_frames": fade_handle_frames,
        "min_overlap": min_overlap,
        "probe_offset_seconds": probe_offset,
    }
    effective_config["timecode"] = {
        "mode": timecode_mode,
        "require_embedded": require_embedded,
        "file_fps": fps,
    }
    effective_config["ocr"] = {
        "mode": ocr_mode,
        "language": ocr_lang,
        "psm": ocr_psm,
        "available": which("tesseract") is not None,
    }
    manifest["effective_config"] = effective_config
    manifest["profile_path"] = str(profile_path)
    manifest["selected_streams"] = selected_streams
    manifest["provenance"] = build_provenance(
        path,
        profile=effective_config,
        profile_path=profile_path,
        selected_streams=selected_streams,
        command=sys.argv,
    )
    validation = validate_manifest(
        manifest,
        require_embedded_timecode=require_embedded,
        min_gaps=int(validation_cfg.get("min_gaps", 0)),
    )
    manifest["validation"] = validation
    if not validation["passed"]:
        emit_error(OP, "; ".join(validation["errors"]), code=3)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    emit_progress("done", 100)
    emit_success(
        OP,
        {
            **manifest,
            "output_path": str(manifest_path),
            "structure_path": str(manifest_path),
            "manifest_path": str(manifest_path),
        },
        [str(manifest_path), *[p["frame_path"] for p in probes]],
    )


if __name__ == "__main__":
    main_wrapper(main)

"""Shared pytest fixtures for mediaskills."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.helpers import REPO_ROOT


def has_cmd(name: str) -> bool:
    return shutil.which(name) is not None


@pytest.fixture(scope="session")
def ffmpeg_available() -> bool:
    return has_cmd("ffmpeg") and has_cmd("ffprobe")


@pytest.fixture(scope="session")
def uv_available() -> bool:
    return has_cmd("uv")


@pytest.fixture
def tmp_media_dir(tmp_path: Path) -> Path:
    out = tmp_path / "media"
    out.mkdir()
    return out


@pytest.fixture
def sample_video(tmp_media_dir: Path, ffmpeg_available: bool) -> Path:
    if not ffmpeg_available:
        pytest.skip("ffmpeg/ffprobe not available")
    path = tmp_media_dir / "sample.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2:size=320x240:rate=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


@pytest.fixture
def sample_audio(tmp_media_dir: Path, ffmpeg_available: bool) -> Path:
    if not ffmpeg_available:
        pytest.skip("ffmpeg/ffprobe not available")
    path = tmp_media_dir / "sample.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


@pytest.fixture
def sample_image(tmp_media_dir: Path, ffmpeg_available: bool) -> Path:
    if not ffmpeg_available:
        pytest.skip("ffmpeg/ffprobe not available")
    path = tmp_media_dir / "sample.png"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=1:size=160x120:rate=1",
            "-frames:v",
            "1",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


@pytest.fixture(scope="session", autouse=True)
def _sync_vendored_libs() -> None:
    from tests.helpers import sync_shared_libs

    sync_shared_libs()

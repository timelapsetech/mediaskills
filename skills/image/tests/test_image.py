"""Tests for image skill scripts."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
from tests.helpers import parse_json_stdout, run_script  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_DIR / "scripts"


def has_cmd(name: str) -> bool:
    return shutil.which(name) is not None


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    if not has_cmd("ffmpeg"):
        pytest.skip("ffmpeg not available")
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    path = media_dir / "sample.png"
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


@pytest.fixture(scope="module", autouse=True)
def sync_common():
    import subprocess

    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "sync_shared_libs.py")],
        check=True,
        cwd=REPO_ROOT,
    )


@pytest.mark.skipif(not shutil.which("convert"), reason="ImageMagick convert not available")
def test_convert(sample_image: Path, tmp_path: Path):
    out = tmp_path / "out.jpg"
    result = run_script(
        SCRIPTS / "convert.py",
        "--input",
        str(sample_image),
        "--format",
        "jpg",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "image.convert"
    assert out.is_file()


@pytest.mark.skipif(not shutil.which("convert"), reason="ImageMagick convert not available")
def test_resize(sample_image: Path, tmp_path: Path):
    out = tmp_path / "resized.png"
    result = run_script(
        SCRIPTS / "resize.py",
        "--input",
        str(sample_image),
        "--width",
        "80",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert out.is_file()


@pytest.mark.skipif(not shutil.which("convert"), reason="ImageMagick convert not available")
def test_crop(sample_image: Path, tmp_path: Path):
    out = tmp_path / "cropped.png"
    result = run_script(
        SCRIPTS / "crop.py",
        "--input",
        str(sample_image),
        "--width",
        "50",
        "--height",
        "40",
        "--x",
        "10",
        "--y",
        "5",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert out.is_file()


@pytest.mark.skipif(not shutil.which("convert"), reason="ImageMagick convert not available")
def test_rotate(sample_image: Path, tmp_path: Path):
    out = tmp_path / "rotated.png"
    result = run_script(
        SCRIPTS / "rotate.py",
        "--input",
        str(sample_image),
        "--degrees",
        "90",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert out.is_file()


@pytest.mark.skipif(not shutil.which("convert"), reason="ImageMagick convert not available")
def test_flip_horizontal(sample_image: Path, tmp_path: Path):
    out = tmp_path / "flipped.png"
    result = run_script(
        SCRIPTS / "flip.py",
        "--input",
        str(sample_image),
        "--direction",
        "horizontal",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert out.is_file()


@pytest.mark.skipif(not shutil.which("convert"), reason="ImageMagick convert not available")
def test_optimize(sample_image: Path, tmp_path: Path):
    out = tmp_path / "opt.jpg"
    result = run_script(
        SCRIPTS / "optimize.py",
        "--input",
        str(sample_image),
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert out.is_file()


@pytest.mark.skipif(not shutil.which("convert"), reason="ImageMagick convert not available")
def test_strip_metadata(sample_image: Path, tmp_path: Path):
    out = tmp_path / "clean.png"
    result = run_script(
        SCRIPTS / "strip_metadata.py",
        "--input",
        str(sample_image),
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert out.is_file()


@pytest.mark.skipif(not shutil.which("exiftool"), reason="exiftool not available")
def test_read_exif(sample_image: Path):
    result = run_script(SCRIPTS / "read_exif.py", "--input", str(sample_image))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "image.read_exif"
    assert isinstance(data["data"], list)


@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract not available")
def test_ocr(sample_image: Path):
    result = run_script(SCRIPTS / "ocr.py", "--input", str(sample_image))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "image.ocr"
    assert "text" in data["data"]


def test_missing_input():
    result = run_script(SCRIPTS / "convert.py")
    assert result.returncode != 0

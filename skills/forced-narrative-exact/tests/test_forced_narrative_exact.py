"""Tests for forced-narrative-exact skill scripts."""

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


@pytest.fixture(scope="module", autouse=True)
def sync_common():
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "sync_shared_libs.py")],
        check=True,
        cwd=REPO_ROOT,
    )


def test_scan_caption_band(sample_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    if shutil.which("tesseract") is None:
        pytest.skip("tesseract not available")
    monkeypatch.setenv("MEDIASKILLS_DATA_DIR", str(tmp_path))
    result = run_script(
        SCRIPTS / "scan_caption_band.py",
        "--input",
        str(sample_video),
        "--interval",
        "0.5",
        "--force",
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "forced_narrative_exact.scan_caption_band"
    assert Path(data["data"]["output_path"]).is_file()
    assert Path(data["data"]["frames_dir"]).is_dir()


def test_self_test(tmp_path: Path):
    result = run_script(SCRIPTS / "self_test.py", "--work-dir", str(tmp_path / "fne-self-test"))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "forced_narrative_exact.self_test"
    assert data["data"]["validated"] is True
    assert data["data"]["cue_count"] == 1

"""Tests for install-media-tools bash scripts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
from tests.helpers import parse_json_stdout  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_DIR / "scripts"


@pytest.fixture(scope="module", autouse=True)
def sync_common():
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "sync_shared_libs.py")],
        check=True,
        cwd=REPO_ROOT,
    )


def run_bash(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), *args],
        capture_output=True,
        text=True,
        cwd=script.parent,
    )


def test_doctor():
    result = run_bash(SCRIPTS / "doctor.sh")
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "install-media-tools.doctor"
    assert "healthy" in data["data"]
    assert isinstance(data["data"]["installed"], list)
    assert isinstance(data["data"]["missing"], list)
    assert "platform" in data["data"]


def test_detect_tools():
    result = run_bash(SCRIPTS / "detect-tools.sh")
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "install-media-tools.detect_tools"
    assert isinstance(data["data"]["tools"], list)


def test_which_ffmpeg():
    result = run_bash(SCRIPTS / "which.sh", "--tool", "ffmpeg")
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["data"]["tool"] == "ffmpeg"


def test_install_syntax():
    result = subprocess.run(
        ["bash", "-n", str(SCRIPTS / "install.sh")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(
    not os.environ.get("MEDIASKILLS_RUN_INSTALL"),
    reason="Set MEDIASKILLS_RUN_INSTALL=1 to run install.sh smoke test",
)
def test_install_smoke():
    result = run_bash(SCRIPTS / "install.sh")
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert data["ok"] is True
    assert data["op"] == "install-media-tools.install"
    assert "platform" in data["data"]

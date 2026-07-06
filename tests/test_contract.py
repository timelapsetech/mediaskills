"""Contract and golden-fixture tests."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
from tests.helpers import parse_json_stdout, run_script, sync_shared_libs  # noqa: E402

OP_RE = re.compile(r"""op\s*=\s*["']([^"']+)["']|OP\s*=\s*["']([^"']+)["']""")


@pytest.fixture(scope="module", autouse=True)
def _sync():
    sync_shared_libs()


def discover_ops() -> list[tuple[str, Path]]:
    rows: list[tuple[str, Path]] = []
    for skill_dir in sorted((REPO_ROOT / "skills").iterdir()):
        script_dir = skill_dir / "scripts"
        if not script_dir.is_dir():
            continue
        for path in sorted(script_dir.glob("*.py")):
            if path.name.startswith("_"):
                continue
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                m = OP_RE.search(line)
                if m:
                    rows.append((m.group(1) or m.group(2), path))
                    break
    return rows


def assert_success_contract(data: dict) -> None:
    assert data.get("ok") is True
    assert isinstance(data.get("op"), str) and data["op"]
    assert isinstance(data.get("data"), dict)
    assert isinstance(data.get("output_paths"), list)


@pytest.mark.parametrize("op,path", discover_ops())
def test_op_id_matches_skill_prefix(op: str, path: Path):
    skill_dir = path.parents[1].name
    prefix = op.split(".", 1)[0]
    expected = {
        "video-transformation": "video",
        "captions-compliance": "caption",
        "speech-captions": "speech_captions",
        "program-master": "program_master",
        "vision-analysis": "vision",
        "install-media-tools": "install-media-tools",
    }.get(skill_dir, skill_dir.replace("-", "_"))
    assert prefix == expected


def test_index_json_matches_list_ops():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "list_ops.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr or result.stdout


@pytest.mark.parametrize(
    "script,op",
    [
        ("skills/inspect/scripts/info.py", "inspect.info"),
        ("skills/timecode/scripts/info.py", "timecode.info"),
        ("skills/video-transformation/scripts/info.py", "video.info"),
        ("skills/captions-compliance/scripts/info.py", "caption.info"),
    ],
)
def test_info_scripts_contract(script: str, op: str):
    result = run_script(REPO_ROOT / script)
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert_success_contract(data)
    assert data["op"] == op


def test_fixture_probe_describe():
    video = FIXTURES / "sample.mp4"
    assert video.is_file()
    result = run_script(REPO_ROOT / "skills/inspect/scripts/describe.py", "--input", str(video))
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert_success_contract(data)
    assert float(data["data"]["duration"]) == pytest.approx(1.0, abs=0.15)


def test_fixture_timecode_analyze_metadata():
    meta = FIXTURES / "ffprobe_drop_frame.json"
    result = run_script(
        REPO_ROOT / "skills/timecode/scripts/analyze_metadata.py",
        "--input",
        str(meta),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert_success_contract(data)
    assert data["data"]["inferred_drop_frame"] is True


def test_fixture_subtitles_srt_to_vtt(tmp_path: Path):
    out = tmp_path / "out.vtt"
    result = run_script(
        REPO_ROOT / "skills/subtitles/scripts/convert.py",
        "--input",
        str(FIXTURES / "sample.srt"),
        "--format",
        "vtt",
        "--output",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    data = parse_json_stdout(result)
    assert_success_contract(data)
    text = out.read_text(encoding="utf-8")
    assert "WEBVTT" in text
    assert "Hello from mediaskills fixtures" in text


def test_error_contract_missing_input():
    result = run_script(
        REPO_ROOT / "skills/inspect/scripts/probe.py",
        "--input",
        "/nonexistent/mediaskills_test_file.mp4",
    )
    assert result.returncode != 0
    line = result.stderr.strip().splitlines()[-1]
    data = json.loads(line)
    assert data.get("ok") is False
    assert data.get("op") == "inspect.probe"
    assert "error" in data

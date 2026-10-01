"""The hooks in .agents/hooks: what each blocks and lets through."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / ".agents" / "hooks"


def run_hook(name: str, event: dict, project: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOKS / name)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)},
        timeout=30,
    )


def edit(file_path: str) -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": file_path}, "cwd": str(ROOT)}


@pytest.mark.parametrize(
    "path",
    [
        "data/c3-schemas/en-US/plugins/sprite.json",
        "data/c3-schemas/_index.json",
        "data/c3-lang/zh-CN.json",
        "data/c3-ts-defs/autocomplete-data.json",
        "data/c3-examples/en-US/examples.json",
    ],
)
def test_edit_of_exported_data_is_blocked(path):
    for file_path in (path, str(ROOT / path)):
        result = run_hook("guard_exported_data.py", edit(file_path))
        assert result.returncode == 2
        assert "scripts/init.py" in result.stderr


@pytest.mark.parametrize(
    "path",
    [
        "data/AGENTS.md",
        "data/c3-new-project/project.c3proj",
        "src/ingest/c3_fetcher.py",
        "docs/data-c3-schemas.md",
    ],
)
def test_edit_elsewhere_passes(path):
    assert run_hook("guard_exported_data.py", edit(path)).returncode == 0


def test_input_that_is_not_an_event_is_reported_not_blocked():
    result = subprocess.run(
        [sys.executable, str(HOOKS / "guard_exported_data.py")],
        input="not json",
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert "nothing checked" in result.stderr


def test_settings_register_every_hook():
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for group in settings["hooks"]["PreToolUse"]
        for hook in group["hooks"]
    ]
    for script in sorted(p.name for p in HOOKS.glob("*.py")):
        assert any(script in command for command in commands), script

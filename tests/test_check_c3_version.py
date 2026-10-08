"""What scripts/check_c3_version.py tells the update workflow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from scripts import check_c3_version
from src.settings import load_settings


@pytest.fixture
def github_output(tmp_path, monkeypatch):
    path = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(path))
    return path


@pytest.mark.parametrize("error", [LookupError("no Stable release"), OSError("unreachable"), ValueError("not JSON")])
def test_a_failed_check_fails_and_writes_no_output(github_output, capsys, error):
    """A CDN that cannot be read must not read as "no new release"."""
    with patch.object(check_c3_version, "latest_stable_version", side_effect=error):
        assert check_c3_version.main(["--github-output"]) == 1
    assert not github_output.exists()
    assert str(error) in capsys.readouterr().err


@pytest.mark.parametrize("latest_is_current, changed", [(True, "false"), (False, "true")])
def test_the_outputs_say_whether_the_release_changed(github_output, latest_is_current, changed):
    current = load_settings().schema.version
    latest = current if latest_is_current else "r9999"
    with patch.object(check_c3_version, "latest_stable_version", return_value=latest):
        assert check_c3_version.main(["--github-output"]) == 0
    assert github_output.read_text(encoding="utf-8").splitlines() == [
        f"current={current}", f"latest={latest}", f"changed={changed}",
    ]

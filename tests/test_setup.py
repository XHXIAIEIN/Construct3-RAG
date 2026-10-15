"""The steps scripts/setup.py takes: the schemas in data/ unless a refresh is asked for, then the
lookup service."""

from __future__ import annotations

import sys

import pytest

import scripts.setup as setup


def _main_steps(monkeypatch: pytest.MonkeyPatch, *flags: str) -> list[tuple]:
    """The steps ``setup.main()`` takes with these flags, in order, each step stubbed."""
    calls: list[tuple] = []
    monkeypatch.setattr(sys, "argv", ["setup.py", "--skip-deps", *flags])
    monkeypatch.setattr(setup, "check_python", lambda: None)
    monkeypatch.setattr(setup, "refresh", lambda version=None: calls.append(("cdn", version)))
    monkeypatch.setattr(setup, "report_local_schema", lambda: calls.append(("local",)))
    monkeypatch.setattr(setup, "start_server", lambda port: calls.append(("server", port)))
    setup.main()
    return calls


def test_default_setup_uses_local_schema_without_cdn(monkeypatch):
    calls = _main_steps(monkeypatch)

    assert ("local",) in calls
    assert not any(call[0] == "cdn" for call in calls)
    assert ("server", setup.SETTINGS.runtime.server_port) in calls


def test_explicit_refresh_fetches_before_lookup_server(monkeypatch):
    calls = _main_steps(monkeypatch, "--refresh-data")

    assert calls[0] == ("cdn", None)
    assert ("local",) not in calls
    assert calls[-1] == ("server", setup.SETTINGS.runtime.server_port)


def test_start_server_runs_uvicorn_with_reload(monkeypatch):
    commands: list[list[str]] = []
    monkeypatch.setattr(setup, "run", lambda command, **kwargs: commands.append(command))

    setup.start_server(port=9000)

    command = commands[-1]
    assert command[-1] == "--reload"
    assert "9000" in command

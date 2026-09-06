"""Product-boundary tests for the setup launcher."""

from __future__ import annotations

import sys

import scripts.setup as setup


def test_default_setup_uses_local_schema_without_cdn(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(sys, "argv", ["setup.py", "--skip-deps"])
    monkeypatch.setattr(setup, "check_python", lambda: None)
    monkeypatch.setattr(setup, "fetch_cdn", lambda version=None: calls.append(("cdn", version)))
    monkeypatch.setattr(setup, "report_local_schema", lambda: calls.append(("local",)))
    monkeypatch.setattr(
        setup,
        "start_server",
        lambda port, full=False, version=None: calls.append(
            ("server", port, full, version)
        ),
    )

    setup.main()

    assert ("local",) in calls
    assert not any(call[0] == "cdn" for call in calls)
    assert ("server", setup.RAG_SERVER_PORT, False, None) in calls


def test_explicit_refresh_fetches_before_lookup_server(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(
        sys, "argv", ["setup.py", "--skip-deps", "--refresh-data"]
    )
    monkeypatch.setattr(setup, "check_python", lambda: None)
    monkeypatch.setattr(setup, "fetch_cdn", lambda version=None: calls.append(("cdn", version)))
    monkeypatch.setattr(setup, "report_local_schema", lambda: calls.append(("local",)))
    monkeypatch.setattr(
        setup,
        "start_server",
        lambda port, full=False, version=None: calls.append(
            ("server", port, full, version)
        ),
    )

    setup.main()

    assert calls[0] == ("cdn", None)
    assert ("local",) not in calls
    assert calls[-1] == ("server", setup.RAG_SERVER_PORT, False, None)


def test_start_server_passes_explicit_mode_and_version(monkeypatch):
    captured: dict = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)

    monkeypatch.setattr(setup, "run", fake_run)

    setup.start_server(port=9000, full=True, version="r999")

    assert captured["env"]["LITE_MODE"] == "false"
    assert captured["env"]["C3_VERSION"] == "r999"
    assert captured["command"][-1] == "--reload"
    assert "9000" in captured["command"]

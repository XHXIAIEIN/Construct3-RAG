"""Download the files of a published Construct game for study: data, scripts, images, fonts.

Audio and video are skipped. A source is ``<kind>:<id>``; the workspace's ``resolvers.py`` turns
it into the base URL of the game's files and a referer.

    python -m scripts.reference_games fetch <kind>:<id> [more sources]

Each game lands in the ignored reference-game workspace with a ``manifest.json``.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKSPACE = REPO / ".local" / "docs" / "evidence" / "c3-reference-games"
DOWNLOADS = WORKSPACE / "downloads"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
SKIP_EXT = {".webm", ".ogg", ".m4a", ".mp3", ".wav", ".mp4", ".opus", ".aac"}
OPTIONAL_SCRIPTS = {
    "scripts/c3main.js", "scripts/c3runtime.js", "scripts/workermain.js", "scripts/dispatchworker.js",
    "scripts/jobworker.js", "scripts/scriptsInEvents.js", "scripts/project/scriptsInEvents.js",
    "c2runtime.js", "data.js", "offline.json",
}
KEEP_EXT = {".json", ".js", ".webp", ".png", ".jpg", ".jpeg", ".avif", ".otf", ".ttf", ".woff", ".woff2", ".css", ".svg", ".txt", ".csv", ".xml"}


def get(url: str, referer: str | None = None, timeout: int = 30) -> bytes:
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def resolve(source: str) -> tuple[str, str]:
    """Base URL of a game's files and the referer to send, from the workspace's ``resolvers.py``."""
    path = WORKSPACE / "resolvers.py"
    if not path.exists():
        raise SystemExit(f"No source resolvers at {path}; create it locally, it is not part of the repository.")
    spec = importlib.util.spec_from_file_location("reference_game_resolvers", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.resolve(source, get)


def image_refs(data_text: str) -> set[str]:
    return set(re.findall(r'"((?:images|media|fonts|icons)/[^"]+?\.(?:webp|png|jpe?g|avif|otf|ttf|woff2?))"', data_text))


def fetch(source: str) -> dict:
    name = source.split(":", 1)[1].replace("/", "__")
    out = DOWNLOADS / name
    out.mkdir(parents=True, exist_ok=True)
    manifest: dict = {"source": source, "files": {}, "skipped": [], "errors": []}
    base, referer = resolve(source)
    manifest["base"] = base

    def save(rel: str) -> bytes | None:
        rel = rel.split("?", 1)[0]
        if rel.startswith(("/", "\\")) or "://" in rel or ".." in Path(rel).parts:
            manifest["skipped"].append(rel)
            return None
        target = out / rel
        if target.exists() and target.stat().st_size > 0:
            manifest["files"][rel] = target.stat().st_size
            return target.read_bytes()
        try:
            body = get(urllib.parse.urljoin(base, urllib.parse.quote(rel)), referer=referer)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            manifest["errors"].append(f"{rel}: {exc}")
            return None
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        except OSError as exc:
            manifest["errors"].append(f"{rel}: {exc}")
            return None
        manifest["files"][rel] = len(body)
        time.sleep(0.05)
        return body

    index = save("index.html") or b""
    text = index.decode("utf-8", "replace")
    manifest["made_with_construct"] = "construct" in text.lower()
    scripts = set(re.findall(r'src="([^"]+\.js)"', text))
    runtime = "c3" if "c3main" in text or "scripts/main.js" in text else ("c2" if "c2runtime" in text else "unknown")

    wanted: set[str] = set()
    offline = save("offline.json")
    if offline:
        try:
            wanted |= set(json.loads(offline)["fileList"])
        except (ValueError, KeyError) as exc:
            manifest["errors"].append(f"offline.json: {exc}")
    data = save("data.json")
    if data is None and runtime != "c3":
        data = save("data.js")
    if data:
        wanted |= image_refs(data.decode("utf-8", "replace"))
    for s in scripts:
        if not s.startswith("http"):
            wanted.add(s)
    main_js = save("scripts/main.js")
    if main_js:
        runtime = "c3"
        for s in re.findall(r'"/?([\w./-]+\.js)"', main_js.decode("utf-8", "replace")):
            if "/" not in s.strip("/"):
                s = "scripts/" + s.strip("/")
            wanted.add(s)
    for rel in sorted(wanted | OPTIONAL_SCRIPTS):
        ext = Path(rel).suffix.lower()
        if ext in SKIP_EXT or ext not in KEEP_EXT:
            manifest["skipped"].append(rel)
            continue
        save(rel)
    if runtime == "unknown" and (out / "c2runtime.js").exists():
        runtime = "c2"
    manifest["runtime"] = runtime
    manifest["errors"] = [e for e in manifest["errors"] if e.split(":", 1)[0] not in OPTIONAL_SCRIPTS]
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def main() -> None:
    for source in sys.argv[1:]:
        try:
            m = fetch(source)
            size = sum(m["files"].values())
            print(f"{source}: {m['runtime']} {len(m['files'])} files {size // 1024} KB, {len(m['skipped'])} skipped, {len(m['errors'])} errors")
        except (urllib.error.URLError, RuntimeError, TimeoutError, ValueError) as exc:
            print(f"{source}: FAILED {exc}")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

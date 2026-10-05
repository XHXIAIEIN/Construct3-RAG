"""plugin/, the Claude Code plugin: equal to a fresh build, under the directory's limits, and holding
every data and prompt file the skill's text sends an agent to (docs/decisions/plugin-folder.md)."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from scripts import build_plugin
from tests.skill_helpers import REPO, SKILL

PLUGIN = REPO / "plugin"
NAMED = re.compile(r"Construct3-RAG/((?:data|prompts)/[A-Za-z0-9_./-]*[A-Za-z0-9_/])")


def test_plugin_folder_is_a_fresh_build_under_the_limits():
    p = subprocess.run([sys.executable, str(REPO / "scripts" / "build_plugin.py"), "--check"],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr


def test_the_build_writes_text_files_with_lf_and_an_image_byte_for_byte(tmp_path, monkeypatch):
    # A checkout made before .gitattributes keeps CRLF files (docs/decisions/lf-line-endings.md)
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "plugin.json").write_bytes(b'{\r\n\t"name": "construct3"\r\n}\r\n')
    (sources / "README.md").write_bytes(b"# Construct 3\r\n\r\nA line.\r\n")
    icon = (build_plugin.SOURCES / "icon.png").read_bytes()
    # The PNG signature holds CR LF, so a build that rewrote an image would change it
    assert b"\r\n" in icon
    (sources / "icon.png").write_bytes(icon)
    monkeypatch.setattr(build_plugin, "SOURCES", sources)
    out = tmp_path / "plugin"
    build_plugin.build(out)
    assert (out / ".claude-plugin" / "plugin.json").read_bytes() == b'{\n\t"name": "construct3"\n}\n'
    assert (out / "README.md").read_bytes() == b"# Construct 3\n\nA line.\n"
    assert (out / "icon.png").read_bytes() == icon


def test_every_data_and_prompt_file_the_skill_names_is_in_the_plugin():
    """SKILL.md tells a plugin user that such a path lies under the plugin's folder, so it names a file
    there, not one that only a bundle holds."""
    texts = [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md")), SKILL / "assets" / "game-project-block.md"]
    missing, names = set(), 0
    for path in texts:
        for rel in NAMED.findall(path.read_text(encoding="utf-8")):
            names += 1
            if not (PLUGIN / rel).exists():
                missing.add(f"{path.name}: {rel}")
    assert names > 10 and not missing, sorted(missing)


def test_the_language_packs_keep_what_check_project_and_a_preview_inspector_read():
    """check_project.py reads two subtrees of each language pack. The keys of a preview's inspector values
    are paths into the name, properties and debugger texts of a plugin or behavior, such as
    behaviors.platform.debugger.vector-x (references/reading-the-runtime.md, "Inspector values")."""
    for locale in ("en-US", "zh-CN"):
        full = json.loads((REPO / "data" / "c3-lang" / f"{locale}.json").read_text(encoding="utf-8-sig"))["text"]
        kept = json.loads((PLUGIN / "data" / "c3-lang" / f"{locale}.json").read_text(encoding="utf-8"))["text"]
        assert kept["ui"]["bars"]["properties"]["project"] == full["ui"]["bars"]["properties"]["project"]
        assert kept["ui"]["bars"]["timeline"]["eases"] == full["ui"]["bars"]["timeline"]["eases"]
        for kind in ("plugins", "behaviors"):
            for addon, texts in full[kind].items():
                for part in ("name", "properties", "debugger"):
                    if part in texts:
                        assert kept[kind][addon][part] == texts[part], f"{locale}: text.{kind}.{addon}.{part}"
        assert kept["behaviors"]["platform"]["debugger"]["vector-x"]


def test_the_marketplace_installs_the_plugin_folder():
    market = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert [p["source"] for p in market["plugins"]] == ["./plugin"]
    assert not (REPO / ".claude-plugin" / "plugin.json").exists()
    assert json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["name"] == "construct3"


def test_the_listing_icon_is_a_file_of_the_plugin():
    """The directory reads the listing icon from plugin.json's "icon", a path inside the plugin, outside
    .claude-plugin/ (Claude Code docs, "Plugin manifest reference", "Directory listing fields")."""
    icon = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["icon"]
    path = (PLUGIN / icon).resolve()
    assert icon.startswith("./") and path.is_file(), icon
    assert path.is_relative_to(PLUGIN.resolve()) and ".claude-plugin" not in path.relative_to(PLUGIN.resolve()).parts


def test_scripts_in_the_plugin_read_the_bundled_data_and_print_what_opens(tmp_path):
    """A plugin user has no clone and often no Construct3-RAG line: a printed path opens as it is, and a
    declaration that only a bundle holds names the command that prints it. An example is its editor URL
    alone, since no example projects lie beside the plugin."""
    # A copy outside the repository, as Claude Code installs the plugin: no clone holds it or lies beside it
    plugin = tmp_path / "construct3"
    shutil.copytree(PLUGIN, plugin, ignore=shutil.ignore_patterns("__pycache__"))
    scripts = plugin / "skills" / "construct3-agent-plugin" / "scripts"
    # No CONSTRUCT3_RAG: the scripts find the plugin folder above them, as an installed plugin does
    env = {k: v for k, v in os.environ.items() if k != "CONSTRUCT3_RAG"}
    env.update(PYTHONIOENCODING="utf-8", CONSTRUCT3_RAG_OFFLINE="1")

    def run(script: str, *args: str) -> str:
        p = subprocess.run([sys.executable, str(scripts / script), *args], cwd=tmp_path, env=env,
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert p.returncode == 0, p.stdout + p.stderr
        return p.stdout

    out = run("lookup_script_api.py", "IRuntime.callFunction")
    assert out.startswith("IRuntime.callFunction   lookup_script_api.py IRuntime.callFunction\n"), out
    out = run("search_guides.py", "wait", "platformer")
    pitfalls = re.findall(r"^(.+\.md):\d+$", out, re.M)
    assert pitfalls and all(Path(p).is_file() and Path(p).is_relative_to(plugin) for p in pitfalls), out
    assert "\n  https://editor.construct.net/#open=3d-platformer\n" in out and "beside Construct3-RAG" not in out, out

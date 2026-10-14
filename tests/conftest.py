"""The stand-in game the skill's tests share: generated once, copied for a test that changes it."""
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from tests.skill_helpers import SKILL, run, install, new_project

# The generator's font cache, with stand-ins for Inter's three files: set before any test loads the
# template, whose HUD picks its fonts as the module loads
FONT_CACHE = Path(tempfile.mkdtemp(prefix="c3-font-cache-"))
for _name in ("Inter-Regular", "Inter-Medium", "InterDisplay-Light"):
    (FONT_CACHE / f"{_name}.woff").write_bytes(b"wOFF" + _name.encode())
os.environ["CONSTRUCT3_RAG_FONT_CACHE"] = str(FONT_CACHE)


@pytest.fixture(scope="session")
def built(tmp_path_factory) -> Path:
    root = new_project(tmp_path_factory.mktemp("coins"))
    code, out = install(root)
    assert code == 0, out
    (root / "tools").mkdir()
    shutil.copy(SKILL / "assets" / "build_project.py", root / "tools" / "build_project.py")
    code, out = run(root, "tools/build_project.py")
    assert code == 0, out
    lines = out.splitlines()
    # the pacing curve of BEATS, one line a beat, the art still to come, then the check
    assert lines[0].startswith("beat 1 intro") and lines[6].startswith("art: 1 of 1 images show their stand-in")
    assert lines[7] == "generated; checking" and lines[-1].startswith("ok:")
    return root


@pytest.fixture
def project(built, tmp_path) -> Path:
    root = tmp_path / "game"
    shutil.copytree(built, root)
    return root

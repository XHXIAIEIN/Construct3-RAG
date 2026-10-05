"""new_project.py: a project starts from the empty project the editor saves, under its own name and uniqueId."""
import json

from tests.skill_helpers import REPO, SKILL, run

SCRIPT = SKILL / "scripts" / "new_project.py"


def test_new_project_copies_the_empty_project_and_names_the_check(tmp_path):
    code, out = run(tmp_path, SCRIPT, "My Game", "--rag", str(REPO))
    game = tmp_path / "My Game"
    data = json.loads((game / "project.c3proj").read_text(encoding="utf-8"))
    template = json.loads((REPO / "data" / "c3-new-project" / "project.c3proj").read_text(encoding="utf-8"))
    assert code == 0 and data["name"] == "My Game"
    assert len(data["uniqueId"]) == 11 and data["uniqueId"] != template["uniqueId"]
    assert sorted(p.name for p in (game / "icons").iterdir()) == sorted(
        p.name for p in (REPO / "data" / "c3-new-project" / "icons").iterdir())
    assert out.rstrip().splitlines()[-1].startswith("ok: next, python ") and "check_project.py" in out


def test_new_project_leaves_a_folder_with_files_alone(tmp_path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "todo.txt").write_text("x", encoding="utf-8")
    code, out = run(tmp_path, SCRIPT, "notes", "--rag", str(REPO))
    assert code == 1 and "is not empty" in out
    assert not (tmp_path / "notes" / "project.c3proj").exists()


def test_new_project_dry_run_writes_nothing(tmp_path):
    code, out = run(tmp_path, SCRIPT, "Game", "--rag", str(REPO), "--dry-run")
    assert code == 0 and "would copy" in out and not (tmp_path / "Game").exists()

"""Compare what the skill's tools print, and what its generators write, between a git ref and the working tree.

    python scripts/output_diff.py [REF] [--only KIND ...] [--limit N] [--examples FOLDER] [--show N] [--verbose]

REF (default origin/main) is checked out with `git worktree add --detach` into
a folder of the system temp folder, which is removed afterwards. A worktree,
not an export, so that REF's scripts find the example clone beside the main
working tree as the working tree's do. The same cases then run with REF's
skill scripts and with the working tree's:

  print_sheet    print_sheet.py on every sheet of every official example
  print_layout   print_layout.py on every layout of every official example
  check_project  check_project.py on every official example
  check_style    check_project.py --style on every official example
  edit_sheet     edit_sheet.py --dry-run of a small plan on the first sheet of every official example
  lookup_ace, lookup_script_api, search_guides   a fixed list of lookups
  new_project    new_project.py into an empty folder: what it prints and every file it writes
  build_project  assets/build_project.py in a stand-in game, as the tests generate it:
                 what install.py and the generator print, and every file the generator writes

A case is `same` when exit code, stdout and stderr, or the content of a written
file, are identical on both sides once the sources of nondeterminism are pinned
or masked: the hash seed and the random module are seeded, the clone is not
fetched, HOME is an empty folder, and each side's clone and temporary folders are
replaced by <rag>, <game> and <tmp> before the comparison. The two clones' paths
differ in length, which moves the point where a script's --limit cuts a line
that holds one, so every case passes --limit 0 except lookup_ace, whose output
names no clone's path: the example folders it names lie beside the main working
tree for both sides. A refactor shows no difference; a change of output shows exactly
the cases it was meant for, and the pull request names them.

The first differing cases are printed with their first differing line, then a
count per kind; the system temp folder keeps every case in
construct3-output-diff.txt.

The official examples are read from the Construct-Example-Projects clone beside
the main working tree of this repository, or from --examples.

exit codes: 0 every case is the same; 1 a case differs; 2 bad arguments, REF is
not a commit, or the example clone is missing
"""
import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
SKILL = Path("skills/construct3-agent-plugin")
REPORT = Path(tempfile.gettempdir()) / "construct3-output-diff.txt"
EXAMPLE_KINDS = ("print_sheet", "print_layout", "check_project", "check_style", "edit_sheet")
LOOKUP_KINDS = ("lookup_ace", "lookup_script_api", "search_guides")
GENERATOR_KINDS = ("new_project", "build_project")
KINDS = EXAMPLE_KINDS + LOOKUP_KINDS + GENERATOR_KINDS
LOOKUPS = {
    "lookup_ace": [["System"], ["System", "wait"], ["System", "every"], ["System", "for", "each"],
                   ["Sprite", "animation"], ["Sprite", "aniamtion"], ["Text", "set"], ["8 Direction", "speed"],
                   ["Tween", "color"], ["Platform", "jump"], ["Array", "push"], ["Touch", "touched"],
                   ["Audio", "play"], ["Physics", "force"], ["NoSuchAddon"], ["Mouse", "set-cursor-style"],
                   ["Glow"], ["System", "wait", "--locale", "zh-CN"]],
    "lookup_script_api": [["IRuntime"], ["Timer"], ["callFunction"], ["ISpriteInstance.x"],
                          ["setAnimation", "startTimer"], ["getImageSize"], ["NoSuchName"]],
    "search_guides": [["chase", "enemy"], ["platform", "jump"], ["tween"], ["save", "load"], ["nosuchword"]],
}
# A plan every project takes: a comment, a variable and an event that uses it, at the end of its first sheet.
PLAN = [{"into": 0, "events": [
    {"eventType": "comment", "text": "output diff"}, {"eventType": "variable", "name": "DiffProbe"},
    {"eventType": "block", "conditions": [], "actions": [
        {"id": "add-to-eventvar", "objectClass": "System", "parameters": {"variable": "DiffProbe", "value": "1"}}]}]}]
# Runs a script as `python script.py` does, with the random module seeded: new_project.py draws the
# project's uniqueId from it, and a tool that starts to draw from it stays comparable.
RUNNER = ("import os, random, runpy, sys; random.seed(0); sys.argv = sys.argv[1:]; "
          "sys.path[0] = os.path.dirname(os.path.abspath(sys.argv[0])); runpy.run_path(sys.argv[0], run_name='__main__')")
EXCERPT = 160


class Side(NamedTuple):
    """One side of the comparison: the clone whose scripts run, and the folders its output is masked by."""
    label: str
    rag: Path
    tmp: Path
    env: dict[str, str]

    def masks(self) -> dict[Path, str]:
        return {self.rag: "<rag>", self.tmp / "game": "<game>", self.tmp: "<tmp>"}


class Case(NamedTuple):
    kind: str
    name: str
    args: list[str]


# --- comparison ---------------------------------------------------------------------------------------------
def spellings(path: Path) -> list[str]:
    """The ways a script may print path: as given and resolved, with either slash, and escaped inside JSON."""
    out = []
    for p in dict.fromkeys((path, path.resolve())):
        for s in (str(p), p.as_posix()):
            out += [s, s.replace("\\", "\\\\")]
            if len(s) > 1 and s[1] == ":":      # a drive letter in either case
                out += [s[0].swapcase() + s[1:], (s[0].swapcase() + s[1:]).replace("\\", "\\\\")]
    return list(dict.fromkeys(out))


def mask(text: str, masks: dict[Path, str]) -> str:
    """text with every spelling of each path replaced by its label, the longest spelling first."""
    pairs = sorted(((s, label) for path, label in masks.items() for s in spellings(path)), key=lambda p: -len(p[0]))
    for s, label in pairs:
        text = text.replace(s, label)
    return text


def first_difference(old: str, new: str) -> str | None:
    """None when old and new are the same, else the first line that differs on each side."""
    if old == new:
        return None
    a, b = old.split("\n"), new.split("\n")
    i = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))

    def at(lines: list[str]) -> str:
        return lines[i][:EXCERPT] + ("..." if len(lines[i]) > EXCERPT else "") if i < len(lines) else "(no more lines)"
    return f"line {i + 1}\n    - {at(a)}\n    + {at(b)}"


def compare(old: dict[str, str], new: dict[str, str]) -> dict[str, str | None]:
    """Each output name of either side, with None when both sides have it the same, else the first difference."""
    out = {}
    for name in sorted(old.keys() | new.keys()):
        if name not in new:
            out[name] = "only on the REF side"
        elif name not in old:
            out[name] = "only in the working tree"
        else:
            out[name] = first_difference(old[name], new[name])
    return out


# --- running --------------------------------------------------------------------------------------------------
def run(side: Side, script: Path, args: list[str], cwd: Path) -> str:
    """exit code, stdout and stderr of one run, line endings unified and paths masked."""
    p = subprocess.run([sys.executable, "-c", RUNNER, str(script), *args], cwd=cwd, env=side.env,
                       capture_output=True, timeout=300)
    out, err = (s.decode("utf-8", "replace").replace("\r\n", "\n") for s in (p.stdout, p.stderr))
    text = f"exit {p.returncode}\n{out}" + (f"\n--- stderr\n{err}" if err else "")
    return mask(text, side.masks())


def tool_output(side: Side, case: Case) -> str:
    whole = [] if case.kind == "lookup_ace" else ["--limit", "0"]
    return run(side, side.rag / SKILL / "scripts" / case.args[0], [*case.args[1:], "--rag", str(side.rag), *whole],
               side.tmp / "cwd")


def files(folder: Path, side: Side, skip: tuple[str, ...]) -> dict[str, str]:
    """Every file under folder by its path in it, masked text, or a digest line for a file that is not UTF-8."""
    out = {}
    for p in sorted(folder.rglob("*")):
        rel = p.relative_to(folder).as_posix()
        if not p.is_file() or rel.split("/")[0] in skip:
            continue
        data = p.read_bytes()
        try:
            out[rel] = mask(data.decode("utf-8").replace("\r\n", "\n"), side.masks())
        except UnicodeDecodeError:
            out[rel] = f"binary, {len(data)} bytes, sha256 {hashlib.sha256(data).hexdigest()}"
    return out


def new_project(side: Side) -> dict[str, str]:
    game = side.tmp / "game"
    shutil.rmtree(game, ignore_errors=True)
    script = side.rag / SKILL / "scripts" / "new_project.py"
    outputs = {"new_project run": run(side, script, [str(game), "--rag", str(side.rag)], side.tmp / "cwd")}
    if game.is_dir():
        outputs.update({f"new_project file {rel}": text for rel, text in files(game, side, (".git",)).items()})
    return outputs


def build_project(side: Side) -> dict[str, str]:
    """The stand-in game of tests/conftest.py: a project the editor never saved, the skill installed, the
    template copied to tools/build_project.py and run."""
    game = side.tmp / "game"
    shutil.rmtree(game, ignore_errors=True)
    game.mkdir()
    (game / "project.c3proj").write_text(json.dumps({"uniqueId": "test", "properties": {}}), encoding="utf-8")
    outputs = {"build_project install": run(side, side.rag / SKILL / "scripts" / "install.py", [], game)}
    template = side.rag / SKILL / "assets" / "build_project.py"
    if template.exists():
        (game / "tools").mkdir()
        shutil.copy(template, game / "tools" / "build_project.py")
        outputs["build_project run"] = run(side, game / "tools" / "build_project.py", [], game)
    outputs.update({f"build_project file {rel}": text
                    for rel, text in files(game, side, (".agents", ".git", "tools")).items()})
    return outputs


GENERATORS = {"new_project": new_project, "build_project": build_project}


# --- the matrix -----------------------------------------------------------------------------------------------
def listed(project: Path, kind: str) -> list[str]:
    """The names project.c3proj lists under kind ("eventSheets", "layouts"), subfolders included."""
    def names(folder: dict) -> list[str]:
        return list(folder.get("items", [])) + [n for sub in folder.get("subfolders", []) for n in names(sub)]
    return names(json.loads((project / "project.c3proj").read_text(encoding="utf-8-sig")).get(kind, {}))


def cases(kinds: list[str], projects: list[Path], plan: Path) -> list[Case]:
    out = []
    for p in projects:
        at = ["--project", str(p)]
        sheets = listed(p, "eventSheets")
        if "print_sheet" in kinds:
            out += [Case("print_sheet", f"{p.name}/{s}", ["print_sheet.py", s, *at]) for s in sheets]
        if "print_layout" in kinds:
            out += [Case("print_layout", f"{p.name}/{lay}", ["print_layout.py", lay, *at])
                    for lay in listed(p, "layouts")]
        if "check_project" in kinds:
            out.append(Case("check_project", p.name, ["check_project.py", *at]))
        if "check_style" in kinds:
            out.append(Case("check_style", p.name, ["check_project.py", "--style", *at]))
        if "edit_sheet" in kinds and sheets:
            out.append(Case("edit_sheet", p.name, ["edit_sheet.py", sheets[0], str(plan), "--dry-run", *at]))
    for kind in LOOKUP_KINDS:
        if kind in kinds:
            out += [Case(kind, " ".join(words), [f"{kind}.py", *words]) for words in LOOKUPS[kind]]
    return out


def examples_folder(given: str | None) -> Path:
    """--examples, else Construct-Example-Projects/example-projects beside the main working tree."""
    if given:
        return Path(given).resolve()
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir")
    main = Path(common).parent if common else ROOT
    return main.parent / "Construct-Example-Projects" / "example-projects"


def git(*args: str) -> str | None:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    return p.stdout.strip() if p.returncode == 0 else None


def environment(home: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("CONSTRUCT3_RAG", "PYTHONSTARTUP")}
    env.update(PYTHONIOENCODING="utf-8", PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1",
               CONSTRUCT3_RAG_OFFLINE="1", HOME=str(home), USERPROFILE=str(home))
    return env


def side_at(label: str, rag: Path, tmp: Path) -> Side:
    folder = tmp / label
    for sub in ("cwd", "home"):
        (folder / sub).mkdir(parents=True)
    return Side(label, rag, folder, environment(folder / "home"))


def remove(folder: Path) -> None:
    def writable(func, path, _exc) -> None:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    shutil.rmtree(folder, onexc=writable)


def compare_sides(args: argparse.Namespace, old: Side, new: Side, projects: list[Path], tmp: Path) -> list[tuple]:
    """(kind, name, difference or None) for every case, in the order of the matrix."""
    plan = tmp / "plan.json"
    plan.write_text(json.dumps(PLAN), encoding="utf-8")
    matrix = cases(args.only, projects, plan)

    def one(case: Case) -> tuple:
        return case.kind, case.name, first_difference(tool_output(old, case), tool_output(new, case))
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for kind in (k for k in GENERATOR_KINDS if k in args.only):
            o, n = pool.map(GENERATORS[kind], (old, new))
            results += [(kind, name.split(" ", 1)[1], diff) for name, diff in compare(o, n).items()]
        results += list(pool.map(one, matrix))
    return results


def report(results: list[tuple], args: argparse.Namespace, ref: str, seconds: float) -> int:
    lines, shown = [], 0
    for kind, name, diff in results:
        if diff is None:
            lines.append(f"same     {kind} {name}")
            continue
        lines.append(f"differs  {kind} {name}: {diff}")
    differing = [line for line in lines if line.startswith("differs")]
    for line in lines:
        if line.startswith("differs") and shown < args.show:
            print(line)
            shown += 1
        elif args.verbose and line.startswith("same"):
            print(line)
    counts: dict[str, list[int]] = {}
    for kind, _name, diff in results:
        counts.setdefault(kind, [0, 0])[diff is not None] += 1
    print("; ".join(f"{kind} {s} same{f', {d} differ' if d else ''}" for kind, (s, d) in counts.items()))
    if len(differing) > shown:
        print(f"-- {len(differing) - shown} more cases differ; --show N prints more")
    try:
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"every case and its first difference: {REPORT}")
    except OSError as exc:
        print(f"the full list was not written to {REPORT}: {exc}")
    print(f"{len(results)} cases, {len(results) - len(differing)} same, {len(differing)} differ: {ref} against the "
          f"working tree, {seconds:.0f} s")
    return 1 if differing else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ref", nargs="?", default="origin/main", help="the commit to compare with (default: origin/main)")
    ap.add_argument("--only", nargs="+", choices=KINDS, metavar="KIND", help=f"only these kinds: {', '.join(KINDS)}")
    ap.add_argument("--limit", type=int, metavar="N", help="only the first N official examples, by folder name")
    ap.add_argument("--examples", metavar="FOLDER", help="the example-projects folder of Construct-Example-Projects")
    ap.add_argument("--show", type=int, default=40, metavar="N", help="differing cases printed (default: 40)")
    ap.add_argument("--verbose", action="store_true", help="print the cases that are the same as well")
    ap.add_argument("--workers", type=int, default=min(16, os.cpu_count() or 4), help="runs in parallel")
    args = ap.parse_args()
    args.only = args.only or list(KINDS)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not shutil.which("git"):
        print("git is not on PATH; install Git, then run this again", file=sys.stderr)
        return 2
    sha = git("rev-parse", "--verify", "--quiet", f"{args.ref}^{{commit}}")
    if not sha:
        print(f"{args.ref} is not a commit of this repository; pass a branch, tag or commit, such as HEAD~1",
              file=sys.stderr)
        return 2
    projects: list[Path] = []
    if any(k in EXAMPLE_KINDS for k in args.only):
        folder = examples_folder(args.examples)
        projects = [p.parent for p in sorted(folder.glob("*/project.c3proj"))][: args.limit]
        if not projects:
            print(f"no official example at {folder}: clone https://github.com/Scirra/Construct-Example-Projects "
                  f"beside this repository, pass --examples <its example-projects folder>, or leave the example "
                  f"kinds out with --only {' '.join(LOOKUP_KINDS + GENERATOR_KINDS)}", file=sys.stderr)
            return 2
    ref = f"{args.ref} ({sha[:7]})"
    start = time.monotonic()
    tmp = Path(tempfile.mkdtemp(prefix="construct3-output-diff-"))
    checkout = tmp / "ref"
    try:
        if git("worktree", "add", "--detach", "--quiet", str(checkout), sha) is None:
            print(f"git worktree add of {ref} into {checkout} failed", file=sys.stderr)
            return 2
        old, new = side_at("old", checkout, tmp), side_at("new", ROOT, tmp)
        print(f"comparing {ref} with the working tree: {len(projects)} official examples, {', '.join(args.only)}")
        sys.stdout.flush()
        results = compare_sides(args, old, new, projects, tmp)
    finally:
        git("worktree", "remove", "--force", str(checkout))
        if tmp.exists():
            remove(tmp)
        git("worktree", "prune")
    return report(results, args, ref, time.monotonic() - start)


if __name__ == "__main__":
    sys.exit(main())

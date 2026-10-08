"""What the scripts of this skill share: finding the project and the
Construct3-RAG clone, reading the files project.c3proj lists, the schemas,
the object model (types, families, behaviors, instance variables), the
schema entry behind a condition or an action, what the editor has
deprecated, and the helpers of a game's generator against the template's.

Not a command. check_project.py, print_sheet.py and lookup_ace.py import it
from the folder they sit in.
"""
import argparse
import ast
import difflib
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from typing import NamedTuple

SKILL = "construct3-agent-plugin"
SKILL_DIR = Path(__file__).resolve().parent.parent
# The end of every "no project.c3proj" message: where a project comes from when there is none yet
START_ONE = f"; to start a new project, run python {(SKILL_DIR / 'scripts' / 'new_project.py').as_posix()} <folder>"
LOWER = str.lower  # expressions are case-insensitive: scrolly, SCROLLY and ScrollY are one name

# An agent's harness cuts tool output somewhere between ten and thirty thousand
# characters, not always at the end and not always saying so. The scripts stop
# below that by themselves and say how to ask for the rest.
LIMIT = 10_000

# --review: the line print_sheet.py and check_project.py end with when the project is someone else's to
# review. Asked in the system prompt alone, a model listed design choices as "not wrong", a warning on an
# omitted parameter and a reset that another event already did; at the end of the tool output it did not.
REVIEW = ("review: say first what the project does. Name a problem only when the events, read together, stop "
          "something from working; before calling a step missing, look for another event that does it. Give a "
          "fix as the final steps to take, stated as what to do. Leave out what works, design choices, what is not wrong, what the "
          "person might check, and warnings that do not stop the project opening or running.")

# The editor numbers these in document order, sub-events included, one
# sequence per sheet. A variable, comment or include takes no number of its
# own: the margin leaves it blank and Find files it under the next numbered
# event, so every row's number is the count of numbered rows before it plus one.
NUMBERED = ("block", "group", "function-block", "custom-ace-block", "script")

# A text literal of an expression: a quote inside it is written twice, "say ""hi""".
STRING_LITERAL = re.compile(r'"(?:[^"]|"")*"')

# A comment or a string in a JavaScript or TypeScript file.
# The leftmost match wins, so // inside a string is not a comment.
SCRIPT_TEXT = re.compile(r"//[^\n]*|/\*.*?\*/|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`", re.S)
# A number written as a literal, not the digits of a name, a hex number or an exponent.
SCRIPT_NUMBER = re.compile(r"(?<![\w.$])(?:\d+(?:\.\d+)?|\.\d+)(?![\w.])")

# What a deprecated addon or ACE is, in the words of the Addon SDK reference
# (SetIsDeprecated, isDeprecated, is-deprecated).
DEPRECATED = "Construct 3 no longer offers it and keeps it only so that old projects open"

# The ACEs of the built-in Functions object. The System schema holds them, and a
# project writes them under the name project.c3proj gives in functionsName: the
# official examples write "objectClass": "Functions" for all 216 Set return value
# and all 17 function map actions, never "System".
FUNCTIONS_ACES = {"set-function-return-value"}
FUNCTIONS_CATEGORY = "function-maps"


def is_functions_ace(it: dict) -> bool:
    """Whether a System schema entry belongs to the built-in Functions object."""
    return it.get("id") in FUNCTIONS_ACES or it.get("category") == FUNCTIONS_CATEGORY


class Findings:
    """Errors fail the run; warnings are printed and do not. Each is kept once.
    A style finding is a warning that also keeps its kind, so that edit_sheet.py
    can refuse a plan for the kinds whose fix is one comment or one deleted condition."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.style: list[tuple[str, str]] = []      # (kind, message), kind one of check_project.check_style's or a trap's: pathfinding, timer, control, count, picked, flip, flip-once, undone

    def err(self, msg: str) -> None:
        if msg not in self.errors:
            self.errors.append(msg)

    def warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)

    def style_finding(self, kind: str, msg: str) -> None:
        if msg not in self.warnings:
            self.style.append((kind, msg))
        self.warn(msg)


def stop_with_a_sentence(script: str, findings: Findings) -> None:
    """A file that lacks a key the editor always writes stops the run; say which
    key and where the script was, instead of a traceback."""
    def stopped(exc_type, exc, tb) -> None:
        while tb.tb_next:
            tb = tb.tb_next
        what = f"missing key {exc}" if exc_type is KeyError else f"{exc_type.__name__}: {exc}"
        code = tb.tb_frame.f_code
        print(f"{script} stopped at {Path(code.co_filename).name} line {tb.tb_lineno} ({code.co_name}): {what}. "
              f"A project file lacks a key the editor always writes, or holds a value of another type than the "
              f"editor writes; compare it with a file assets/build_project.py generates, or with an official example.")
        for w in findings.warnings:
            print(f"warning: {w}")
        if findings.errors:
            print("\n".join(findings.errors))
        sys.stdout.flush()
        os._exit(2)     # sys.exit would raise inside the hook and print a second traceback

    sys.excepthook = stopped


def utf8_output() -> None:
    """The harness reads a script's pipe as UTF-8. A piped Python on Windows
    writes the ANSI code page instead: under cp936 Chinese names and comments
    arrive as mojibake, and cp1252 cannot encode them at all. An encoding the
    caller chose with PYTHONIOENCODING is kept, without the crash."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            if "PYTHONIOENCODING" in os.environ:
                stream.reconfigure(errors="replace")
            else:
                stream.reconfigure(encoding="utf-8", errors="replace")


def fitting(lines: list[str], limit: int) -> int:
    """How many of lines print within limit characters; all of them when limit is 0."""
    if not limit:
        return len(lines)
    used = 0
    for n, line in enumerate(lines):
        used += len(line) + 1
        if used > limit:
            return n
    return len(lines)


def load(path: Path):
    """A JSON file; one that starts with a byte order mark reads too, as the editor opens it."""
    try:
        with path.open(encoding="utf-8-sig") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"{path}: not valid JSON, line {e.lineno} column {e.colno}: {e.msg}")


def data_texts(rag: Path, folder: str, pattern: str) -> dict[str, str]:
    """The files of a data folder whose name matches pattern, as text by their path inside it.
    The clone keeps the files; the Claude Code plugin keeps them in bundles beside the folder,
    <folder>.bundle-<n>.json, each a JSON object from that path to the text (docs/decisions/plugin-folder.md)."""
    root = rag / folder
    out: dict[str, str] = {}
    for bundle in sorted(root.parent.glob(f"{root.name}.bundle-*.json")):
        out.update(load(bundle))
    if root.is_dir():
        out.update({p.relative_to(root).as_posix(): p.read_text(encoding="utf-8-sig", errors="replace")
                    for p in root.rglob(pattern) if p.is_file()})
    return {k: out[k] for k in sorted(out) if PurePosixPath(k).match(pattern)}


def squash(s: str) -> str:
    """Letters and digits only, lowercased: 'Set animation', 'SetAnimation' and 'set-animation' are one key."""
    return re.sub(r"[\W_]+", "", str(s).lower())


def closest(word: str, options, n: int = 3) -> str:
    """'; closest: a, b' for an error message, or '' when nothing is near."""
    table = {squash(o): o for o in options}
    hits = difflib.get_close_matches(squash(word), list(table), n=n, cutoff=0.6)
    return "; closest: " + ", ".join(table[h] for h in hits) if hits else ""


def describe(cond: dict) -> str:
    return f"{cond.get('objectClass')}:{cond.get('id')}"


def folder_items(folder: dict, prefix: Path = Path()) -> list[tuple[str, Path]]:
    """(name, relative folder) for every item of a project.c3proj folder tree."""
    out = [(name, prefix) for name in folder.get("items", [])]
    for sub in folder.get("subfolders", []):
        out += folder_items(sub, prefix / sub["name"] if sub.get("name") else prefix)
    return out


def folder_entries(folder: dict) -> list[dict]:
    """The entries of a folder tree whose items are objects, subfolders included."""
    return [i for i in folder.get("items", []) if isinstance(i, dict)] + [
        i for sub in folder.get("subfolders", []) if isinstance(sub, dict) for i in folder_entries(sub)]


def numbered_events(events: list) -> Iterator[dict]:
    """Every numbered event in document order, sub-events included: the n-th is event n of the
    sheet, so print_sheet.py and edit_sheet.py name the same event by the same number."""
    for ev in events:
        if ev.get("eventType") in NUMBERED:
            yield ev
        yield from numbered_events(ev.get("children", []))


def layers_of(layers: list, depth: int = 0) -> Iterator[tuple[dict, int]]:
    """(layer, depth) of a layout's layers bottom to top, a sublayer above the layer that holds it."""
    for layer in layers:
        yield layer, depth
        yield from layers_of(layer.get("subLayers", []), depth + 1)


def box(world: dict) -> tuple[float, float, float, float]:
    """left, top, right, bottom of an unrotated instance, from its origin. The editor writes
    originX and originY on every instance; one without them is read as centred."""
    w, h = world.get("width", 0), world.get("height", 0)
    left = world.get("x", 0) - w * world.get("originX", 0.5)
    top = world.get("y", 0) - h * world.get("originY", 0.5)
    return left, top, left + w, top + h


# --- locate the project and the clone ---------------------------------------------
def above(start: Path, marker: str) -> Path | None:
    """The nearest folder at or above start that holds marker."""
    for folder in (start, *start.parents):
        if (folder / marker).exists():
            return folder
    return None


def find_project(given: str | None) -> Path | None:
    """--project, else the project the current directory is in, else the one
    this copy of the skill is installed in."""
    if given:
        return Path(given).resolve()
    return above(Path.cwd(), "project.c3proj") or above(SKILL_DIR, "project.c3proj")


def rag_line(text: str) -> str | None:
    """The path on the `Construct3-RAG:` line of an instruction file. The line
    may spell the folder out or keep `<path-to>` and define it once above, as
    `path-to = D:\\GitHub` or `<path-to>: D:/GitHub`; a path may hold spaces."""
    m = re.search(r"^[ \t>*-]*Construct3-RAG\s*[:=][ \t]*(.+)$", text, re.M)
    if not m:
        return None
    value = m.group(1).strip().strip("`\"'")
    if "<path-to>" in value:
        base = re.search(r"^[ \t>*-]*<?path-to>?\s*[:=][ \t]*(.+)$", text, re.M)
        if not base:
            return None
        value = value.replace("<path-to>", base.group(1).strip().strip("`\"'").rstrip("\\/"))
    return None if "<" in value else value


def is_clone(folder: Path) -> bool:
    return (folder / "data" / "c3-schemas" / "_index.json").exists()


def clone_root(rag: Path) -> Path:
    """The clone that holds rag: its parent when rag is the plugin/ folder of a clone, else rag itself.
    A clone's plugin/ folder, linked into ~/.claude/skills/ as the Claude Code plugin, is where the scripts
    find data/. The sibling clones lie beside the clone, not beside plugin/."""
    return rag.parent if rag.name == "plugin" and is_clone(rag.parent) else rag


def siblings_folder(rag: Path) -> Path:
    """The folder that holds the sibling clones, Construct-Example-Projects among them: the parent of the clone
    that holds rag. A git worktree lies inside the clone it belongs to, so for a worktree it is the parent of
    the main working tree. The worktree's .git file points to its git folder. The commondir file in that folder
    points to the main .git folder, whose parent is the main working tree."""
    clone = clone_root(rag)
    try:
        link = (clone / ".git").read_text(encoding="utf-8") if (clone / ".git").is_file() else ""
        gitdir = clone / link.partition("gitdir:")[2].strip()    # absolute, or relative to the worktree
        common = gitdir / "commondir"
        main = (gitdir / common.read_text(encoding="utf-8").strip()).resolve() if link and common.is_file() else None
    except OSError:
        main = None
    return main.parent.parent if main and main.name == ".git" else clone.parent


EXAMPLES_CLONE = "Construct-Example-Projects"
EXAMPLES_URL = "https://github.com/Scirra/Construct-Example-Projects"


def examples_clone_command(rag: Path | None) -> str:
    """The command that puts the examples clone where the scripts look for it: the clone's bootstrap.py,
    or the git clone itself from a plugin that holds no bootstrap.py."""
    if rag is None:
        return "python <Construct3-RAG>/scripts/bootstrap.py"
    bootstrap = clone_root(rag) / "scripts" / "bootstrap.py"
    if bootstrap.is_file():
        return f"python {bootstrap.as_posix()}"
    return f'git clone --depth 1 {EXAMPLES_URL} "{(siblings_folder(rag) / EXAMPLES_CLONE).as_posix()}"'


def missing_example(folder: Path, override: str | None) -> str | None:
    """Why --project names no project when it is a folder of the examples clone that is not there, with
    the next step: the clone to get, or the search that lists the examples. None for any other folder."""
    parts = [p.lower() for p in folder.parts]
    if folder.exists() or EXAMPLES_CLONE.lower() not in parts:
        return None
    clone = Path(*folder.parts[:parts.index(EXAMPLES_CLONE.lower()) + 1])
    if clone.is_dir():
        return (f"no example project at {folder}; python {(SKILL_DIR / 'scripts' / 'search_guides.py').as_posix()} "
                f"WORD lists the examples that hold a word, each with the folder to read")
    rag = locate_rag(None, override)[0]
    into = f" into {siblings_folder(rag) / EXAMPLES_CLONE}" if rag else ""
    return (f"no example project at {folder}: the {EXAMPLES_CLONE} clone is not at {clone}; "
            f"{examples_clone_command(rag)} clones it{into}")


def locate_rag(root: Path | None, override: str | None) -> tuple[Path | None, list[str]]:
    """The clone or None, and the places tried before it; for a script that runs without a clone."""
    tried = []
    candidates = [("--rag", override), ("CONSTRUCT3_RAG", os.environ.get("CONSTRUCT3_RAG"))]
    # The project being read, then the one this copy of the skill is installed in:
    # an official example printed from a game project has no instruction file of its own.
    folders = (root, Path.cwd(), above(SKILL_DIR, "project.c3proj"))
    for folder in dict.fromkeys(f for f in folders if f):
        for name in ("CLAUDE.md", "AGENTS.md"):
            f = folder / name
            if f.exists():
                candidates.append((str(f), rag_line(f.read_text(encoding="utf-8"))))
    for source, c in candidates:
        if not c:
            continue
        if is_clone(Path(c)):
            return Path(c), tried
        tried.append(f"{source}: {c}")
    # Run in place, from <Construct3-RAG>/skills/, the clone is the script's own.
    return above(SKILL_DIR, "data/c3-schemas/_index.json"), tried


def find_rag(root: Path | None, override: str | None) -> Path:
    rag, tried = locate_rag(root, override)
    if rag:
        return rag
    sys.exit("Construct3-RAG not found. Pass --rag <folder>, set CONSTRUCT3_RAG, or write the line "
             "'- Construct3-RAG: <folder>' in the project's AGENTS.md or CLAUDE.md; the folder is the "
             "one that holds data/c3-schemas/_index.json."
             + ("\nTried " + "; ".join(tried) if tried else ""))


def skill_files(skill_dir: Path) -> dict[str, Path]:
    """The files a copy of the skill consists of, by their path inside it.
    evals/ tests the skill from the clone and is not part of a copy."""
    files = {p.relative_to(skill_dir).as_posix(): p for p in sorted(skill_dir.rglob("*"))
             if p.is_file() and "__pycache__" not in p.parts}
    return {rel: p for rel, p in files.items() if not rel.startswith("evals/")}


STAMPS = Path(tempfile.gettempdir()) / "construct3-sheet-stamps"


def stamp_of(sheet: Path) -> Path:
    return STAMPS / hashlib.sha1(str(sheet.resolve()).lower().encode()).hexdigest()[:20]


def stamp(sheet: Path) -> None:
    """Keep the hash of a sheet as print_sheet.py printed it or edit_sheet.py wrote it,
    outside the project, so that edit_sheet.py notices a save in between."""
    try:
        STAMPS.mkdir(exist_ok=True)
        draft = stamp_of(sheet).with_suffix(f".{os.getpid()}")
        draft.write_text(hashlib.sha1(sheet.read_bytes()).hexdigest(), encoding="ascii")
        os.replace(draft, stamp_of(sheet))
    except OSError:
        pass


def changed_since_stamp(sheet: Path) -> bool:
    try:
        return stamp_of(sheet).read_text(encoding="ascii") != hashlib.sha1(sheet.read_bytes()).hexdigest()
    except OSError:     # never printed: nothing to compare with
        return False


def same_text(a: Path, b: Path) -> bool:
    """Line endings aside: a checkout may convert them."""
    return a.read_bytes().replace(b"\r\n", b"\n") == b.read_bytes().replace(b"\r\n", b"\n")


def refresh_command(rag: Path) -> str | None:
    """The command that makes this copy of the skill the clone's again; None when
    the scripts run from the clone itself."""
    source = rag / "skills" / SKILL
    if not (source / "SKILL.md").exists() or source.resolve() == SKILL_DIR:
        return None
    return f"python \"{source / 'scripts' / 'install.py'}\" --into \"{SKILL_DIR.parent}\""


def skill_drift(rag: Path) -> str | None:
    """A sentence when this copy of the skill, installed in a game project, is
    not what the clone holds. The clone is the source; install.py refreshes the copy."""
    refresh = refresh_command(rag)
    if not refresh:
        return None
    wanted, have = skill_files(rag / "skills" / SKILL), skill_files(SKILL_DIR)
    changed = [rel for rel, path in wanted.items() if rel not in have or not same_text(path, have[rel])]
    changed += [rel for rel in have if rel not in wanted]
    if not changed:
        return None
    return (f"this copy of the {SKILL} skill differs from the clone's ({', '.join(changed[:4])}"
            f"{' ...' if len(changed) > 4 else ''}); refresh it: {refresh}")


def note_drift(rag: Path) -> None:
    """Print skill_drift's sentence as a note, when there is one."""
    drift = skill_drift(rag)
    if drift:
        print(f"note: {drift}")


FETCH_STAMPS = Path(tempfile.gettempdir()) / "construct3-rag-fetch"
FETCH_EVERY = 3600          # seconds between two fetches of one clone
FETCH_WAIT = 8              # seconds a fetch may take before the check goes on without it


def git_out(rag: Path, *args: str, wait: float = 5) -> str | None:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    try:
        p = subprocess.run(["git", "-C", str(rag), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=wait, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout.strip() if p.returncode == 0 else None


def offline() -> bool:
    """CONSTRUCT3_RAG_OFFLINE=1: the clone is neither fetched nor compared with its upstream. Only "1"
    sets it, so that 0 or an empty value keeps the check."""
    return os.environ.get("CONSTRUCT3_RAG_OFFLINE") == "1"


def clone_behind(rag: Path) -> tuple[str, bool] | None:
    """A sentence when the clone's branch is behind its upstream, and whether the
    agent updates it. A clone with no commits or changes of its own fast-forwards:
    the sentence gives the fast-forward to the fetched upstream, which needs no network,
    and, for a copy of the skill, its refresh. A clone that holds the user's work is
    the user's to update. The clone is fetched at most every FETCH_EVERY seconds;
    offline(), or with no upstream, nothing is said."""
    rag = clone_root(rag)
    if offline() or not (rag / ".git").exists() or not shutil.which("git"):
        return None
    upstream = git_out(rag, "rev-parse", "--abbrev-ref", "@{u}")
    if not upstream:        # detached, or a branch that tracks nothing
        return None
    stamp_file = FETCH_STAMPS / hashlib.sha1(str(rag.resolve()).lower().encode()).hexdigest()[:20]
    try:
        due = time.time() - stamp_file.stat().st_mtime > FETCH_EVERY
    except OSError:
        due = True
    if due:
        # Stamped before the fetch, so that an offline machine waits once per period, not on every check
        try:
            FETCH_STAMPS.mkdir(exist_ok=True)
            stamp_file.touch()
        except OSError:
            pass
        git_out(rag, "fetch", "--quiet", upstream.split("/")[0], wait=FETCH_WAIT)
    try:
        ahead, behind = (int(n) for n in git_out(rag, "rev-list", "--left-right", "--count", "HEAD...@{u}").split())
    except (AttributeError, ValueError):
        return None
    if not behind:
        return None
    lag = f"Construct3-RAG at {rag} is {behind} commit{'s' if behind != 1 else ''} behind {upstream}"
    own = [f"{ahead} commit{'s' if ahead != 1 else ''}"] if ahead else []
    if git_out(rag, "status", "--porcelain", "--untracked-files=no"):
        own.append("uncommitted changes")
    if own:
        return f"{lag}, and it holds {' and '.join(own)} of its own; tell the user, who decides how to update it", False
    refresh = refresh_command(rag)
    return (f"{lag}, so the scripts lack the fixes and checks of those commits. Run git -C \"{rag}\" merge --ff-only {upstream}, "
            f"{f'then {refresh}, ' if refresh else ''}then run this check again"), True


def project_file(root: Path, kind: str, name: str, folder: Path) -> Path | None:
    """The JSON file for a listed item. Older projects keep the files flat even
    when project.c3proj has subfolders, so fall back to a search by name."""
    direct = root / kind / folder / f"{name}.json"
    if direct.exists():
        return direct
    hits = [p for p in (root / kind).rglob(f"{name}.json") if not p.name.endswith(".uistate.json")]
    return hits[0] if hits else None


def listed_files(root: Path, data: dict, kind: str) -> dict[str, Path | None]:
    """The file of every item project.c3proj lists under kind; None for one that has no file."""
    return {name: project_file(root, kind, name, folder) for name, folder in folder_items(data.get(kind, {}))}


# --- the strings a web export ships -------------------------------------------------------
# A web export ships every string of the events, the scripts and the project files to every player, who
# can read it in the browser's tools, so every player can read a key there. The shapes below are the keys
# of common services, and the first matching shape names the key. A random-looking token in a text
# literal, 32 to 512 letters, digits and -_+/=, is the key of some other service; a longer one is data.
# ALLOW on the line, in the comment above the event or in a variable's comment marks a key meant to be
# public.
# Evidence: docs/decisions/secret-scan.md.
KEY_SHAPES = (
    (re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"), "an Anthropic API key"),
    (re.compile(r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{32,}"), "an OpenAI API key"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}"), "a Google API key"),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "an AWS access key"),
    (re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})"), "a GitHub token"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "a Slack token"),
    (re.compile(r"\b[rs]k_live_[0-9A-Za-z]{20,}"), "a Stripe secret key"),
    (re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"), "a private key"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "a signed token (JWT)"),
)
TOKEN = re.compile(r"(?<![\w+/=-])[A-Za-z0-9+/=_-]{32,512}(?![\w+/=-])")
DATA_URI = re.compile(r"data:[\w/+.-]*;base64,[A-Za-z0-9+/=]*")
URL = re.compile(r"\b(?:https?|wss?)://([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)(?::\d+)?([^\s\"'`<>?#]*)", re.I)
LOCAL_HOSTS = re.compile(r"localhost|127(?:\.\d+){3}|0\.0\.0\.0", re.I)
WORDS = re.compile(r"(?:[A-Z]?[a-z]{2,}|[A-Z]{2,}|\d{1,3})+")      # a name: CamelCase words and short numbers
JS_LITERAL = re.compile(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`")
ALLOW = "allow-secret"
TEXT_FILES = (".json", ".txt", ".csv", ".tsv", ".xml", ".html", ".htm", ".md", ".yaml", ".yml", ".ini", ".cfg")
SCRIPT_FILES = (".js", ".mjs", ".ts")


class Shipped(NamedTuple):
    place: str      # sheet Game event 5 action 2, scripts/main.js line 12, files/config.json line 3
    text: str
    allowed: bool   # marked ALLOW where the place can carry a mark
    mark: str       # where an ALLOW goes for this place
    literals: re.Pattern | None = None     # code: the text literals in it hold its strings

    def strings(self) -> list[str]:
        """The text of the strings it holds: its literals in code, else all of it."""
        if self.literals is None:
            return [self.text]
        return [m.group(0)[1:-1] for m in self.literals.finditer(self.text)]


def shipped_strings(root: Path, data: dict, sheets: dict[str, dict]) -> Iterator[Shipped]:
    """Every string a web export of the project ships: the parameters of conditions and actions, the values
    of variables and the lines of scripts in the sheets, the lines of the script files and of the text files
    project.c3proj lists. Comments, group descriptions and names stay in the editor."""
    above = "the comment above the event"

    def values(obj) -> Iterator[str]:
        if isinstance(obj, str):
            yield obj
        elif isinstance(obj, dict):
            for v in obj.values():
                yield from values(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from values(v)

    def script_lines(script) -> list[str]:
        return script.splitlines() if isinstance(script, str) else [str(s) for s in script or []]

    def walk(sheet: str, events: list, counter: list[int]) -> Iterator[Shipped]:
        noted = ""      # the comments right above the next event
        for ev in events:
            et = ev.get("eventType")
            if et == "comment":
                noted += str(ev.get("text", ""))
                continue
            allowed = ALLOW in noted
            noted = ""
            if et in NUMBERED:
                counter[0] += 1
            where = f"sheet {sheet} event {counter[0]}"
            if et == "variable":
                for text in values(ev.get("initialValue")):
                    yield Shipped(f"sheet {sheet} variable {ev.get('name')}", text,
                                  allowed or ALLOW in str(ev.get("comment", "")), "its comment")
            if et == "script":
                for n, line in enumerate(script_lines(ev.get("script")), 1):
                    yield Shipped(f"{where} script line {n}", line, allowed or ALLOW in line,
                                  "a comment on that line", JS_LITERAL)
            for kind in ("conditions", "actions"):
                for n, ace in enumerate(ev.get(kind) or [], 1):
                    if not isinstance(ace, dict) or ace.get("type") == "comment":
                        continue
                    place = f"{where} {kind[:-1]} {n}"
                    if ace.get("type") == "script":
                        for k, line in enumerate(script_lines(ace.get("script")), 1):
                            yield Shipped(f"{place} line {k}", line, allowed or ALLOW in line,
                                          "a comment on that line", JS_LITERAL)
                    for text in values(ace.get("parameters")):
                        yield Shipped(place, text, allowed, above, STRING_LITERAL)
            yield from walk(sheet, ev.get("children") or [], counter)

    for name, sheet in sheets.items():
        if isinstance(sheet, dict):
            yield from walk(name, sheet.get("events") or [], [0])
    folders = data.get("rootFileFolders") or {}
    for kind, folder in (("script", "scripts"), ("general", "files")):
        for item, sub in folder_items(folders.get(kind) or {}):
            name = item.get("name") if isinstance(item, dict) else item
            path = root / folder / sub / str(name)
            code = path.suffix.lower() in SCRIPT_FILES
            if not isinstance(name, str) or not (code or path.suffix.lower() in TEXT_FILES) or not path.is_file() \
                    or path.stat().st_size > 4_000_000:
                continue
            rel = (Path(folder) / sub / name).as_posix()
            for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                yield Shipped(f"{rel} line {n}", line, ALLOW in line,
                              "a comment on that line" if code else "that line", JS_LITERAL if code else None)


def entropy(text: str) -> float:
    """Bits per character of text, from how often each character comes."""
    counts: dict[str, int] = {}
    for c in text:
        counts[c] = counts.get(c, 0) + 1
    return -sum(n / len(text) * math.log2(n / len(text)) for n in counts.values())


def key_shape(s: Shipped) -> tuple[str, str] | None:
    """The kind of key a shipped string holds, and the key's first characters; None when it holds none."""
    for pattern, what in KEY_SHAPES:
        m = pattern.search(s.text)
        if m:
            return what, m.group(0)[:6] + "…"
    for text in s.strings():
        bare = URL.sub(" ", DATA_URI.sub(" ", text))     # an address up to its query, a picture in a data URI
        for m in TOKEN.finditer(bare):
            token = m.group(0)
            # A key mixes letters and digits and repeats some characters; an alphabet written out does not,
            # and a name such as Draco_Float32Array_GetValue_1 is words and short numbers
            if not (re.search(r"\d", token) and re.search(r"[A-Za-z]", token)) or len(set(token)) == len(token) \
                    or all(WORDS.fullmatch(part) for part in re.split(r"[_-]+", token) if part):
                continue
            if re.fullmatch(r"[0-9a-fA-F]+", token):
                random = entropy(token) >= 3.0
            else:
                random = re.search(r"[a-z]", token) and re.search(r"[A-Z]", token) and entropy(token) >= 4.3
            if random:
                return "a random token, such as a key", f"{token[:4]}… ({len(token)} characters)"
    return None


def secrets_in(strings) -> list[tuple[Shipped, str, str]]:
    """Each shipped string shaped like a key that no ALLOW marks, with what it is and its first characters."""
    out = []
    for s in strings:
        found = None if s.allowed else key_shape(s)
        if found:
            out.append((s, *found))
    return out


def hosts_in(strings) -> dict[str, str]:
    """Each host an address in the shipped strings names, the machine's own aside, with the first place."""
    hosts: dict[str, str] = {}
    for s in strings:
        for text in s.strings():
            for m in URL.finditer(text):
                host = m.group(1).lower()
                if not LOCAL_HOSTS.fullmatch(host):
                    hosts.setdefault(host, s.place)
    return hosts


# --- the generator's helpers ----------------------------------------------------------
# assets/build_project.py keeps its helpers between a begin and an end marker, and the end
# marker carries their version and the stamp of the lines between. A game's copy,
# tools/build_project.py, takes the template's part in place of its own when the skill is
# refreshed, as long as its lines still match the stamp on its end marker: then nothing in
# the part was edited there, and the replacement loses nothing of the game's.
GENERATOR = "tools/build_project.py"
TEMPLATE = SKILL_DIR / "assets" / "build_project.py"
HELPERS_BEGIN = re.compile(r"# =+ construct3-agent-plugin helpers: begin\b")
HELPERS_END = re.compile(r"# =+ construct3-agent-plugin helpers: end\b")
HELPERS_VERSION = re.compile(r"; version (\d{4}-\d{2}-\d{2}), stamp ([0-9a-f]{12})\b")
MARKER_WIDTH = 100


class Helpers(NamedTuple):
    """The marked part of a generator: its markers' line indexes, the version and stamp its
    end marker carries, and the stamp of the lines between them as they are now."""
    begin: int
    end: int
    version: str
    stamp: str
    actual: str


class HelperState(NamedTuple):
    """How a game's generator stands against the template: missing, unmarked, broken (detail
    says what is wrong), current, older, newer, or edited (its lines match neither stamp)."""
    state: str
    detail: str = ""
    have: Helpers | None = None
    want: Helpers | None = None


def versions(have: Helpers, want: Helpers) -> tuple[str, str]:
    """The two versions in words, "2026-09-01" and "2026-10-04", with their stamps when the
    dates are the same."""
    if have.version != want.version:
        return have.version, want.version
    return f"{have.version}, stamp {have.stamp}", f"{want.version}, stamp {want.stamp}"


def helpers_stamp(lines: list[str]) -> str:
    """The stamp of the lines between the markers: the first 12 hex digits of their SHA-256."""
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:12]


def helpers_end_line(version: str, stamp: str) -> str:
    """The end marker as the template writes it."""
    line = f"# ==== construct3-agent-plugin helpers: end; version {version}, stamp {stamp} "
    return line + "=" * max(4, MARKER_WIDTH - len(line))


def text_lines(path: Path) -> tuple[list[str], str, bool]:
    """A UTF-8 file's lines without their ends, the line end it uses, and whether it starts
    with a byte order mark, so that it can be written back the way it was."""
    data = path.read_bytes()
    bom = data.startswith(b"\xef\xbb\xbf")
    text = data[3 if bom else 0:].decode("utf-8")
    return text.replace("\r\n", "\n").split("\n"), "\r\n" if "\r\n" in text else "\n", bom


def helpers_in(lines: list[str]) -> Helpers | str | None:
    """The marked part of a generator's lines; None when it has neither marker, and a sentence
    saying what is wrong and what to write when its markers are broken."""
    begins = [i for i, line in enumerate(lines) if HELPERS_BEGIN.match(line)]
    ends = [i for i, line in enumerate(lines) if HELPERS_END.match(line)]
    if not begins and not ends:
        return None
    copy = "copy the marker lines of the skill's assets/build_project.py around its helpers"
    if len(begins) != 1 or len(ends) != 1:
        return f"it has {len(begins)} begin and {len(ends)} end markers of the helpers, not one of each; {copy}"
    if ends[0] < begins[0]:
        return f"the end marker of its helpers stands above the begin marker; {copy}"
    found = HELPERS_VERSION.search(lines[ends[0]])
    if not found:
        return f"the end marker of its helpers has lost its version and stamp; {copy}"
    return Helpers(begins[0], ends[0], found[1], found[2], helpers_stamp(lines[begins[0] + 1:ends[0]]))


def generator_helpers(root: Path, template: Path = TEMPLATE) -> HelperState:
    """How the helpers of root's tools/build_project.py stand against the template's. Older and
    newer go by the version on the end markers; edited is a part whose lines match neither the
    stamp on its own end marker nor the template's lines."""
    path = root / GENERATOR
    if not path.is_file():
        return HelperState("missing")
    template_lines = text_lines(template)[0]
    want = helpers_in(template_lines)
    if not isinstance(want, Helpers):
        return HelperState("broken", f"the skill's own assets/build_project.py: {want or 'no markers'}")
    try:
        lines = text_lines(path)[0]
    except UnicodeDecodeError:
        return HelperState("broken", "it is not UTF-8 text, which Python reads a source file as; save it as UTF-8")
    have = helpers_in(lines)
    if have is None:
        return HelperState("unmarked")
    if isinstance(have, str):
        return HelperState("broken", have)
    if lines[have.begin:have.end + 1] == template_lines[want.begin:want.end + 1]:
        return HelperState("current", have=have, want=want)
    if have.actual not in (have.stamp, want.stamp):
        return HelperState("edited", have=have, want=want)
    return HelperState("newer" if have.version > want.version else "older", have=have, want=want)


def top_level_defs(lines: list[str]) -> list[tuple[str, int, list[str]]]:
    """Each top-level def of a module's lines: its name, the index of its first line, and its lines,
    decorators included. Raises SyntaxError when the lines do not parse."""
    found = []
    for node in ast.parse("\n".join(lines)).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            first = min([node.lineno, *(d.lineno for d in node.decorator_list)]) - 1
            found.append((node.name, first, lines[first:node.end_lineno]))
    return found


TEMPLATE_IN_CLONE = f"skills/{SKILL}/assets/build_project.py"


def copied_template(rag: Path, stamp: str) -> list[str] | None:
    """The template's lines at the newest commit of the clone whose marked part carries stamp and
    matches it: the template a game's generator was copied from, before the game edited it. None
    without the clone's history, as in the plugin cache, or when no commit has that stamp."""
    clone = clone_root(rag)
    if not (clone / ".git").exists() or not shutil.which("git"):
        return None
    log = git_out(clone, "log", "--follow", "--format=commit %H", "--name-only", "--", TEMPLATE_IN_CLONE, wait=30)
    commits: list[list[str]] = []
    for line in (log or "").splitlines():
        if line.startswith("commit "):
            # a merge lists no file: it has the path of the commit above it
            commits.append([line[7:], commits[-1][1] if commits else TEMPLATE_IN_CLONE])
        elif line.strip() and commits:
            commits[-1][1] = line.strip()
    for sha, path in commits:
        lines = (git_out(clone, "show", f"{sha}:{path}") or "").replace("\r\n", "\n").split("\n")
        found = helpers_in(lines)
        if not isinstance(found, Helpers):
            return None             # the commits below this one are older than the markers
        if found.stamp == stamp == found.actual:
            return lines
    return None


def unkept_helpers(root: Path, template: Path = TEMPLATE,
                   copied: list[str] | None = None) -> list[tuple[str, str, str]] | str:
    """What replacing the marked part of root's generator would lose: each def between its markers
    that no def of the same name below the end marker replaces and that the game changed. With copied,
    the template the part was copied from (copied_template), a def the game changed is one whose lines
    differ from copied's def of that name, or that copied lacks; without it, every def that differs from
    the template's counts, since the stamp cannot tell the game's edits from the template's. Each comes
    with the first line that differs, here and in the template it is compared with ('' where one has no
    such line). A sentence when the file does not parse."""
    lines, template_lines = text_lines(root / GENERATOR)[0], copied or text_lines(template)[0]
    have, want = helpers_in(lines), helpers_in(template_lines)
    try:
        ours, theirs = top_level_defs(lines), top_level_defs(template_lines)
    except SyntaxError as e:
        return f"it does not parse, line {e.lineno}: {e.msg}"
    below = {name for name, first, _ in ours if first > have.end}
    skills = {name: src for name, first, src in theirs if want.begin < first < want.end}
    lost = []
    for name, first, src in ours:
        if not have.begin < first < have.end or name in below or skills.get(name) == src:
            continue
        other = skills.get(name, [])
        k = next(k for k in range(max(len(src), len(other))) if src[k:k + 1] != other[k:k + 1])
        lost.append((name, src[k] if k < len(src) else "", other[k] if k < len(other) else ""))
    return lost


def replace_helpers(root: Path, template: Path = TEMPLATE, dry_run: bool = False) -> str | None:
    """Put the template's marked part, both markers included, in place of the one in root's
    tools/build_project.py; every line outside the markers, the line ends and a byte order mark
    stay as they were. None when done, or a sentence when the result would not compile, and
    then nothing is written."""
    path = root / GENERATOR
    lines, newline, bom = text_lines(path)
    template_lines = text_lines(template)[0]
    have, want = helpers_in(lines), helpers_in(template_lines)
    text = newline.join(lines[:have.begin] + template_lines[want.begin:want.end + 1] + lines[have.end + 1:])
    try:
        compile(text, str(path), "exec")
    except SyntaxError as e:
        return f"with the skill's helpers it would not compile, line {e.lineno}: {e.msg}"
    if not dry_run:
        draft = path.with_name(f".{path.name}.{os.getpid()}")
        draft.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
        shutil.copymode(path, draft)
        os.replace(draft, path)
    return None


def argument_parser(description: str, epilog: str) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=description, epilog=epilog,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", metavar="FOLDER",
                    help="the folder that holds project.c3proj (default: found from the current directory upward)")
    ap.add_argument("--rag", metavar="FOLDER",
                    help="the Construct3-RAG clone (default: CONSTRUCT3_RAG, else the 'Construct3-RAG:' line "
                         "of the project's AGENTS.md or CLAUDE.md)")
    ap.add_argument("--locale", default="en-US",
                    help="schema locale, one of `languages` in data/c3-schemas/_index.json; ids are the same in "
                         "every locale, names and wording differ (default: en-US)")
    ap.add_argument("--limit", type=int, default=LIMIT, metavar="CHARS",
                    help=f"stop after about this many characters and say how to get the rest, since a harness "
                         f"cuts longer tool output; 0 prints everything (default: {LIMIT})")
    return ap


# --- the project ----------------------------------------------------------------------
class Project:
    """project.c3proj, the object types and families it lists, and the schemas
    of the clone. Loading reports what it cannot find to `findings`."""

    def __init__(self, root: Path | None, rag: Path, locale: str, findings: Findings) -> None:
        self.root = root or Path.cwd()
        self.rag = rag
        self.locale = locale
        self.findings = findings
        self.err, self.warn = findings.err, findings.warn
        self.schemas = rag / "data" / "c3-schemas" / locale
        self.data: dict = load(root / "project.c3proj") if root else {}
        self.used_addons = {a["id"]: a for a in self.data.get("usedAddons", [])}
        self.functions_object: str = self.data.get("functionsName", "Functions")

        self._schema_cache: dict[tuple[str, str], dict | None] = {}
        self._addon_names: dict[str, dict[str, str]] = {}
        self._expression_names: dict[tuple[str, str], dict[str, str]] = {}
        self._common_of: dict[str, dict] = {}
        self._deprecated: dict[str, dict] = {}
        self.index = load(rag / "data" / "c3-schemas" / "_index.json")
        if not self.schemas.is_dir():
            sys.exit(f"no schemas for --locale {locale}; the clone has: {', '.join(self.index.get('languages', []))}")
        self.common = self.schema("plugins", "_common")
        self.system = self.schema("plugins", "system")
        self.system_expression_names = self.expressions_of(self.system)
        self.system_expressions = self.system_expression_names | {"self", "loopindex", "infinity"}
        self.common_expressions = self.expressions_of(self.common)

        self.types = self.load_listed("objectTypes")
        self.families = self.load_listed("families")
        self.plugin_of = {n: t["plugin-id"] for n, t in self.types.items()}
        self.plugin_of.update({n: f["plugin-id"] for n, f in self.families.items()})
        self.plugin_of["System"] = "system"
        # the built-in Functions object: Set return value lives in the System schema
        self.plugin_of[self.functions_object] = "system"
        self.objects_lower = {LOWER(n): n for n in self.plugin_of}

    @classmethod
    def open(cls, args: argparse.Namespace, findings: Findings, needs_project: bool = True) -> "Project":
        root = find_project(args.project)
        if root and not (root / "project.c3proj").exists():
            example = missing_example(root, args.rag)
            if example:
                sys.exit(example)
            sys.exit(f"no project.c3proj in {root}: --project is the folder the editor saved the project into"
                     f"{START_ONE}")
        if root is None and needs_project:
            sys.exit(f"no project.c3proj in {Path.cwd()} or above it; run this from the project folder "
                     f"or pass --project <folder>{START_ONE}")
        return cls(root, find_rag(root, args.rag), args.locale, findings)

    # --- files ------------------------------------------------------------------------
    def project_file(self, kind: str, name: str, folder: Path) -> Path | None:
        return project_file(self.root, kind, name, folder)

    def listed_files(self, kind: str) -> dict[str, Path | None]:
        """The file of every item project.c3proj lists under kind; None for one that has no file."""
        return listed_files(self.root, self.data, kind)

    def script_files(self) -> list[Path]:
        """The JavaScript and TypeScript files project.c3proj lists, relative to the project folder."""
        out = []
        for item, folder in folder_items(self.data.get("rootFileFolders", {}).get("script", {})):
            path = Path("scripts") / folder / str(item.get("name", "") if isinstance(item, dict) else item)
            if (self.root / path).is_file():
                out.append(path)
        return out

    def scripts_summary(self) -> str:
        """'scripts/main.js (110 lines)', each listed script with its length."""
        def lines(path: Path) -> int:
            return len((self.root / path).read_text(encoding="utf-8", errors="replace").splitlines())
        return ", ".join(f"{path.as_posix()} ({lines(path)} lines)" for path in self.script_files())

    def script_numbers(self, path: Path) -> dict[float, int]:
        """How often each number is written as a literal in the code of a script; comments and
        strings do not count."""
        code = SCRIPT_TEXT.sub(" ", (self.root / path).read_text(encoding="utf-8", errors="replace"))
        counts: dict[float, int] = {}
        for m in SCRIPT_NUMBER.finditer(code):
            counts[float(m.group(0))] = counts.get(float(m.group(0)), 0) + 1
        return counts

    def load_listed(self, kind: str) -> dict[str, dict]:
        out = {}
        for name, path in self.listed_files(kind).items():
            if path is None:
                self.err(f"{kind}: {name} is listed in project.c3proj but has no file")
                continue
            out[name] = load(path)
            if kind in ("objectTypes", "families") and isinstance(out[name], dict):
                self.read_lists(kind, name, out[name])
        return out

    def read_lists(self, kind: str, name: str, data: dict) -> None:
        """An object type's or family's instance variables, behaviors and effects are each a
        list, and the editor stops on a folder there, {"items": [], "subfolders": []}, with
        "TypeError: ... is not iterable". The finding names the key, and the folder's items are
        read as the list, so that the later checks and the other scripts can read the file."""
        what = "object type" if kind == "objectTypes" else "family"
        for key in ("instanceVariables", "behaviorTypes", "effectTypes"):
            value = data.get(key, [])
            if isinstance(value, list):
                continue
            data[key] = found = folder_entries(value) if isinstance(value, dict) else []
            shape = "a folder" if isinstance(value, dict) and ("items" in value or "subfolders" in value) \
                else json.dumps(value, ensure_ascii=False)[:60]
            self.err(f"{what} {name}: \"{key}\" is {shape}, and the editor reads it as a list, stopping with "
                     f"\"TypeError: ... is not iterable\" before the project opens. Write \"{key}\": "
                     + ("[...], the folder's items in a list" if found else "[]"))

    # --- schemas ----------------------------------------------------------------------
    def addon_names(self, kind: str) -> dict[str, str]:
        """Schema id by squashed id and display name, in the locale and in en-US:
        '8 Direction', 'EightDir' and '八方向' are eightdir."""
        if kind not in self._addon_names:
            by_name = {}
            for locale in {self.locale, "en-US"}:
                names_file = self.rag / "data" / "c3-schemas" / locale / "_index.json"
                if names_file.exists():
                    for k, v in load(names_file).get(kind, {}).items():
                        by_name[squash(v.get("name", k))] = k
            self._addon_names[kind] = {**by_name, **{squash(k): k for k in self.index.get(kind, {})}}
        return self._addon_names[kind]

    def addon_hint(self, kind: str, addon_id: str) -> str | None:
        """The id the editor uses for what the project calls addon_id, found through
        the display name ('Array' is Arr, '8 Direction' is EightDir) or a near id."""
        ids = self.index.get(kind, {})
        table = self.addon_names(kind)
        hit = table.get(squash(addon_id))
        if hit is None:
            near = difflib.get_close_matches(squash(addon_id), list(table), n=1, cutoff=0.75)
            hit = table[near[0]] if near else None
        if hit is None or hit not in ids or hit == "_common":
            return None
        return ids[hit].get("originalId", hit)

    def schema(self, kind: str, addon_id: str) -> dict | None:
        key = (kind, addon_id.lower())
        if key not in self._schema_cache:
            path = self.schemas / kind / f"{addon_id.lower()}.json"
            self._schema_cache[key] = load(path) if path.exists() else None
            if self._schema_cache[key] is None:
                # An addon the project lists under another author is a third-party one: no schema, no hint.
                third_party = self.used_addons.get(addon_id, {}).get("author", "Scirra") != "Scirra"
                retired = None if third_party else self.deprecated_addon(kind, addon_id)
                hint = None if third_party or retired else self.addon_hint(kind, addon_id)
                if retired:
                    unchecked = "its parameters are" if kind == "effects" else "its ACEs and properties are"
                    self.warn(f"{kind[:-1]} {addon_id} ({retired.get('name', addon_id)}) is deprecated: "
                              f"{DEPRECATED}; {unchecked} not checked")
                elif hint:
                    self.err(f"{kind[:-1]} id {addon_id!r} does not exist: the editor's id is {hint!r}")
                elif kind != "effects" and self.used_addons.get(addon_id, {}).get("author") == "Scirra":
                    # Every addon by Scirra is in the schema index, so one that is not there was made up.
                    # The editor reports it as a missing legacy (SDK v1) addon and does not open the project.
                    self.err(f"{kind[:-1]} id {addon_id!r} is invented: usedAddons lists it by Scirra, and no "
                             f"addon by Scirra has that id, so the editor stops with \"Missing addons\". Remove "
                             f"its usedAddons entry and the object type or behavior that uses it. Functions need "
                             f"no object type and no usedAddons entry: project.c3proj names the built-in object "
                             f"in \"functionsName\": \"{self.functions_object}\"")
                else:
                    self.warn(f"no schema for {kind[:-1]} {addon_id}: its ACEs and properties are not checked")
        return self._schema_cache[key]

    def expression_names(self, schema: dict | None) -> dict[str, str]:
        """ACE id -> the name an expression is written under. A project file holds
        the English name whatever language the editor runs in, so it is read from
        en-US: in another locale `translated-name` is wording, `移动速度` for `Speed`."""
        if not schema:
            return {}
        key = (schema["type"], schema["id"])
        if key not in self._expression_names:
            english = schema if self.locale == "en-US" else \
                load(self.rag / "data" / "c3-schemas" / "en-US" / f"{schema['type']}s" / f"{schema['id']}.json")
            self._expression_names[key] = {e["id"]: e["translated-name"] for e in english.get("expressions", [])}
        return self._expression_names[key]

    def expressions_of(self, schema: dict | None) -> set[str]:
        return {LOWER(name) for name in self.expression_names(schema).values()}

    def common_of(self, plugin: dict) -> dict:
        """The part of plugins/_common.json the editor gives this plugin: the ids
        its `commonAces` lists. Text has no set-default-color, Array no X, and the
        editor refuses a project that uses one. A schema without the list, from
        an older export, gets all of them."""
        allowed = plugin.get("commonAces")
        if allowed is None or not self.common:
            return self.common or {}
        if plugin["id"] not in self._common_of:
            self._common_of[plugin["id"]] = {
                **self.common,
                **{kind: [it for it in self.common.get(kind, []) if it["id"] in allowed.get(kind, [])]
                   for kind in ("conditions", "actions", "expressions")}}
        return self._common_of[plugin["id"]]

    def common_expressions_of(self, plugin: dict | None) -> set[str]:
        """The shared expressions a plugin has, as they are written, lower case."""
        if plugin is None:
            return self.common_expressions
        ids = {it["id"] for it in self.common_of(plugin).get("expressions", [])}
        return {LOWER(name) for ace, name in self.expression_names(self.common).items() if ace in ids}

    # --- what the editor has deprecated -----------------------------------------------
    def deprecated(self, locale: str | None = None) -> dict:
        """{locale}/_deprecated.json: every addon and ACE the editor has deprecated,
        whether the schema kept it or not. Empty for a clone exported without it."""
        locale = locale or self.locale
        if locale not in self._deprecated:
            path = self.rag / "data" / "c3-schemas" / locale / "_deprecated.json"
            self._deprecated[locale] = load(path) if path.exists() else {}
        return self._deprecated[locale]

    def deprecated_addon(self, kind: str, addon_id: str) -> dict | None:
        return self.deprecated().get("addons", {}).get(kind, {}).get(addon_id.lower())

    def deprecated_addon_named(self, name: str) -> tuple[str, str, dict] | None:
        """(kind, id, entry) of the deprecated plugin, behavior or effect with this
        id or display name, in the locale or in en-US: 'NW.js' is nodewebkit."""
        for kind in ("plugins", "behaviors", "effects"):
            for locale in dict.fromkeys((self.locale, "en-US")):
                for addon_id, entry in self.deprecated(locale).get("addons", {}).get(kind, {}).items():
                    spellings = {squash(addon_id), squash(entry.get("originalId", addon_id)), squash(entry.get("name", ""))}
                    if squash(name) in spellings:
                        return kind, addon_id, self.deprecated_addon(kind, addon_id) or entry
        return None

    def deprecated_aces(self, addon_kind: str, addon_id: str, ace_kind: str, locale: str | None = None) -> dict[str, dict]:
        """ACE id -> entry of the addon's deprecated conditions, actions or expressions."""
        return (self.deprecated(locale).get("aces", {}).get(addon_kind, {})
                .get(addon_id.lower(), {}).get(ace_kind, {}))

    def deprecated_expressions(self, addon_kind: str, addon_id: str) -> dict[str, tuple[str, dict]]:
        """Written name, lower case -> (ACE id, entry) of the addon's deprecated
        expressions. The written name is the English one in every locale."""
        english = self.deprecated_aces(addon_kind, addon_id, "expressions", "en-US")
        entries = self.deprecated_aces(addon_kind, addon_id, "expressions")
        return {LOWER(e.get("translated-name", ace)): (ace, entries.get(ace, e)) for ace, e in english.items()}

    def deprecated_entry(self, kind: str, ace: dict) -> tuple[str, dict] | None:
        """(addon id, entry) when a condition or action is one the editor has
        deprecated, whether the schema kept it or not."""
        obj = ace.get("objectClass")
        if obj not in self.plugin_of:
            return None
        if "behaviorType" in ace:
            behavior_id = self.behaviors_of(obj).get(ace["behaviorType"])
            owners = [("behaviors", behavior_id)] if behavior_id else []
        else:
            owners = [("plugins", self.plugin_of[obj])] + ([] if obj == "System" else [("plugins", "_common")])
        for addon_kind, addon_id in owners:
            entry = self.deprecated_aces(addon_kind, addon_id, kind).get(ace.get("id"))
            if entry:
                return addon_id, entry
        return None

    # --- object types and families ----------------------------------------------------
    def families_of(self, obj: str) -> list[str]:
        return [f for f, d in self.families.items() if obj in d.get("members", [])]

    def ivar_types_of(self, obj: str) -> dict[str, str]:
        """instance variable name -> type, family variables included for member types."""
        ivars = {}
        if obj in self.types:
            ivars.update({v["name"]: v["type"] for v in self.types[obj].get("instanceVariables", [])})
            for f in self.families_of(obj):
                ivars.update({v["name"]: v["type"] for v in self.families[f].get("instanceVariables", [])})
        if obj in self.families:
            ivars.update({v["name"]: v["type"] for v in self.families[obj].get("instanceVariables", [])})
        return ivars

    def ivars_of(self, obj: str) -> set[str]:
        return set(self.ivar_types_of(obj))

    def behaviors_of(self, obj: str) -> dict[str, str]:
        """behavior name -> behavior id, family behaviors included for member types."""
        names = {}
        if obj in self.types:
            for b in self.types[obj].get("behaviorTypes", []):
                names[b["name"]] = b["behaviorId"]
            for f in self.families_of(obj):
                for b in self.families[f].get("behaviorTypes", []):
                    names[b["name"]] = b["behaviorId"]
        if obj in self.families:
            for b in self.families[obj].get("behaviorTypes", []):
                names[b["name"]] = b["behaviorId"]
        return names

    def animations_of(self, obj: str) -> set[str] | None:
        """Animation names of a Sprite type, or the union over a family's members. None: not a Sprite."""
        def walk(folder):
            out = {LOWER(a["name"]) for a in folder.get("items", [])}
            for sub in folder.get("subfolders", []):
                out |= walk(sub)
            return out
        if obj in self.types and "animations" in self.types[obj]:
            return walk(self.types[obj]["animations"])
        if obj in self.families:
            members = [m for m in self.families[obj].get("members", [])
                       if m in self.types and "animations" in self.types[m]]
            return set().union(*(walk(self.types[m]["animations"]) for m in members)) if members else None
        return None

    # --- conditions and actions -------------------------------------------------------
    def ace_sources(self, ace: dict) -> list[dict]:
        """The schemas an ACE is looked up in: the named behavior's, or the plugin's
        and then the shared world-object one. Empty when the object, the behavior or
        its schema is unknown."""
        obj = ace.get("objectClass")
        if obj not in self.plugin_of:
            return []
        if "behaviorType" in ace:
            behavior_id = self.behaviors_of(obj).get(ace["behaviorType"])
            own = self.schema("behaviors", behavior_id) if behavior_id else None
            return [own] if own else []
        own = self.schema("plugins", self.plugin_of[obj])
        if own is None:
            return []       # a third-party plugin: its own ACEs cannot be told from a wrong id
        return [own] if obj == "System" else [own, self.common_of(own)]

    def ace_entry(self, kind: str, ace: dict) -> dict | None:
        return next((it for s in self.ace_sources(ace) for it in s.get(kind, []) if it["id"] == ace.get("id")), None)

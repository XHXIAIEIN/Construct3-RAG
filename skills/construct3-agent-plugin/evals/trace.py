"""Read what a run did from its transcript: every tool call, what came back, what failed, and the route it took.

    python evals/trace.py TRANSCRIPT.jsonl [--out RUN_DIR] [--root FOLDER] [--full]
    python evals/trace.py --list SESSION_DIR

A run's answer lists the commands it remembers; its transcript lists the ones
it made. Claude Code keeps the transcript of a subagent as
~/.claude/projects/<project>/<session id>/subagents/agent-<id>.jsonl, with
the description it was started under in agent-<id>.meta.json beside it;
--list prints both for every subagent of a session. --out copies the
transcript to RUN_DIR/transcript.jsonl and records where it was read from, so
that a column can be recounted after the session's files are gone.

The trace shows where a run lost turns: a lookup that found nothing, an edit
that did not match, a script called for output it then could not use. A call
counts as lost when its result is an error, except a run of check_project.py
that reported findings (a warning:, stop: or "N problem(s)" line) and a run of
check_design.py that reported findings, whose exit code 1 is what they were
asked for; a Grep or Glob that found nothing counts as lost too. outside
lists the writes outside the run folder (--root, by default RUN_DIR of
--out): an absolute path given to Write, Edit or NotebookEdit, and one a
shell command redirects to or gives to a command that writes (cp, mv,
mkdir, rm, tee, Set-Content, Copy-Item ...); outside_reads lists the other
absolute paths outside it. A relative path, a variable and a path built
inside a script are not resolved, so the list is a floor: an empty one
proves nothing. read_skill_md is true when this skill's SKILL.md reached the
model: the Skill tool called with this skill, its SKILL.md read, or a shell
read of it (cat, type, Get-Content, sed, head) that came back with more than
5000 characters, and the call's result came back without an error, as
run_trigger_eval.py counts a trigger. turns, output_tokens and input_tokens
(cache writes and reads included) are read from the model's responses in the
transcript, and seconds from its first and last timestamps: what the run cost.

The route columns say how the run used the skill, each counted from the
calls and their results:

- first_script: the first script of this skill the run called, a --help
  read included.
- chain_depth, chain_end, chain_attempts, chain: the check chain
  check_project, review_design, open_in_editor --preview, preview_project,
  review_look. A step passed when a call of it printed the line a passing
  run ends on: "ok:", "design: 0 findings", "N of N opened and ran without
  errors", "keep:" or "kept:", "look: 0 findings ... 0 runtime errors".
  chain_depth is the position of the deepest step that passed (0 to 5),
  chain_end its name, chain_reached the deepest step called whether it
  passed or not, chain_attempts the calls of chain scripts, and chain the
  calls and the outcome of each step.
- preview_failed: script calls whose result says that no preview window
  opened or that the editor did not load.
- help_reads, repeat_help, help_reads_by_script: --help reads, the reads
  beyond the first of the same script, and the reads per script.
- plan_refusals: edit_sheet.py calls that wrote nothing: exit code 1 as
  the harness saw it, or the refusal's "nothing was written" outside a dry
  run's own last line.
- hand_edits: a file tool, a shell command or an inline script of one
  (python -, a heredoc) writing a .json or .c3proj file of the project
  outside its dot folders: a change the skill's scripts make.
- lookups_before_first_edit: the calls before the first one that tried to
  change the project: a write under project/ outside its dot folders,
  failed or not, or an edit_sheet.py run, a dry run included, because
  the plan it checks is the edit; null when nothing did.
- data_reads, other_clone_reads: calls that read the clone the project's
  Construct3-RAG: line names, read as scripts/c3project.py reads it (a
  path with spaces, or <path-to> defined above), under its data/ and
  elsewhere in it, a relative path resolved against the cd before it. A
  script run from the clone, and a --rag or --project value, are not
  reads.
- entry_chars: the characters that came back before the first script
  call: the skill, the instruction files, the listing of the project.
- printed_command_failures: lost shell calls whose script path an earlier
  result printed, as a word or as the end of a longer one. A check that
  reported findings is not lost, so the fix loop a printed check starts
  does not count; a refused plan is lost and counts here as well as in
  plan_refusals.

hand_edits, lookups_before_first_edit and the clone reads need the run
folder (--out or --root) with its project/; without it they are null.

exit codes: 0 read, 1 the file holds no tool call
"""
import argparse
import json
import os
import re
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from run_trigger_eval import loads_skill

SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL = SKILL_DIR.name
sys.path.insert(0, str(SKILL_DIR / "scripts"))
import c3project  # noqa: E402
# The scripts of this skill, so that a call of one is found whatever path form it is run by ($S/x.py too).
SCRIPT_NAMES = sorted(p.stem for p in (SKILL_DIR / "scripts").glob("*.py") if not p.stem.startswith("_"))
SCRIPT = re.compile(r"(?<![\w.-])(" + "|".join(SCRIPT_NAMES) + r")\.py\"?"
                    r"((?:\s+(?!\d*[<>])(?:\"[^\"]*\"|[^\s|;&<>]+))*)")     # 2>&1 is not an argument
# The word a script is run by, with the path in front of it, quoted or bare.
SCRIPT_WORD = re.compile(r"\"([^\"]*?\.py)\"|([^\s\"|;&<>]+\.py)")
HELP = {"--help", "-h"}

# The check chain in order, and the line a passing call of each step prints.
CHAIN = ("check_project", "review_design", "open_in_editor", "preview_project", "review_look")
PASSED = {
    "check_project": re.compile(r"^ok: ", re.M),
    "review_design": re.compile(r"^design: 0 findings", re.M),
    "open_in_editor": re.compile(r"^(\d+) of (\d+) opened and ran without errors", re.M),
    "preview_project": re.compile(r"^(keep|kept): ", re.M),
    "review_look": re.compile(r"^look: 0 findings on \d+ layouts?, 0 runtime errors", re.M),
}
PREVIEW_FAILED = ("no preview window", "the editor did not load")
CHECK_FINDINGS = re.compile(r"^(warning: |stop: |\d+ problem\(s\)$)", re.M)
DESIGN_FINDINGS = re.compile(r"^design: \d+ findings?; fix", re.M)
NO_MATCH = ("No matches found", "No files found")
REFUSED = "nothing was written"
DRY_RUN_LINE = "dry run: nothing was written"
PROJECT_FILES = (".json", ".c3proj")
SKILL_READ_CHARS = 5000


def short(value: object, n: int) -> str:
    text = str(value).replace("\n", " \\n ")
    return text if len(text) <= n else f"{text[:n]} ...[{len(text)} chars]"


def calls_of(path: Path) -> list[dict]:
    """Tool calls in order, each with the size and the failure of its result."""
    calls, by_id = [], {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            content = (json.loads(line).get("message") or {}).get("content")
        except ValueError:
            continue
        for part in content if isinstance(content, list) else []:
            if part.get("type") == "tool_use":
                given = part.get("input", {})
                what = given.get("command") or given.get("file_path") or given.get("pattern") or given.get("skill") or given
                by_id[part["id"]] = {"tool": part.get("name"), "what": str(what), "chars": None, "failed": False,
                                     "result": "", "loads_skill": loads_skill(part), "input": given}
                calls.append(by_id[part["id"]])
            elif part.get("type") == "tool_result" and part.get("tool_use_id") in by_id:
                body = part.get("content")
                if isinstance(body, list):
                    body = " ".join(b.get("text", "") for b in body if isinstance(b, dict))
                text = str(body or "")
                by_id[part["tool_use_id"]].update(chars=len(text), failed=bool(part.get("is_error")), result=text)
    return calls


# The tools a run starts a script with: Bash, or PowerShell on Windows.
SHELLS = ("Bash", "PowerShell")


# Shell text in words: 2>&1, a redirection, a separator, a quoted string, or a bare word.
WORD = re.compile(r"""\d?>>?&\d|\d?>>?|&&|\|\||[|;&\n]|"[^"]*"|'[^']*'|[^\s"'|;&>]+""")
REDIRECT = re.compile(r"\d?>>?")
SEPARATORS = {"&&", "||", "|", ";", "&", "\n"}
NOWHERE = {"/dev/null", "$null", "nul"}
WRITES_EVERY = {"mkdir", "md", "rm", "rmdir", "rd", "del", "erase", "touch", "tee", "tee-object", "new-item", "ni",
                "remove-item", "ri", "set-content", "sc", "add-content", "ac", "out-file"}
WRITES_LAST = {"cp", "mv", "copy", "move", "copy-item", "cpi", "move-item", "mi", "rsync"}
# Shell commands that print a file: a read of SKILL.md by one of them counts as the skill reaching the model.
READERS = {"cat", "type", "get-content", "gc", "sed", "head", "tail", "more", "less"}
# Options whose value is a folder the script is pointed at, not one the command reads.
POINTED_AT = {"--rag", "--project", "--old-clone", "--root", "--out"}
FILE_WRITES = {"Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path", "NotebookEdit": "notebook_path"}
FILE_READS = {"Read": "file_path", "Glob": "path", "Grep": "path"}


def absolute(word: str) -> str | None:
    """word as an absolute path, or None: a relative path or a variable is not resolved.
    Git Bash's /c/Users is C:/Users."""
    word = word.strip("\"'")
    if word.lower() in NOWHERE:
        return None
    word = re.sub(r"^/([A-Za-z])(?=/|$)", r"\1:", word)
    word = os.path.expanduser(word) if word.startswith("~") else word
    return os.path.abspath(word) if re.match(r"[A-Za-z]:[\\/]|/|\\\\", word) else None


def command_name(word: str) -> str:
    return Path(word.strip("\"'")).name.lower().removesuffix(".exe")


def without_sed_script(words: list[str]) -> list[str]:
    """A sed command's words without its script, which can start with / (`/^}/d`): the word after -e or -f, or else
    the first word that is not an option."""
    out, given, skip = [words[0]], any(w in ("-e", "-f") for w in words), False
    for w in words[1:]:
        if skip:
            skip = False
        elif w in ("-e", "-f"):
            skip = True
        elif not given and not w.startswith("-"):
            given = True
        else:
            out.append(w)
    return out


def split_shell(command: str) -> tuple[list[list[str]], list[str]]:
    """The command's segments as words, a sed script left out, and the absolute paths its redirections write."""
    segments: list[list[str]] = []
    writes: list[str] = []
    segment: list[str] = []

    def close() -> None:
        if segment:
            segments.append(without_sed_script(segment) if command_name(segment[0]) == "sed" else list(segment))
        segment.clear()

    words = WORD.findall(command)
    i = 0
    while i < len(words):
        if words[i] in SEPARATORS:
            close()
        elif REDIRECT.fullmatch(words[i]):
            i += 1
            target = absolute(words[i]) if i < len(words) else None
            if target:
                writes.append(target)
        elif "&" not in words[i]:      # 2>&1
            segment.append(words[i])
        i += 1
    close()
    return segments, writes


def shell_paths(command: str) -> tuple[list[str], list[str]]:
    """The absolute paths a shell command writes and the ones it only names, as far as its words say."""
    segments, writes = split_shell(command)
    named = []
    for words in segments:
        name = command_name(words[0])
        values = [w.split("=", 1)[1] if w.startswith("-") and "=" in w else w for w in words[1:]]
        paths = [p for w in values if not w.startswith("-") and (p := absolute(w))]
        if name in WRITES_EVERY or (name == "sed" and any(w.startswith("-i") for w in words)):
            writes.extend(paths)
        elif name in WRITES_LAST and paths:
            writes.append(paths[-1])
            named.extend(paths[:-1])
        else:
            named.extend(paths)
    return writes, named


# A word that can be a relative path: no shell or code punctuation, a separator in it or an extension at its end.
PATH_LIKE = re.compile(r"[^\s()\[\]{};'\"$*?<>|&\\][^\n\t()\[\]{};'\"$*?<>|&]*(?:[\\/][^\n\t()\[\]{};'\"$*?<>|&]*|\.[A-Za-z0-9]{1,5})")
# A string literal of an inline script that names a file: a path with a separator, or a name with a known extension.
LITERAL_PATH = re.compile(r"""["']([^"'\n\t()\[\]{};$*?<>|&\\][^"'\n\t()\[\]{};$*?<>|&]*?"""
                          r"""(?:[\\/][^"'\n\t()\[\]{};$*?<>|&]*|\.(?:json|c3proj|ts|js|md|txt)))["']""")
# An inline script (python -, python -c, node -e, a heredoc) that writes a file.
INTERPRETER = re.compile(r"(?<![\w-])(?:python3?|py|node|pwsh|powershell)(?:\.exe)?\"?\s+(?:-[ce]?\s|-\s*<<|<<)|<<\s*-?\s*['\"]?\w+")
WRITE_CALL = re.compile(r"\.write_(?:text|bytes)\(|writeFile(?:Sync)?\(|open\([^)]*[\"'][wa]b?\+?[\"']|Set-Content|Out-File")
CD = re.compile(r"""(?:^|&&|\|\||;|\n)\s*cd\s+("[^"]+"|'[^']+'|[^\s;&|]+)""")
REDIRECT_TARGET = re.compile(r"""(?<![\d&])>>?\s*("[^"]+"|'[^']+'|[^\s;&|<>]+)""")


def resolved(word: str, cwd: str | None) -> str | None:
    """word as an absolute path: given so, or relative to the cwd a cd in the same command set."""
    value = word.strip("\"'")
    if p := absolute(value):
        return p
    return os.path.abspath(os.path.join(cwd, value)) if cwd and PATH_LIKE.fullmatch(value) else None


def read_paths(command: str) -> list[str]:
    """The absolute paths a shell command reads, as far as its words say: the paths it names that are not the
    script it runs or a folder a script is pointed at, a relative one resolved against the cd before it. A cd
    target counts only when the command names no other path and runs no script of this skill, because the rest
    of it then runs relative to that folder."""
    moved, named = [], []
    cwd = None
    for words in split_shell(command)[0]:
        if command_name(words[0]) == "cd":
            if len(words) > 1 and (target := absolute(words[-1])):
                cwd = target
                moved.append(target)
            continue
        skip = False
        for w in words[1:]:
            option, _, value = w.partition("=") if w.startswith("-") else ("", "", w)
            if skip:
                skip = False
            elif option in POINTED_AT:
                skip = not value
            elif not option and (p := resolved(value, cwd)) and not p.lower().endswith(".py"):
                named.append(p)
    return named or ([] if SCRIPT.search(command) else moved)


def cwd_at(command: str, position: int) -> str | None:
    """The folder the command is in at position: the target of the last cd before it, None when there is none or
    it is a variable."""
    target = None
    for m in CD.finditer(command):
        if m.start() >= position:
            break
        target = absolute(m.group(1))
    return target


def inline_writes(command: str) -> list[str]:
    """The files the command writes by a redirection or an inline script, relative to the cd before each: a
    python -, python -c, node -e or heredoc script that holds a write call names its files as string literals."""
    out = [p for m in REDIRECT_TARGET.finditer(command) if (p := resolved(m.group(1), cwd_at(command, m.start())))]
    script = INTERPRETER.search(command)
    if script and WRITE_CALL.search(command):
        cwd = cwd_at(command, script.start())
        out += [p for literal in LITERAL_PATH.findall(command[script.start():]) if (p := resolved(literal, cwd))]
    return out


def reads_skill_md(command: str) -> bool:
    """A shell command that prints this skill's SKILL.md."""
    return any(command_name(words[0]) in READERS
               and any(("/" + w.strip("\"'").replace("\\", "/")).endswith(f"/{SKILL}/SKILL.md") for w in words[1:])
               for words in split_shell(command)[0])


def base_of(folder: Path) -> str:
    """folder as within and parts_below compare a path with it: absolute, case-normalized, no trailing slash."""
    return os.path.normcase(os.path.abspath(folder)).rstrip("\\/")


def within(path: str, folder: Path) -> bool:
    base = base_of(folder)
    path = os.path.normcase(path)
    return path == base or path.startswith(base + os.sep)


def parts_below(path: str, folder: Path) -> list[str]:
    """The parts of path below folder, which holds it."""
    return [p for p in re.split(r"[\\/]", os.path.normcase(path)[len(base_of(folder)):]) if p]


def outside(calls: list[dict], root: Path) -> tuple[list[dict], list[dict]]:
    """The writes and the reads of absolute paths outside root, each with its tool."""
    writes, reads = [], []
    for c in calls:
        wrote, named = paths_of(c)
        writes += [{"tool": c["tool"], "path": p} for p in wrote if not within(p, root)]
        reads += [{"tool": c["tool"], "path": p} for p in named if not within(p, root)]
    return writes, reads


def paths_of(c: dict) -> tuple[list[str], list[str]]:
    """The absolute paths a call writes and the ones it names."""
    given = c["input"] if isinstance(c["input"], dict) else {}
    if c["tool"] in SHELLS:
        return shell_paths(str(given.get("command", "")))
    path = absolute(str(given.get(FILE_WRITES.get(c["tool"]) or FILE_READS.get(c["tool"]) or "", "")))
    return ([path], []) if c["tool"] in FILE_WRITES and path else ([], [path] if path else [])


def usage_of(path: Path) -> dict:
    """What the run cost, from its transcript. turns counts the model's responses by message id, because the
    transcript writes a response once per content block. output_tokens and input_tokens add up the responses'
    usage, input with cache writes and reads. seconds runs from the first timestamp to the last. model is the
    responses' model."""
    seen: dict[str, dict] = {}
    times, model = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("timestamp"):
            times.append(entry["timestamp"])
        message = entry.get("message") or {}
        if entry.get("type") == "assistant" and message.get("id") and isinstance(message.get("usage"), dict):
            seen[message["id"]] = message["usage"]
            model = message.get("model") or model
    stamps = sorted(datetime.fromisoformat(t.replace("Z", "+00:00")) for t in times)
    return {"turns": len(seen), "output_tokens": sum(u.get("output_tokens", 0) for u in seen.values()),
            "input_tokens": sum(u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                                + u.get("cache_read_input_tokens", 0) for u in seen.values()),
            "seconds": round((stamps[-1] - stamps[0]).total_seconds(), 1) if len(stamps) > 1 else None, "model": model}


def scripts_of(c: dict) -> list[tuple[str, list[str]]]:
    """The scripts of this skill a call runs, each with its argument words."""
    if c["tool"] not in SHELLS:
        return []
    return [(m.group(1), m.group(2).split()) for m in SCRIPT.finditer(c["what"])]


def work_scripts(c: dict) -> set[str]:
    """The scripts the call runs for their work, not for their --help."""
    return {script for script, args in scripts_of(c) if not HELP & set(args)}


def runs_script(c: dict, name: str) -> bool:
    return name in work_scripts(c)


def is_lost(c: dict) -> bool:
    if c["tool"] in ("Grep", "Glob"):
        return c["failed"] or any(p in c["result"] for p in NO_MATCH)
    if not c["failed"]:
        return False
    if runs_script(c, "check_project") and CHECK_FINDINGS.search(c["result"]):
        return False
    return not (runs_script(c, "check_design") and DESIGN_FINDINGS.search(c["result"]))


def step_passed(name: str, result: str) -> bool:
    m = PASSED[name].search(result)
    if name == "open_in_editor":
        return bool(m) and m.group(1) == m.group(2) != "0"
    return bool(m)


def chain_of(calls: list[dict]) -> dict:
    """How far the check chain got: the calls and the outcome of each step, the deepest step that passed."""
    steps = {name: {"calls": 0, "passed": False} for name in CHAIN}
    for c in calls:
        for name in work_scripts(c) & set(CHAIN):
            steps[name]["calls"] += 1
            steps[name]["passed"] |= step_passed(name, c["result"])
    passed = [name for name in CHAIN if steps[name]["passed"]]
    reached = [name for name in CHAIN if steps[name]["calls"]]
    return {"chain_depth": CHAIN.index(passed[-1]) + 1 if passed else 0, "chain_end": passed[-1] if passed else None,
            "chain_reached": reached[-1] if reached else None,
            "chain_attempts": sum(s["calls"] for s in steps.values()), "chain": steps}


def refused_plan(c: dict) -> bool:
    """An edit_sheet.py call that wrote nothing: the harness saw exit 1, or the refusal text came back."""
    return runs_script(c, "edit_sheet") and (c["failed"] or REFUSED in c["result"].replace(DRY_RUN_LINE, ""))


def project_edits(c: dict, project: Path) -> list[str]:
    """The project files the call tried to write, outside the dot folders (.tmp, .git, the skill copy): by a
    file tool, a shell command, or an inline script of one."""
    wrote = paths_of(c)[0]
    if c["tool"] in SHELLS:
        wrote = wrote + inline_writes(str(c["input"].get("command", "")))
    return [p for p in wrote if within(p, project) and (below := parts_below(p, project))
            and not any(part.startswith(".") for part in below)]


def edits(c: dict, project: Path) -> bool:
    """The call tries to change the project: a write to a file of it, failed or not, or an edit_sheet.py run, a dry
    run included, because the plan it checks is the edit. The lookups are over at the first of these."""
    return bool(project_edits(c, project)) or runs_script(c, "edit_sheet")


def clone_of(project: Path | None) -> Path | None:
    """The clone the project's instruction file names on its Construct3-RAG: line, read as the scripts read it."""
    for name in ("AGENTS.md", "CLAUDE.md"):
        try:
            value = c3project.rag_line((project / name).read_text(encoding="utf-8")) if project else None
        except OSError:
            value = None
        if value:
            return Path(value)
    return None


def clone_reads(calls: list[dict], clone: Path) -> tuple[int, int]:
    """The calls that read the clone's data/, and the calls that read the rest of it."""
    data = other = 0
    for c in calls:
        given = c["input"] if isinstance(c["input"], dict) else {}
        if c["tool"] in SHELLS:
            paths = read_paths(str(given.get("command", "")))
        else:
            path = absolute(str(given.get(FILE_READS.get(c["tool"], ""), ""))) if c["tool"] in FILE_READS else None
            paths = [path] if path else []
        if any(within(p, clone / "data") for p in paths):
            data += 1
        elif any(within(p, clone) for p in paths):
            other += 1
    return data, other


def printed_command_failures(calls: list[dict]) -> int:
    """Lost shell calls whose script word an earlier result printed, as a word or at the end of a longer path. A
    check that reported findings is not lost, so a copied check in the fix loop does not count."""
    seen: list[str] = []
    count = 0
    for c in calls:
        if c["tool"] in SHELLS and is_lost(c) and scripts_of(c):
            words = [a or b for a, b in SCRIPT_WORD.findall(c["what"]) if Path(a or b).stem in SCRIPT_NAMES]
            if any(w in r for w in words for r in seen):
                count += 1
        seen.append(c["result"])
    return count


def whole_sheet(args: list[str]) -> bool:
    """A print_sheet.py call that asked for whole sheets past its limit: --limit 0 without a part, a name to find,
    one event or the changes since a commit."""
    words = [a.strip("\"'") for a in args]
    unlimited = "--limit=0" in words or any(
        w == "--limit" and n + 1 < len(words) and words[n + 1] == "0" for n, w in enumerate(words))
    return unlimited and not {"--events", "--find", "--show", "--since"} & {w.split("=")[0] for w in words}


def summary(calls: list[dict], root: Path | None = None) -> dict:
    scripts = [{"script": name, "args": " ".join(args), "failed": c["failed"], "chars": c["chars"]}
               for c in calls for name, args in scripts_of(c)]
    by_tool: dict[str, dict[str, int]] = {}
    for c in calls:
        counts = by_tool.setdefault(c["tool"], {"calls": 0, "failed": 0})
        counts["calls"] += 1
        counts["failed"] += c["failed"]
    helps = dict(Counter(name for c in calls for name, args in scripts_of(c) if HELP & set(args)))
    first_script = next((n for c in calls for n, _ in scripts_of(c)), None)
    before_first = next((n for n, c in enumerate(calls) if scripts_of(c)), len(calls))
    out = {"tool_calls": len(calls), "lost_calls": sum(is_lost(c) for c in calls), "by_tool": by_tool,
           "scripts": scripts,
           "read_skill_md": any(c["chars"] is not None and not c["failed"] and (c["loads_skill"] or (
               c["tool"] in SHELLS and c["chars"] > SKILL_READ_CHARS and reads_skill_md(c["what"]))) for c in calls),
           "first_script": first_script, **chain_of(calls),
           "preview_failed": sum(1 for c in calls if work_scripts(c) and any(p in c["result"] for p in PREVIEW_FAILED)),
           "help_reads": sum(helps.values()), "repeat_help": sum(n - 1 for n in helps.values()),
           "help_reads_by_script": helps, "plan_refusals": sum(refused_plan(c) for c in calls),
           "hand_edits": None, "lookups_before_first_edit": None, "data_reads": None, "other_clone_reads": None,
           "entry_chars": sum(c["chars"] or 0 for c in calls[:before_first]),
           "printed_command_failures": printed_command_failures(calls),
           # each call once, though its command runs print_sheet.py more than once: the characters the run read back
           "print_sheet_chars": sum(c["chars"] or 0 for c in calls if any(n == "print_sheet" for n, _ in scripts_of(c))),
           "whole_sheet_prints": sum(1 for c in calls for name, args in scripts_of(c) if name == "print_sheet"
                                     and whole_sheet(args))}
    project = root / "project" if root else None
    if project and project.is_dir():
        out["hand_edits"] = sum(1 for c in calls if not c["failed"]
                                and any(p.lower().endswith(PROJECT_FILES) for p in project_edits(c, project)))
        out["lookups_before_first_edit"] = next((n for n, c in enumerate(calls) if edits(c, project)), None)
        clone = clone_of(project)
        if clone:
            out["data_reads"], out["other_clone_reads"] = clone_reads(calls, clone)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcript", nargs="?", metavar="TRANSCRIPT.jsonl")
    ap.add_argument("--out", metavar="RUN_DIR", help="write the counts to RUN_DIR/trace.json and copy the transcript "
                                                    "to RUN_DIR/transcript.jsonl")
    ap.add_argument("--root", metavar="FOLDER",
                    help="the folder the run may write in, for outside (default: RUN_DIR of --out)")
    ap.add_argument("--full", action="store_true", help="print commands and results unshortened")
    ap.add_argument("--list", metavar="SESSION_DIR", help="print the subagent transcripts of a session with their descriptions")
    args = ap.parse_args()
    c3project.utf8_output()

    if args.list:
        for meta in sorted(Path(args.list).glob("subagents/agent-*.meta.json")):
            about = json.loads(meta.read_text(encoding="utf-8"))
            print(f"{meta.with_suffix('').with_suffix('.jsonl')}  {about.get('model', '')}  {about.get('description', '')}")
        return 0
    if not args.transcript:
        ap.error("TRANSCRIPT.jsonl is required unless --list is given")

    transcript = Path(args.transcript).resolve()
    calls = calls_of(transcript)
    if not calls:
        print(f"{args.transcript} holds no tool call", file=sys.stderr)
        return 1
    width = 100_000 if args.full else 240
    for n, c in enumerate(calls, 1):
        print(f"{n:>3} {c['tool']:<6} {short(c['what'], width)}")
        print(f"      -> {c['chars']} chars{' FAILED' if c['failed'] else ''}: {short(c['result'], width)}")
    root = Path(args.root or args.out) if args.root or args.out else None
    counts = summary(calls, root) | usage_of(transcript)
    print(f"{counts['turns']} turns, {counts['output_tokens']} output tokens, {counts['input_tokens']} input tokens, "
          f"{counts['seconds']} s, {counts['model']}")
    print(f"{counts['tool_calls']} tool calls, {counts['lost_calls']} lost; scripts run: "
          + ", ".join(f"{s['script']} {s['args']}".strip() + (" (failed)" if s["failed"] else "") for s in counts["scripts"]))
    print(f"first script {counts['first_script']}, chain to {counts['chain_end']} ({counts['chain_depth']} of {len(CHAIN)}, "
          f"{counts['chain_attempts']} calls), {counts['help_reads']} help reads, {counts['plan_refusals']} refused plans, "
          + (f"{counts['hand_edits']} hand edits, {counts['lookups_before_first_edit']} calls before the first edit"
             if counts["hand_edits"] is not None else
             "hand edits and calls before the first edit need --out or --root with its project/"))
    if root:
        counts["outside"], counts["outside_reads"] = outside(calls, root)
        writes = counts["outside"]
        print(f"{len(writes)} write{'s' if len(writes) != 1 else ''} outside {root.resolve()}"
              + "".join(f"\n  {w['tool']}: {w['path']}" for w in writes))
    counts["transcript"] = str(transcript)
    if args.out:
        kept = Path(args.out) / "transcript.jsonl"
        if kept.resolve() != transcript:
            shutil.copyfile(transcript, kept)
        (Path(args.out) / "trace.json").write_text(json.dumps(counts, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

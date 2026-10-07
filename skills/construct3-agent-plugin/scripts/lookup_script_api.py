"""Look up the scripting API: an interface with its members, or a member by name.

    python scripts/lookup_script_api.py NAME [NAME ...] [--limit CHARS] [--project FOLDER] [--rag FOLDER]

NAME is an interface or class of the runtime API (`IRuntime`,
`ITimerBehaviorInstance`), a plugin or behavior by its name (`Sprite`,
`Timer`, `8 Direction`), a member (`callFunction`, `startTimer`), or a member
of one interface (`IRuntime.callFunction`, `ISpriteInstance.x`). A member of
one interface is searched in the interfaces it extends as well, so
`ISpriteInstance.x` finds `x` on `IWorldInstance`.

The declarations are the `.d.ts` files of
`Construct3-RAG/data/c3-ts-defs/`, without the addon SDK, and those under the
project's `scripts/ts-defs/` when the editor has written them
(`open_in_editor.py --typescript`): there `InstanceType.Coin` lists the
behaviors and instance variables of the project's own objects. The Claude
Code plugin keeps these `.d.ts` files in bundles, so there a declaration
shows the command that prints it instead of a file and line.

A grep for a name also hits the parameters and event maps that mention it.
This prints the declaration, the interface it belongs to, and its file and
line. A name the API does not declare prints the names that come near it.
"""
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import c3project as c3
from c3project import closest, squash

DECLARATION = re.compile(
    r"^\s*(?:export\s+)?(?:declare\s+)?(?:abstract\s+)?(class|interface|namespace|type|function|const|enum)\s+([\w$]+)")
MEMBER = re.compile(r"^\s*(?:(?:readonly|static|get|set|async|abstract)\s+)*([\w$]+)\s*[?]?\s*[<(:]")
# the suffixes an addon's interface carries after its name: Timer is ITimerBehaviorInstance
SUFFIXES = ("behaviorinstance", "instance", "behaviortype", "objecttype", "behaviors", "behavior", "plugin", "")
FULL = 6    # this many member hits or fewer print with their doc comment
# The declarations that hold members and answer to an addon's name; a type alias, function or const does not.
TYPES = ("class", "interface", "namespace")
# What a size member measures, where its name does not say. From the manual's scripting reference: iruntime,
# plugin-interfaces/sprite and plugin-interfaces/tiled-background. Printed under the member.
VIEWPORT = ("the project's viewport size from Project Properties, not the layout's size, which is "
            "runtime.layout.width and runtime.layout.height")
IN_LAYOUT = "not the instance's size in the layout, which is the instance's width and height"
SIZE_NOTES = {
    **{("IRuntime", name): VIEWPORT for name in ("viewportWidth", "viewportHeight", "getViewportSize")},
    **{("ISpriteInstance", name): f"the size in pixels of the current animation frame's source image, {IN_LAYOUT}"
       for name in ("imageWidth", "imageHeight", "getImageSize")},
    **{("ITiledBackgroundInstance", name): f"the size in pixels of the image without the tiling, {IN_LAYOUT}"
       for name in ("imageWidth", "imageHeight", "getImageSize")},
}


@dataclass
class Member:
    name: str
    text: str
    line: int
    doc: str = ""


@dataclass
class Declaration:
    kind: str
    name: str
    header: str
    file: str
    line: int
    extends: list[str] = field(default_factory=list)
    members: list[Member] = field(default_factory=list)


def without_generics(text: str) -> str:
    """The text with every <...> removed, nested ones too, so `extends` inside them is not read as inheritance."""
    out, depth = [], 0
    for ch in text:
        if ch == "<":
            depth += 1
        elif ch == ">" and depth:
            depth -= 1
        elif not depth:
            out.append(ch)
    return "".join(out)


def parse(text: str, shown: str) -> list[Declaration]:
    """The declarations of the text of a .d.ts file, each with the members written one level inside it. A declaration
    inside a namespace is named with it: the editor writes a project's objects as `InstanceType.Coin`."""
    found: list[Declaration] = []
    stack: list[list] = []      # [declaration, depth of its line, whether its body has opened]
    depth, doc, in_doc = 0, [], False
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if in_doc or line.startswith("/*"):
            in_doc = "*/" not in line
            doc.append(re.sub(r"^/?\*+/?|\*/$", "", line).strip())
            continue
        if line.startswith("//") or not line:
            doc = [] if not line else doc
            continue
        code = re.sub(r"//.*$", "", re.sub(r"\"[^\"]*\"|'[^']*'", '""', line))
        while stack and stack[-1][2] and depth <= stack[-1][1]:
            stack.pop()
        if stack and not stack[-1][2] and DECLARATION.match(line):
            stack.pop()         # a type alias on one line, which opens no body
        top = stack[-1] if stack else None
        m = DECLARATION.match(line)
        if m and (top is None or top[0].kind == "namespace" and depth == top[1] + 1):
            head = without_generics(line)
            extends = re.search(r"\bextends\s+(.+?)(?:\bimplements\b|\{|$)", head)
            d = Declaration(m.group(1), (top[0].name + "." if top else "") + m.group(2), line.rstrip("{ ").strip(),
                            shown, n, [e.strip() for e in extends.group(1).split(",") if e.strip()] if extends else [])
            found.append(d)
            stack.append([d, depth, False])
        elif top and top[2] and depth == top[1] + 1 and top[0].kind != "namespace":
            mm = MEMBER.match(line)
            if mm and mm.group(1) != "constructor":
                top[0].members.append(Member(mm.group(1), line, n, " ".join(d for d in doc if d)))
        doc = []
        depth = max(depth + code.count("{") - code.count("}"), 0)
        if stack and not stack[-1][2] and depth > stack[-1][1]:
            stack[-1][2] = True
    return found


def load_api(rag: Path, project: Path | None) -> list[Declaration]:
    """The declarations of the clone's API, then those of the project. The editor copies the whole API into
    scripts/ts-defs/ beside the project's own files, so a project file with the name of one of the clone's is
    skipped."""
    defs = rag / "data" / "c3-ts-defs"
    api = {k: text for k, text in c3.data_texts(rag, "data/c3-ts-defs", "*.d.ts").items() if "sdk" not in k.split("/")}
    # A file the plugin keeps only in a bundle has no path to open; where() shows the command instead
    files = [((defs / k).as_posix() if (defs / k).is_file() else "", text) for k, text in api.items()]
    names = {k.rpartition("/")[2] for k in api}
    own = project / "scripts" / "ts-defs" if project else None
    if own and own.is_dir():
        for path in sorted(own.rglob("*.d.ts")):
            if path.name not in names and "sdk" not in path.relative_to(own).parts:
                files.append((f"scripts/ts-defs/{path.relative_to(own).as_posix()}",
                              path.read_text(encoding="utf-8", errors="replace")))
    out = []
    for shown, text in files:
        out += parse(text, shown)
    return out


def where(d: Declaration, m: Member | None = None) -> str:
    """The file and line of a declaration or of one of its members, or the command that prints it when the
    declaration has no file to open."""
    if not d.file:
        return f"lookup_script_api.py {d.name}{f'.{m.name}' if m else ''}"
    return f"{d.file}:{m.line if m else d.line}"


def addon_keys(name: str) -> set[str]:
    """The keys a declaration answers to: its own name, and without the I and the suffix an addon's carries."""
    key = squash(name.rpartition(".")[2])
    keys = {key, squash(name)}
    bare = key[1:] if key.startswith("i") else key
    for suffix in SUFFIXES:
        if bare.endswith(suffix) and len(bare) > len(suffix):
            keys.add(bare[: len(bare) - len(suffix)] if suffix else bare)
    return keys


def ancestors(api: dict[str, list[Declaration]], name: str) -> list[Declaration]:
    """The declarations of name and of every one it extends, nearest first."""
    out, queue, seen = [], [name], set()
    while queue:
        n = queue.pop(0)
        if n in seen:
            continue
        seen.add(n)
        for d in api.get(n, []):
            out.append(d)
            queue += [e.split(".")[-1] for e in d.extends]
    return out


def heading(d: Declaration) -> list[str]:
    """The declaration's kind, name and place, then its header line."""
    return [f"{d.kind} {d.name}   {where(d)}", f"  {d.header}"]


def print_declaration(d: Declaration) -> list[str]:
    lines = heading(d)
    sizes = [SIZE_NOTES.get((d.name, m.name)) for m in d.members]
    for i, m in enumerate(d.members):
        lines.append(f"  {m.text}")
        # members side by side that measure the same size share one line, under the last of them
        if sizes[i] and (i + 1 == len(sizes) or sizes[i + 1] != sizes[i]):
            lines.append(f"  -- {sizes[i]}")
    if d.extends:
        lines.append(f"  -- members of {', '.join(d.extends)} are {d.name}'s too: "
                     f"lookup_script_api.py {d.extends[0]}, or {d.name}.NAME for one of them")
    return lines


def print_members(hits: list[tuple[Declaration, Member]]) -> list[str]:
    lines = []
    for d, m in hits:
        lines.append(f"{d.name}.{m.name}   {where(d, m)}")
        lines.append(f"  {m.text}")
        if (d.name, m.name) in SIZE_NOTES:
            lines.append(f"  -- {SIZE_NOTES[d.name, m.name]}")
        if m.doc and len(hits) <= FULL:
            lines.append(f"  /** {m.doc} */")
    return lines


def lookup(decls: list[Declaration], query: str) -> tuple[list[str], bool]:
    """The lines that answer query, and whether anything was found."""
    by_name: dict[str, list[Declaration]] = {}
    for d in decls:
        by_name.setdefault(d.name, []).append(d)
    owner, _, member = query.rpartition(".")
    if owner:
        known = {squash(n): n for n in by_name}
        target = known.get(squash(owner))
        if target:
            line = ancestors(by_name, target)
            hits = [(d, m) for d in line for m in d.members if m.name.lower() == member.lower()]
            if hits:
                return print_members(hits), True
            names = sorted({m.name for d in line for m in d.members})
            return [f"{target} and the interfaces it extends declare no {member!r}{closest(member, names)}; "
                    f"lookup_script_api.py {target} lists its members"], False
        # `runtime.callFunction`, `this.x`: an instance, not an interface; look the member up anywhere
        query = member

    lines: list[str] = []
    key = squash(query)
    named = [d for d in decls if d.kind in TYPES and key in addon_keys(d.name)]
    named += [d for d in decls if d.kind not in TYPES and squash(d.name) == key]
    for d in named:
        lines += print_declaration(d) if d.kind in TYPES else heading(d)
    exact = [(d, m) for d in decls for m in d.members if m.name.lower() == query.lower()]
    if exact:
        lines += print_members(exact)
    if lines:
        return lines, True
    near = [(d, m) for d in decls for m in d.members if key and key in squash(m.name)]
    if near:
        return ([f"no member is named {query!r}; members whose name holds it:"]
                + [f"{d.name}.{m.name}   {where(d, m)}" for d, m in near]), True
    names = {d.name for d in decls} | {m.name for d in decls for m in d.members}
    return [f"the scripting API declares no {query!r}{closest(query, names)}"], False


def main() -> int:
    ap = c3.argument_parser(
        "Look up the Construct 3 scripting API: an interface with its members, or a member with the interface "
        "it belongs to, its declaration and the file and line it is on. Use it before calling an API in a "
        "script, and before saying that a call in a script does not exist.",
        "examples:\n"
        "  python scripts/lookup_script_api.py IRuntime                  an interface and its members\n"
        "  python scripts/lookup_script_api.py Timer                     a behavior or plugin by name\n"
        "  python scripts/lookup_script_api.py callFunction              a member, on whichever interface has it\n"
        "  python scripts/lookup_script_api.py ISpriteInstance.x         a member, inherited ones included\n"
        "  python scripts/lookup_script_api.py setAnimation startTimer   several names, one after another\n\n"
        "exit codes: 0 every NAME was found, 1 a NAME was not (the nearest names are listed), or the clone\n"
        "was not found")
    ap.add_argument("names", nargs="+", metavar="NAME",
                    help="an interface, a plugin or behavior name, a member, or INTERFACE.MEMBER")
    args = ap.parse_args()
    c3.utf8_output()
    root = c3.find_project(args.project)
    if root and not (root / "project.c3proj").exists():
        root = None
    rag = c3.find_rag(root, args.rag)
    c3.note_drift(rag)
    decls = load_api(rag, root)
    lines, missing = [], 0
    for name in args.names:
        found, ok = lookup(decls, name)
        missing += not ok
        if lines:
            lines.append("")
        lines += found
    shown = c3.fitting(lines, args.limit)
    print("\n".join(lines[:shown]))
    if shown < len(lines):
        print(f"-- {len(lines) - shown} more lines; name the member as INTERFACE.MEMBER, or pass --limit 0 for all")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())

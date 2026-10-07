"""The Advanced Random plugin of Construct 3 in Python: one seed string gives the same numbers
as in the game.

    python scripts/advanced_random.py SEED [--count N] [--table JSON] [--limit CHARS]
    python scripts/advanced_random.py --check [--runtime C3RUNTIME.js | --preview] [--project FOLDER]
                                      [--release rNNN] [--browser EXE]

Use it to design odds and to reproduce a run offline: what the game draws for a seed,
without the editor or a preview. It follows plugins/AdvancedRandom of the runtime:

- Update seed hashes the seed string with djb2 to an unsigned 32-bit integer, seeds
  xoshiro256** with splitmix64 from it, then draws 768 numbers for the noise tables
  (256 gradients of two numbers, then a permutation of 256), before Random or a
  table draws anything.
- Random is the top 53 bits of xoshiro256** divided by 2^53, in [0, 1).
- Weighted and WeightedByName draw one number in [0, total weight) and return the
  first entry whose running sum of weights exceeds it. Creating a table draws nothing.
- Create permutation table holds `length` numbers from `offset`, shuffled with
  Fisher-Yates from the last one down; a length below 2 is not shuffled and draws nothing.

As a module, from a script in another folder:

    import importlib.util
    spec = importlib.util.spec_from_file_location("advanced_random", "<this file>")
    ar = importlib.util.module_from_spec(spec); spec.loader.exec_module(ar)
    r = ar.AdvancedRandom("ABCDEFGHIJ")
    r.random()                                      # AdvancedRandom.Random
    r.table_from_json("cards", '[[3,"dango1"],[1,"sword"]]')
    r.weighted_by_name("cards")                     # AdvancedRandom.WeightedByName("cards")
    r.create_permutation(5, 0); r.permutation(2)    # Create permutation table, AdvancedRandom.Permutation(2)

--check runs the plugin's own code with node and compares it with this one, value by
value: the hash, Random, both kinds of table draw and the permutation tables, over
several seeds. The code comes from the project's Web export, the newest
scripts/c3runtime.js below the project, or --runtime. An export carries the runtime of
the release that made it; --preview instead opens the project in the editor, as
open_in_editor.py does, runs a preview and takes the plugin's code from the preview
window, which is what F5 runs in that release. Run --check after Construct updates: a
change of the plugin's algorithm shows as a difference, and a change of its code's shape
stops the check with what it no longer found.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random as _random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

M64 = (1 << 64) - 1
GOLDEN = 0x9E3779B97F4A7C15
TWO53 = float(1 << 53)
NOISE_DRAWS = 256 * 2 + 256     # the gradients, two numbers each, then the noise permutation

EPILOG = """examples:
  python scripts/advanced_random.py ABCDEFGHIJ                     the first 10 Random values of a seed
  python scripts/advanced_random.py "run7:card:3" --count 3
  python scripts/advanced_random.py ABCDEFGHIJ --table "[[3,\\"dango\\"],[1,\\"sword\\"]]" --count 20
  python scripts/advanced_random.py --check                        against the project's export
  python scripts/advanced_random.py --check --runtime export/web/scripts/c3runtime.js
  python scripts/advanced_random.py --check --preview              against what the editor's preview runs

output:
  SEED: one Random value per line, as JavaScript prints it
  SEED --table: one draw of WeightedByName per line, a text value in quotes
  --check:
    runtime: <file, or the editor release of the preview>
    same: <seeds>, each compared on ...
    differs: seed '<seed>', step <n> <operation>: game <values>, here <values>

exit codes: 0 printed, or --check found every value the same; 1 --check found a difference, or the
runtime code no longer has the shape this script reads; 2 a flag that cannot be used, no runtime
found, no node, or the preview did not run
"""


# --- the algorithm ----------------------------------------------------------------------------
def _int32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - (1 << 32) if x & 0x80000000 else x


def _utf16_units(text: str) -> list[int]:
    """The units charCodeAt reads: UTF-16, so a character outside the BMP is two."""
    data = text.encode("utf-16-le", "surrogatepass")
    return [int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data), 2)]


def seed_hash(seed: str) -> int:
    """The integer _UpdateSeed seeds with: djb2 over the UTF-16 units, where `t << 5` wraps to a
    signed 32-bit integer and the sum stays a JavaScript number until `t >>>= 0` at the end."""
    t = 5381
    for unit in _utf16_units(seed):
        t = _int32(_int32(t) << 5) + t + unit
    return t & 0xFFFFFFFF


def _rotl(x: int, k: int) -> int:
    return ((x << k) | (x >> (64 - k))) & M64


def random_seed(length: int = 10) -> str:
    """AdvancedRandom.RandomSeed: ten capital letters from Math.random. Not reproducible; for a new run."""
    return "".join(chr(round(25 * _random.random()) + 65) for _ in range(length))


def _strict_equal(a, b) -> bool:
    """JavaScript's ===: a text never equals a number, 7 equals 7.0."""
    return isinstance(a, str) == isinstance(b, str) and a == b


class ProbabilityTable:
    """C3.ProbabilityTable: [weight, value] entries and a total weight kept as the runtime keeps
    it, added to and subtracted from, so that a draw after a removal sees the same total."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.items: list[list] = []
        self.total = 0

    def add(self, weight, value) -> None:
        self.total += weight
        self.items.append([weight, value])

    def remove(self, weight, value) -> None:
        """The first entry of that value, of that weight unless the weight is 0."""
        for i, (w, v) in enumerate(self.items):
            if (weight == 0 or w == weight) and _strict_equal(v, value):
                del self.items[i]
                self.total -= w
                return

    def sample(self, roll):
        acc = 0
        for w, v in self.items:
            acc += w
            if roll < acc:
                return v
        return 0


class AdvancedRandom:
    """One Advanced Random object: its seeded sequence, its probability tables and its
    permutation table. Each method is the action or expression of the same name."""

    def __init__(self, seed: str | None = None) -> None:
        self.tables: dict[str, ProbabilityTable] = {}
        self.current: ProbabilityTable | None = None
        self.perm: list = [0]
        self.create_table("default")
        self.update_seed(random_seed() if seed is None else seed)

    # The seed and the sequence

    def update_seed(self, seed: str) -> None:
        """Update seed: the sequence starts again, so the same string gives the same numbers."""
        self.seed = seed
        self._split = seed_hash(seed)
        self._s = [self._splitmix() for _ in range(4)]
        self._splitmix()
        self._splitmix()
        for _ in range(NOISE_DRAWS):
            self._next()

    def _splitmix(self) -> int:
        self._split = (self._split + GOLDEN) & M64
        t = self._split
        t = ((t ^ (t >> 30)) * 0xBF58476D1CE4E5B9) & M64
        t = ((t ^ (t >> 27)) * 0x94D049BB133111EB) & M64
        return t ^ (t >> 31)

    def _next(self) -> int:
        s = self._s
        out = (_rotl((s[1] * 5) & M64, 7) * 9) & M64
        t = (s[1] << 17) & M64
        s[2] ^= s[0]
        s[3] ^= s[1]
        s[1] ^= s[2]
        s[0] ^= s[3]
        s[2] ^= t
        s[3] = _rotl(s[3], 45)
        return out

    def random(self, lo: float = 0.0, hi: float = 1.0) -> float:
        """AdvancedRandom.Random for [0, 1); the runtime's draw in [lo, hi) otherwise."""
        return (self._next() >> 11) / TWO53 * (hi - lo) + lo

    # Probability tables

    def create_table(self, name: str) -> None:
        """Create probability table: an empty table, made the current one. Draws nothing."""
        self.current = self.tables[name.lower()] = ProbabilityTable(name)

    def table_from_json(self, name: str, text) -> None:
        """Create probability table from JSON, [[weight, value], ...], made the current one. Draws nothing."""
        table = ProbabilityTable(name)
        for weight, value in json.loads(text) if isinstance(text, str) else text:
            table.add(weight, value)
        self.current = self.tables[name.lower()] = table

    def set_table(self, name: str) -> None:
        """Set current probability table; a name with no table leaves none current."""
        self.current = self.tables.get(name.lower())

    def add_entry(self, value, weight) -> None:
        """Add probability entry, at the end of the current table."""
        if self.current:
            self.current.add(weight, value)

    def remove_entry(self, value, weight=0) -> None:
        """Remove probability entry: the first of that value, of that weight unless the weight is 0."""
        if self.current:
            self.current.remove(weight, value)

    def _sample(self, table: ProbabilityTable | None):
        return table.sample(self.random(0, table.total)) if table else 0

    def weighted(self):
        """AdvancedRandom.Weighted: a draw from the current table, 0 when there is none."""
        return self._sample(self.current)

    def weighted_by_name(self, name: str):
        """AdvancedRandom.WeightedByName: the name ignores case; 0 for a table that does not exist."""
        return self._sample(self.tables.get(name.lower()))

    # The permutation table

    def create_permutation(self, length: float, offset: float = 0) -> None:
        """Create permutation table: offset, offset + 1, ... below offset + length, shuffled. A
        length below 2 holds the offset alone and draws nothing."""
        if length < 2:
            self.perm = [offset]
            return
        self.perm = [offset + i for i in range(math.ceil(length))]
        self.shuffle_permutation()

    def shuffle_permutation(self) -> None:
        """Shuffle permutation table: Fisher-Yates, one draw per entry, from the last one down."""
        p = self.perm
        r = len(p)
        while r > 0:
            i = math.floor(self.random(0, r))
            r -= 1
            p[r], p[i] = p[i], p[r]

    def permutation(self, index: float):
        """AdvancedRandom.Permutation: the index rounded down, wrapped by the length, a negative
        one counted from the end."""
        return self.perm[math.floor(index) % len(self.perm)]


# --- --check: the plugin's own code, run by node ----------------------------------------------
class ShapeChanged(Exception):
    """The runtime code no longer has the parts this script reads."""


CASES = ["ABCDEFGHIJ", "", "seed:stage:12", "QWERTYUIOP:card:137", "种子🙂", "x" * 300]
TABLE = [[3, "dango1"], [1.5, "dango2"], [0.25, "sword"], [2, 7]]
# The same steps for every seed, as actions and expressions of the plugin. Creating tables
# between two Random steps shows that it draws nothing; the pool's removals that its running
# total weight is kept as the runtime keeps it.
STEPS = [
    ["random", 50],
    ["table_json", "Loot", json.dumps(TABLE)],
    ["random", 3],
    ["weighted_by_name", "LOOT", 50],
    ["table", "pool"], ["add", "a", 2], ["add", 7, 0.5], ["add", "b", 0.1], ["add", "c", 0.2],
    ["remove", "b", 0], ["remove", 7, 0.25], ["remove", "7", 0], ["weighted", 30],
    ["set_table", "loot"], ["weighted", 5], ["weighted_by_name", "missing", 2],
    ["perm", 9, 3], ["perm_all"], ["permutation", -1], ["permutation", 2.7], ["shuffle"], ["perm_all"],
    ["perm", 2.5, 0], ["perm_all"], ["perm", 1, 4], ["perm_all"], ["random", 5],
    ["seed", None], ["random", 5],
]
COMPARED = "the hash, Random, WeightedByName and Weighted after tables were created, added to and removed " \
           "from, permutation tables created, read and shuffled, and Update seed again"

# What the plugin's code needs of the runtime around it to load and to construct an instance.
HARNESS_HEAD = r"""
globalThis.self = globalThis;
const noop = () => 0;
self.C3 = {Plugins: {}, clamp: (x, a, b) => Math.min(Math.max(x, a), b), lerp: (a, b, x) => a + (b - a) * x,
  PackRGBEx: noop, PackRGBAEx: noop, GetRValue: noop, GetGValue: noop, GetBValue: noop, GetAValue: noop,
  IsString: x => typeof x === "string", clear2DArray: a => { a.length = 0; },
  SDKPluginBase: class { constructor() {} Release() {} },
  SDKTypeBase: class { constructor() {} Release() {} },
  SDKInstanceBase: class { constructor() { this._runtime = {SetRandomNumberGeneratorCallback() {}}; } Release() {} }};
self.C3X = new Proxy({}, {get: () => noop});
self.IObjectType = class {};
"""

HARNESS_TAIL = r"""
const P = C3.Plugins.AdvancedRandom || {}, A = P.Acts || {}, X = P.Exps || {}, F = P.NoiseFuncs || {};
const need = {"C3.ProbabilityTable": C3.ProbabilityTable, "C3.Plugins.AdvancedRandom.Instance": P.Instance,
  "NoiseFuncs.seed": F.seed};
for (const n of ["SetSeed", "CreateProbabilityTable", "CreateProbabilityTableFromJSON", "SetProbabilityTable",
                 "AddProbabilityEntry", "RemoveProbabilityEntry", "CreatePermutationTable", "ShufflePermutationTable"])
  need["Acts." + n] = A[n];
for (const n of ["Random", "Weighted", "WeightedByName", "Permutation", "Seed"]) need["Exps." + n] = X[n];
const missing = Object.keys(need).filter(k => typeof need[k] !== "function");
if (missing.length) { process.stdout.write(JSON.stringify({missing})); process.exit(0); }
let hash = null;
const seed = F.seed;
F.seed = function (t) { hash = t; return seed.call(this, t); };
const out = [];
for (const c of CASES) {
  // The seed property "" would give the instance a random seed, so it starts on another one.
  const inst = new P.Instance(null, ["start", false]), n = k => Array.from({length: k});
  hash = null;
  A.SetSeed.call(inst, c);
  const got = [[hash, X.Seed.call(inst)]];
  for (const [op, a, b] of STEPS) {
    switch (op) {
      case "random": got.push(n(a).map(() => X.Random.call(inst))); break;
      case "table_json": A.CreateProbabilityTableFromJSON.call(inst, a, b); got.push(null); break;
      case "table": A.CreateProbabilityTable.call(inst, a); got.push(null); break;
      case "set_table": A.SetProbabilityTable.call(inst, a); got.push(null); break;
      case "add": A.AddProbabilityEntry.call(inst, a, b); got.push(null); break;
      case "remove": A.RemoveProbabilityEntry.call(inst, a, b); got.push(null); break;
      case "weighted": got.push(n(a).map(() => X.Weighted.call(inst))); break;
      case "weighted_by_name": got.push(n(b).map(() => X.WeightedByName.call(inst, a))); break;
      case "perm": A.CreatePermutationTable.call(inst, a, b); got.push(null); break;
      case "shuffle": A.ShufflePermutationTable.call(inst); got.push(null); break;
      case "perm_all": got.push(n(Math.max(inst._permutation.length, 1)).map((_, i) => X.Permutation.call(inst, i))); break;
      case "permutation": got.push(X.Permutation.call(inst, a)); break;
      case "seed": hash = null; A.SetSeed.call(inst, c); got.push([hash, X.Seed.call(inst)]); break;
      default: throw new Error("unknown step " + op);
    }
  }
  out.push(got);
}
process.stdout.write(JSON.stringify({out}));
"""


def run_here(case: str) -> list:
    """The STEPS on this module, in the shape the harness returns."""
    r = AdvancedRandom(case)
    got: list = [[seed_hash(case), r.seed]]
    for op, *args in STEPS:
        a, b = (args + [None, None])[:2]
        if op == "random":
            got.append([r.random() for _ in range(a)])
        elif op in ("table_json", "table", "set_table", "add", "remove", "perm", "shuffle"):
            {"table_json": lambda: r.table_from_json(a, b), "table": lambda: r.create_table(a),
             "set_table": lambda: r.set_table(a), "add": lambda: r.add_entry(a, b),
             "remove": lambda: r.remove_entry(a, b), "perm": lambda: r.create_permutation(a, b),
             "shuffle": r.shuffle_permutation}[op]()
            got.append(None)
        elif op == "weighted":
            got.append([r.weighted() for _ in range(a)])
        elif op == "weighted_by_name":
            got.append([r.weighted_by_name(a) for _ in range(b)])
        elif op == "perm_all":
            got.append([r.permutation(i) for i in range(len(r.perm))])
        elif op == "permutation":
            got.append(r.permutation(a))
        elif op == "seed":
            r.update_seed(case)
            got.append([seed_hash(case), r.seed])
    return got


# A file of the runtime in a Web export starts with a line `// <path>` and a line `{`.
SECTION = re.compile(r"^// (\S+\.js)\n\{\n", re.M)
PLUGIN_FILE = re.compile(r"(?:^|/)advancedrandom/c3runtime/([\w.-]+\.js)$", re.I)
TABLE_FILE = re.compile(r"(?:^|/)lib/misc/probability\.js$")


def pick_sources(files: dict[str, str]) -> list[tuple[str, str]]:
    """The probability table and the plugin's runtime files, in the order they load: the table,
    the plugin's runtime.js, which defines the plugin, then its other files."""
    table = [(n, code) for n, code in files.items() if TABLE_FILE.search(n)]
    plugin = [(n, code) for n, code in files.items() if PLUGIN_FILE.search(n)]
    plugin.sort(key=lambda f: PLUGIN_FILE.search(f[0]).group(1).lower() != "runtime.js")
    lacking = [what for what, found in (("lib/misc/probability.js", table),
                                        ("plugins/AdvancedRandom/c3runtime/runtime.js",
                                         [f for f in plugin if f[0].lower().endswith("/runtime.js")]))
               if not found]
    if lacking:
        raise ShapeChanged(f"no file {' or '.join(lacking)} among {len(files)} runtime files")
    return table[:1] + plugin


def export_sources(c3runtime: Path) -> list[tuple[str, str]]:
    """The files of the plugin and its probability table, cut out of an exported c3runtime.js."""
    text = c3runtime.read_text(encoding="utf-8").replace("\r\n", "\n")
    marks = list(SECTION.finditer(text))
    if not marks:
        raise ShapeChanged(f"{c3runtime} holds no `// <path>.js` section headers, so its files cannot be told apart")
    files = {m.group(1): text[m.start():marks[i + 1].start() if i + 1 < len(marks) else len(text)]
             for i, m in enumerate(marks)}
    return pick_sources(files)


def compare(sources: list[tuple[str, str]], node: str) -> tuple[list[str], int]:
    """The differences between the plugin's code run by node and this module, and the values compared."""
    script = "\n".join([HARNESS_HEAD, f"const CASES = {json.dumps(CASES)}, STEPS = {json.dumps(STEPS)};",
                        # each file in a block of its own, as the export wraps it: a preview loads
                        # each as a script, and two of them declare `const C3` at the top
                        *(f"// {name}\n{{\n{code}\n}}" for name, code in sources), HARNESS_TAIL])
    try:
        p = subprocess.run([node, "-"], input=script, capture_output=True, text=True, encoding="utf-8", timeout=60)
    except subprocess.TimeoutExpired:
        raise ShapeChanged("node ran the plugin's code for 60 seconds without an answer") from None
    if p.returncode:
        error = next((line for line in p.stderr.splitlines() if re.match(r"\w*Error\b", line)), p.stderr.strip()[-500:])
        raise ShapeChanged(f"node could not run the plugin's code with this script's stand-in runtime: {error}")
    answer = json.loads(p.stdout)
    if "missing" in answer:
        raise ShapeChanged(f"the plugin's code no longer defines {', '.join(answer['missing'])}")
    differences, values = [], 0
    for case, game in zip(CASES, answer["out"]):
        here = json.loads(json.dumps(run_here(case)))      # as JSON carries it: tuples become lists
        for step, (want, got) in enumerate(zip(game, here)):
            values += len(want) if isinstance(want, list) else want is not None
            if want != got:
                name = "start" if step == 0 else " ".join(map(str, STEPS[step - 1][:2]))
                differences.append(f"differs: seed {case[:24]!r}, step {step} {name}: game {json.dumps(want)[:160]}, "
                                   f"here {json.dumps(got)[:160]}")
                break   # the sequence is shared, so every later step differs as well
    return differences, values


def find_export(project: Path) -> Path | None:
    """The newest scripts/c3runtime.js below the project, outside .git, .tmp, .claude and node_modules."""
    found = []
    for folder, subfolders, files in os.walk(project):
        subfolders[:] = [s for s in subfolders if s not in (".git", ".tmp", ".claude", "node_modules")]
        if "c3runtime.js" in files and Path(folder).name == "scripts":
            found.append(Path(folder) / "c3runtime.js")
    return max(found, key=lambda f: f.stat().st_mtime, default=None)


PREVIEW_WAIT = 20   # seconds for the preview's runtime to start ticking; about 3 with a warm profile


def preview_sources(project: Path, release: str | None, exe: str | None) -> tuple[list[tuple[str, str]], str]:
    """The plugin's files as the editor's preview loaded them, with the editor release they came from.

    The project is opened and previewed as open_in_editor.py --preview does, in the same browser
    profile. Once the runtime ticks, the debugger of the preview window and of each of its
    workers lists the scripts it parsed, and their source is read from there: the code that runs,
    not a copy fetched again."""
    import open_in_editor as oe
    exe = exe or oe.browser_path()
    if not exe:
        raise RuntimeError("no Edge, Chrome or Chromium here to run the preview; pass --browser or --runtime")
    editor = f"{oe.EDITOR}{release.strip('/')}/" if release else oe.EDITOR
    browser = oe.Browser(exe, oe.scratch(project) / f"editor-{Path(exe).stem.lower()}", False)

    def then(b, target, page) -> dict:
        started = oe.start_preview(b, target, page)
        if isinstance(started, list):
            return {"errors": started}
        window, win = started
        try:
            sessions, live, stalled = oe.attach(win, patience=PREVIEW_WAIT)
            if not live:
                return {"errors": ["the runtime loaded but did not tick" if stalled else
                                   f"no runtime ticked in the preview window within {PREVIEW_WAIT} seconds"]}
            files: dict[str, str] = {}
            for session in sessions:
                first = len(win.events)
                win.call("Debugger.enable", wait=20, session=session)
                parsed = [e["params"] for e in win.events[first:] if e["method"] == "Debugger.scriptParsed"]
                for script in parsed:
                    if PLUGIN_FILE.search(script["url"]) or TABLE_FILE.search(script["url"]):
                        files[script["url"]] = win.call("Debugger.getScriptSource", wait=20, session=session,
                                                        scriptId=script["scriptId"])["scriptSource"]
                win.call("Debugger.disable", session=session)
            return {"files": files}
        finally:
            win.ws.close()
            b.devtools.call("Target.closeTarget", targetId=window["targetId"])

    try:
        result = oe.open_one(browser, editor, project, browser.profile / "project-0.c3p", None, bool(release), then)
    finally:
        browser.close()
    ran = result.get("preview") or {}
    if result["status"] != "opened":
        raise RuntimeError(f"the editor did not open the project: "
                           f"{'; '.join(result['dialogs']) or result['exception'] or result['status']}; "
                           f"run open_in_editor.py for the whole message")
    if "files" not in ran:
        raise RuntimeError(f"the preview did not run: {'; '.join(ran.get('errors', [])) or 'no answer'}")
    if not any(PLUGIN_FILE.search(u) for u in ran["files"]):
        raise RuntimeError("the preview loaded no Advanced Random code: the project has no Advanced Random object")
    where = re.search(r"editor\.construct\.net/(r[\d-]+)/", next(iter(ran["files"])))
    return pick_sources(ran["files"]), f"the preview of the editor {where.group(1) if where else result['editor']}"


def check(args) -> int:
    import c3project as c3
    node = shutil.which("node")
    if not node:
        print("--check runs the plugin's code with node, and no node is on PATH: install Node.js or add it to PATH",
              file=sys.stderr)
        return 2
    project = c3.find_project(args.project)
    note = None
    try:
        if args.runtime:
            runtime = Path(args.runtime)
            if not runtime.is_file():
                print(f"no file {runtime}: pass the c3runtime.js of a Web export, its scripts/c3runtime.js",
                      file=sys.stderr)
                return 2
            sources, where = export_sources(runtime), str(runtime)
        elif args.preview or not (project and find_export(project)):
            if not project:
                print("no project.c3proj found from here upward, so there is no export or preview to compare with: "
                      "pass --project <folder> or --runtime <c3runtime.js>", file=sys.stderr)
                return 2
            if not args.preview:
                print(f"no Web export below {project}, so the plugin's code is taken from the editor's preview")
            sources, where = preview_sources(project, args.release, args.browser)
        else:
            runtime = find_export(project)
            sources, where = export_sources(runtime), str(runtime)
            made = time.strftime("%Y-%m-%d %H:%M", time.localtime(runtime.stat().st_mtime))
            where += f" (exported {made})"
            if (project / "project.c3proj").stat().st_mtime > runtime.stat().st_mtime:
                note = ("project.c3proj changed after this export, which runs the release it was made with: if the "
                        "editor was updated since, run --check --preview to compare what the editor runs now")
    except ShapeChanged as e:
        print(f"the runtime code no longer has the shape this script reads: {e}. Read the plugin's code and update "
              f"advanced_random.py before trusting its numbers")
        return 1
    except (RuntimeError, OSError) as e:
        print(f"no runtime to compare with: {e}", file=sys.stderr)
        return 2
    print(f"runtime: {where}")
    try:
        differences, values = compare(sources, node)
    except ShapeChanged as e:
        print(f"the runtime code no longer has the shape this script reads: {e}. Read the plugin's code and update "
              f"advanced_random.py before trusting its numbers")
        return 1
    for line in differences:
        print(line)
    if differences:
        print(f"{len(differences)} of {len(CASES)} seeds differ: the plugin's algorithm changed. Do not use these "
              f"numbers until advanced_random.py follows the plugin's code again")
    else:
        print(f"same: {len(CASES)} seeds, {values} values in all, compared on {COMPARED}")
    if note:
        print(note)
    return 1 if differences else 0


# --- the command line -------------------------------------------------------------------------
def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import c3project as c3
    c3.utf8_output()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].replace("\n", " "), epilog=EPILOG,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("seed", nargs="?", metavar="SEED", help="the seed string, as Update seed is given it")
    ap.add_argument("--count", type=int, default=10, metavar="N", help="values to print (default: 10)")
    ap.add_argument("--table", metavar="JSON",
                    help="a probability table as Create probability table from JSON takes it, [[weight, value], ...]: "
                         "print N draws of WeightedByName from it, made right after Update seed")
    ap.add_argument("--check", action="store_true",
                    help="run the plugin's code with node and compare it with this script, value by value")
    ap.add_argument("--runtime", metavar="C3RUNTIME.js",
                    help="for --check: the scripts/c3runtime.js of a Web export (default: the newest one below the "
                         "project, else the editor's preview)")
    ap.add_argument("--preview", action="store_true",
                    help="for --check: take the plugin's code from a preview in the editor, as F5 runs it, instead of "
                         "an export; needs Edge, Chrome or Chromium and the network")
    ap.add_argument("--release", metavar="rNNN",
                    help="for --preview: the editor release, as its URL spells it (default: the current stable one)")
    ap.add_argument("--browser", metavar="EXE", help="for --preview: the Chromium-based browser to start")
    ap.add_argument("--project", metavar="FOLDER",
                    help="the folder that holds project.c3proj (default: found from the current directory upward)")
    ap.add_argument("--limit", type=int, default=c3.LIMIT, metavar="CHARS",
                    help=f"stop after about this many characters and say how to get the rest, since a harness cuts "
                         f"longer tool output; 0 prints everything (default: {c3.LIMIT})")
    args = ap.parse_args()

    if args.check:
        if args.seed is not None or args.table:
            ap.error("--check takes no SEED or --table")
        if args.runtime and args.preview:
            ap.error("--runtime and --preview name two runtimes; pass one")
        return check(args)
    if args.runtime or args.preview or args.release or args.browser:
        ap.error("--runtime, --preview, --release and --browser go with --check")
    if args.seed is None:
        ap.error("give a SEED, or --check")
    if args.count < 0:
        ap.error("--count is a number of values, 0 or more")
    r = AdvancedRandom(args.seed)
    if args.table:
        try:
            r.table_from_json("table", args.table)
        except (ValueError, TypeError) as e:
            ap.error(f"--table is not [[weight, value], ...]: {e}")
        lines = [json.dumps(r.weighted_by_name("table"), ensure_ascii=False) for _ in range(args.count)]
    else:
        # repr is the shortest text that reads back as the same number, as JavaScript's own
        lines = [repr(r.random()) for _ in range(args.count)]
    shown = c3.fitting(lines, args.limit)
    print("\n".join(lines[:shown]))
    if shown < len(lines):
        print(f"{len(lines) - shown} more values; --limit 0 prints them all")
    return 0


if __name__ == "__main__":
    sys.exit(main())

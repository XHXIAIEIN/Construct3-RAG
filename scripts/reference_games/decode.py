"""Decode a published Construct 3 export into readable event sheets and a project summary.

    python -m scripts.reference_games decode <folder> [more folder names]

Writes the ignored workspace's ``decoded/<game>/``: ``sheets/<sheet>.txt``, ``summary.json``, ``summary.md`` and
``aces.jsonl`` (one line per condition or action, for statistics across games).

ACE names come from the runtime's object reference table and parameter names from the
repository's schemas (``data/c3-schemas/en-US``). Exports whose runtime was minified with
mangled names have no readable reference table; their ACEs print as ``ace#N`` and only
object, variable, group and constant names survive.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from .catalog import DECODED, REPO

SCHEMAS = REPO / "data" / "c3-schemas" / "en-US"


# ---------------------------------------------------------------- runtime tables

def balanced(src: str, start: int) -> str:
    depth, i, quote, esc = 0, start, None, False
    while i < len(src):
        c = src[i]
        if quote:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == quote:
                quote = None
        elif c in "\"'`":
            quote = c
        elif c in "[({":
            depth += 1
        elif c in "])}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    raise ValueError("unbalanced")


def split_top(body: str) -> list[str]:
    out, cur, depth, quote, esc = [], [], 0, None, False
    for c in body:
        if quote:
            cur.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == quote:
                quote = None
            continue
        if c in "\"'`":
            quote = c
        elif c in "[({":
            depth += 1
        elif c in "])}":
            depth -= 1
        if c == "," and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(c)
    if cur:
        out.append("".join(cur))
    return out


def runtime_tables(game: Path) -> tuple[list[str] | None, list[str] | None]:
    for name in ("scripts/c3runtime.js", "scripts/c3main.js", "scripts/workermain.js"):
        f = game / name
        if not f.exists():
            continue
        src = f.read_text(encoding="utf-8", errors="replace")
        refs = funcs = None
        m = re.search(r"C3_GetObjectRefTable\s*=\s*function\s*\(\)\s*\{\s*return\s*", src)
        if m:
            arr = balanced(src, src.index("[", m.end()))
            refs = [re.sub(r"^.*?\b(Plugins|Behaviors|ScriptsInEvents)\.", r"\1.", r.strip()) for r in split_top(arr[1:-1])]
        m = re.search(r"C3_ExpressionFuncs\s*=\s*", src)
        if m:
            arr = balanced(src, src.index("[", m.end()))
            funcs = split_top(arr[1:-1])
        elif src.rstrip().endswith("]}"):
            end = src.rstrip().rfind("]")
            depth, i = 0, end
            while i >= 0:
                if src[i] == "]":
                    depth += 1
                elif src[i] == "[":
                    depth -= 1
                    if depth == 0:
                        break
                i -= 1
            try:
                funcs = split_top(src[i + 1:end])
            except ValueError:
                funcs = None
        if refs or funcs:
            return refs, funcs
    return None, None


# ---------------------------------------------------------------- schemas

_schema_cache: dict[str, dict] = {}


def schema_for(addon: str, kind: str) -> dict | None:
    key = f"{kind}:{addon.lower()}"
    if key in _schema_cache:
        return _schema_cache[key]
    f = SCHEMAS / kind / f"{addon.lower()}.json"
    data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    _schema_cache[key] = data
    return data


COMMON = schema_for("_common", "plugins")

# The schemas order combo items as the language file does; an export stores a combo as an
# index into the editor's ACE definition, so the order comes from the cached allAces.json.
ALL_ACES: dict[tuple[str, str, str], list[dict]] = {}
_cache = sorted((REPO / ".cache" / "c3-cdn").glob("r*/plugins_allAces.json"))
for kind_file in _cache[-1:]:
    for fname in ("plugins_allAces.json", "behaviors_allAces.json"):
        data = json.loads((kind_file.parent / fname).read_text(encoding="utf-8"))
        for addon, cats in data.items():
            for cat in cats.values():
                for table in ("conditions", "actions", "expressions"):
                    for entry in cat.get(table, []):
                        ALL_ACES[(addon.lower(), table, entry.get("scriptName") or entry.get("expressionName") or "")] = entry.get("params", [])

DEFAULT_EASES = ["default", "noease", "easeinsine", "easeoutsine", "easeinoutsine", "easeinelastic", "easeoutelastic",
                 "easeinoutelastic", "easeinback", "easeoutback", "easeinoutback", "easeinbounce", "easeoutbounce",
                 "easeinoutbounce", "easeincubic", "easeoutcubic", "easeinoutcubic", "easeinquad", "easeoutquad",
                 "easeinoutquad", "easeinquart", "easeoutquart", "easeinoutquart", "easeinquint", "easeoutquint",
                 "easeinoutquint", "easeincirc", "easeoutcirc", "easeinoutcirc", "easeinexpo", "easeoutexpo", "easeinoutexpo"]


def ace_schema(ref: str) -> tuple[str, list[tuple[str, dict]]]:
    """'Behaviors.Tween.Acts.TweenOneProperty' -> ('Tween.TweenOneProperty', [(param id, spec)])."""
    parts = ref.split(".")
    if len(parts) < 4:
        return ref, []
    kind, addon, group, fn = parts[:4]
    table = {"Cnds": "conditions", "Acts": "actions", "Exps": "expressions"}.get(group, "")
    folder = "plugins" if kind == "Plugins" else "behaviors"
    labels: dict = {}
    for sch in (schema_for(addon, folder), COMMON if folder == "plugins" else None):
        for entry in (sch or {}).get(table, []):
            if entry.get("scriptName") == fn or entry.get("expressionName") == fn:
                labels = entry.get("params", {})
                break
        if labels:
            break
    ordered = ALL_ACES.get((addon.lower(), table, fn))
    if ordered is None:
        return f"{addon}.{fn}", list(labels.items())
    specs = []
    for prm in ordered:
        spec = dict(labels.get(prm["id"], {}))
        spec["type"] = prm.get("type", spec.get("type"))
        if prm.get("items"):
            names = labels.get(prm["id"], {}).get("items", {})
            spec["items"] = {k: names.get(k, k) for k in prm["items"]}
        specs.append((prm["id"], spec))
    return f"{addon}.{fn}", specs


def tween_single_properties(game: Path) -> list[str] | None:
    """The Tween behavior's one-property list in this export's runtime; its order changed between releases."""
    for name in ("scripts/c3runtime.js", "scripts/c3main.js"):
        f = game / name
        if not f.exists():
            continue
        src = f.read_text(encoding="utf-8", errors="replace")
        best: list[str] = []
        for m in re.finditer(r"offsetX\W{1,4}offsetY", src):
            run = re.match(r"[\w\s\",]*", src[m.start():]).group(0)
            tokens = re.findall(r"offset\w+", run)
            if len(tokens) > len(best):
                best = tokens
        if len(best) >= 6:
            return best
    return None


def ease_names(game: Path) -> list[str]:
    for name in ("scripts/c3runtime.js", "scripts/c3main.js"):
        f = game / name
        if f.exists():
            src = f.read_text(encoding="utf-8", errors="replace")
            i = src.find("_CreateEaseMap(){")
            if i >= 0:
                names = re.findall(r'_AddPredifinedEase\("([a-z]+)"', src[i:i + 30000])
                if names:
                    return names
    return DEFAULT_EASES


# ---------------------------------------------------------------- decoding

class Game:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        data = folder / "data.json" if (folder / "data.json").exists() else folder / "data.js"
        self.p = json.loads(data.read_text(encoding="utf-8-sig"))["project"]
        self.refs, self.funcs = runtime_tables(folder)
        self.eases = ease_names(folder)
        self.tween_single = tween_single_properties(folder)
        p = self.p
        self.objs = p[3]
        self.objname = {i: o[0] for i, o in enumerate(self.objs)}
        self.ivars = {}
        for i, o in enumerate(self.objs):
            names = []
            for iv in o[3] if isinstance(o[3], list) else []:
                s = next((x for x in iv if isinstance(x, str)), None) if isinstance(iv, list) else None
                names.append(s or str(iv))
            self.ivars[i] = names
        self.behname = {}
        for i, o in enumerate(self.objs):
            behs = o[8] if len(o) > 8 and isinstance(o[8], list) else []
            self.behname[i] = [b[0] for b in behs if isinstance(b, list) and b and isinstance(b[0], str)]
        self.varname: dict[int, str] = {}
        for sheet in p[6]:
            self._collect_vars(sheet[1])
        self.aces: list[dict] = []

    # names
    def ref(self, i: Any) -> str:
        if self.refs and isinstance(i, int) and 0 <= i < len(self.refs):
            return self.refs[i]
        return f"ace#{i}"

    def _collect_vars(self, node: Any) -> None:
        """Global, local and function-parameter variables: [1, name, type, initial, ..., sid, ...]."""
        if not isinstance(node, list):
            return
        if len(node) > 2 and node[0] == 1 and isinstance(node[1], str):
            sid = next((x for x in node[2:] if isinstance(x, int) and not isinstance(x, bool) and x > 10**9), None)
            if sid:
                self.varname[sid] = node[1]
                return
        for sub in node:
            if isinstance(sub, list):
                self._collect_vars(sub)

    # expressions
    def node_desc(self, node: Any) -> str:
        if not isinstance(node, list) or not node:
            return str(node)
        t = node[0]
        on = lambda i: self.objname.get(i, f"obj{i}")
        tail = lambda r: self.ref(r).split(".")[-1]
        try:
            if t == 0:
                return f"{on(node[1])}.{node[2]}.{tail(node[3])}"
            if t == 1:
                return f"{on(node[1])}.{tail(node[2])}"
            if t == 2:
                names = self.ivars.get(node[1], [])
                vi = node[3] if len(node) > 3 else node[2]
                return f"{on(node[1])}.{names[vi] if isinstance(vi, int) and vi < len(names) else f'ivar{vi}'}"
            if t == 3:
                return self.varname.get(node[1], f"var#{node[1]}")
            if t == 4:
                return tail(node[1])
            if t == 5:
                return f"Functions.{node[1]}"
        except (IndexError, TypeError):
            pass
        return f"node{node}"

    def expr(self, data: Any) -> str:
        if not isinstance(data, list) or not data:
            return json.dumps(data)
        num, nodes = data[0], data[1:]
        if not self.funcs:
            # Construct 2 keeps expressions as trees; literal nodes are [0 int | 1 float | 2 string, value].
            if len(data) == 2 and num in (0, 1, 2) and not isinstance(data[1], list):
                return json.dumps(data[1], ensure_ascii=False)
            return "EXPR" + json.dumps(data, ensure_ascii=False)[:80]
        if not isinstance(num, int) or num >= len(self.funcs):
            return f"EXP#{num}"
        src = self.funcs[num].strip()
        m = re.fullmatch(r"\(\)\s*=>\s*(.*)", src, re.S)
        if m and "_GetNode" not in src:
            return m.group(1)
        decl = {}
        for dm in re.finditer(r"(\w+)\s*=\s*\w+\.(?:_GetNode|\w+)\((\d+)\)((?:\.\w+\(\))?)", src):
            v, idx = dm.group(1), int(dm.group(2))
            decl[v] = nodes[idx] if idx < len(nodes) else ["?"]
        bm = re.search(r"return\s*\(\)\s*=>\s*(.*)\}\s*$", src, re.S)
        body = bm.group(1) if bm else src
        for v, nd in sorted(decl.items(), key=lambda kv: -len(kv[0])):
            d = self.node_desc(nd)
            body = re.sub(r"\b" + re.escape(v) + r"\.\w+\(\)", d, body)
            body = re.sub(r"\b" + re.escape(v) + r"\.\w+\(", d + "(", body)
            body = re.sub(r"\b" + re.escape(v) + r"\(", d + "(", body)
            body = re.sub(r"\b" + re.escape(v) + r"\b", d, body)
        return body.strip()

    def param(self, prm: Any, spec: tuple[str, dict] | None, obj: int | None = None) -> str:
        name = spec[0] if spec else None
        info = spec[1] if spec else {}
        if not isinstance(prm, list) or not prm:
            val = json.dumps(prm)
        else:
            t = prm[0]
            v = prm[1] if len(prm) > 1 else None
            if t == 10 and isinstance(v, int) and obj is not None:
                names = self.ivars.get(obj, [])
                val = names[v] if v < len(names) else f"ivar#{v}"
            elif isinstance(v, list) and v and isinstance(v[0], int) and t != 13:
                val = self.expr(v)
            elif info.get("type") == "ease" and isinstance(v, int):
                val = self.eases[v] if 0 <= v < len(self.eases) else f"custom-ease#{v}"
            elif info.get("items") and isinstance(v, int):
                keys = list(info["items"].values())
                val = keys[v] if v < len(keys) else f"combo{v}"
            elif t == 4 and isinstance(v, int):
                val = self.objname.get(v, f"obj{v}")
            elif t == 13:
                val = "(" + ", ".join(self.param(x, None) for x in prm[1:]) + ")"
            elif t == 11 and isinstance(v, int):
                val = self.varname.get(v, f"var#{v}")
            else:
                val = json.dumps(v, ensure_ascii=False)
        return f"{name}={val}" if name else val

    def ace(self, entry: list, kind: str, sheet: str, group: str | None) -> str:
        o, r = entry[0], entry[1]
        params = next((x for x in reversed(entry) if isinstance(x, list) and (not x or isinstance(x[0], list))), [])
        ref = self.ref(r)
        label, specs = ace_schema(ref) if self.refs else (ref, [])
        if self.tween_single and label.startswith("Tween.") and label.endswith("OneProperty"):
            fixed = []
            for pid, spec in specs:
                if pid == "property" and spec.get("items"):
                    names = spec["items"]
                    spec = dict(spec, items={k: names.get(k, k) for k in self.tween_single})
                fixed.append((pid, spec))
            specs = fixed
        rendered = [self.param(prm, specs[i] if i < len(specs) else None, o if isinstance(o, int) and o >= 0 else None)
                    for i, prm in enumerate(params)]
        if o == -1:
            who = "System"
        elif o == -2:
            who = "Function"
        else:
            who = self.objname.get(o, f"obj{o}")
        inverted = kind == "cond" and len(entry) > 5 and entry[5] is True
        head = f"{'NOT ' if inverted else ''}{who}: {label}"
        self.aces.append({"sheet": sheet, "group": group, "kind": kind, "object": who, "ace": ref,
                          "params": rendered})
        return f"{head}({', '.join(rendered)})"

    def walk(self, items: list, depth: int, sheet: str, group: str | None, out: list[str]) -> None:
        ind = "  " * depth
        for it in items:
            if not isinstance(it, list) or not it:
                continue
            t = it[0]
            if t == 1 and isinstance(it[1], str):
                out.append(f"{ind}VAR {it[1]} = {json.dumps(it[3], ensure_ascii=False) if len(it) > 3 else ''}")
                continue
            if t == 2 and isinstance(it[1], str):
                out.append(f"{ind}INCLUDE {it[1]}")
                continue
            if isinstance(it[1], list) and len(it[1]) >= 2 and isinstance(it[1][1], str) and isinstance(it[1][0], bool):
                name = it[1][1]
                out.append(f"{ind}GROUP \"{name}\"{'' if it[1][0] else ' (inactive)'}")
                subs = next((x for x in it[6:] if isinstance(x, list) and x and isinstance(x[0], list) and isinstance(x[0][0], int) and len(x[0]) > 3), [])
                conds, acts = (it[6] if len(it) > 6 else []), (it[7] if len(it) > 7 else [])
                self._event_body(conds, acts, depth + 1, sheet, name, out, show_always=False)
                self.walk(it[8] if len(it) > 8 else subs, depth + 1, sheet, name, out)
                continue
            if isinstance(it[1], list) and it[1] and isinstance(it[1][0], str):
                fn = it[1]
                out.append(f"{ind}FUNCTION {fn[0]}")
                self._event_body(it[6] if len(it) > 6 else [], it[7] if len(it) > 7 else [], depth + 1, sheet, group, out, show_always=False)
                self.walk(it[8] if len(it) > 8 else [], depth + 1, sheet, group, out)
                continue
            if t in (0, 3, 4):
                conds = it[6] if len(it) > 6 and isinstance(it[6], list) else []
                acts = it[7] if len(it) > 7 and isinstance(it[7], list) else []
                orb = " [OR]" if len(it) > 2 and it[2] is True else ""
                heads = [self.ace(c, "cond", sheet, group) for c in conds if isinstance(c, list) and len(c) > 1]
                out.append(f"{ind}EVENT{orb}: " + (" & ".join(heads) if heads else "(always)"))
                for a in acts:
                    if isinstance(a, list) and len(a) > 1:
                        out.append(f"{ind}    -> {self.ace(a, 'act', sheet, group)}")
                self.walk(it[8] if len(it) > 8 and isinstance(it[8], list) else [], depth + 1, sheet, group, out)
                continue
            out.append(f"{ind}? {json.dumps(it)[:160]}")

    def _event_body(self, conds: list, acts: list, depth: int, sheet: str, group: str | None, out: list[str],
                    show_always: bool = True) -> None:
        ind = "  " * depth
        heads = [self.ace(c, "cond", sheet, group) for c in conds if isinstance(c, list) and len(c) > 1]
        if heads or show_always:
            out.append(f"{ind}EVENT: " + (" & ".join(heads) if heads else "(always)"))
        for a in acts:
            if isinstance(a, list) and len(a) > 1:
                out.append(f"{ind}    -> {self.ace(a, 'act', sheet, group)}")

    # summary
    def summary(self) -> dict:
        p = self.p
        plugin_ref = lambda i: self.ref(i).split(".")[1] if self.refs and isinstance(i, int) else f"plugin{i}"
        objs = []
        for i, o in enumerate(self.objs):
            anims = []
            for a in o[7] if len(o) > 7 and isinstance(o[7], list) else []:
                if isinstance(a, list) and a and isinstance(a[0], str):
                    frames = a[7] if len(a) > 7 and isinstance(a[7], list) else []
                    size = [frames[0][4], frames[0][5]] if frames and len(frames[0]) > 5 else None
                    durs = sorted({f[7] for f in frames if isinstance(f, list) and len(f) > 7 and isinstance(f[7], (int, float))})
                    anims.append({"name": a[0], "speed": a[1], "loop": a[2], "pingpong": a[5] if len(a) > 5 else None,
                                  "frames": len(frames), "size": size, "frame_durations": durs})
            behs = []
            for b in o[8] if len(o) > 8 and isinstance(o[8], list) else []:
                if isinstance(b, list) and b and isinstance(b[0], str):
                    behs.append({"name": b[0], "type": plugin_ref(b[1]) if self.refs else b[1]})
            effects = []
            for e in o[12] if len(o) > 12 and isinstance(o[12], list) else []:
                if isinstance(e, list) and e and isinstance(e[0], str):
                    effects.append(e[0] if len(e) < 2 else f"{e[0]}:{e[1]}")
            image = o[6][0] if len(o) > 6 and isinstance(o[6], list) and o[6] and isinstance(o[6][0], str) else None
            objs.append({"name": o[0], "plugin": plugin_ref(o[1]), "family": o[2], "ivars": self.ivars[i],
                         "behaviors": behs, "animations": anims, "effects": effects, "image": image})
        layouts = []
        tints: dict[str, int] = {}
        beh_props: dict[str, list] = {}
        for L in p[5]:
            layers = []
            counts: dict[str, int] = {}
            for ly in L[9] if len(L) > 9 else []:
                if not isinstance(ly, list) or not ly:
                    continue
                insts = ly[14] if len(ly) > 14 and isinstance(ly[14], list) else []
                for inst in insts:
                    if not isinstance(inst, list) or len(inst) < 2:
                        continue
                    name = self.objname.get(inst[1], str(inst[1]))
                    counts[name] = counts.get(name, 0) + 1
                    world = inst[0] if isinstance(inst[0], list) else []
                    col = next((x for x in world if isinstance(x, list) and len(x) == 4 and all(isinstance(c, (int, float)) for c in x)), None)
                    if col and col != [1, 1, 1, 1]:
                        hexc = "#" + "".join(f"{round(max(0, min(1, c)) * 255):02x}" for c in col[:3])
                        tints[hexc] = tints.get(hexc, 0) + 1
                    if len(inst) > 4 and isinstance(inst[4], list) and inst[4]:
                        for bi, bp in enumerate(inst[4]):
                            bn = self.behname.get(inst[1], [])
                            key = f"{name}.{bn[bi] if bi < len(bn) else bi}"
                            if key not in beh_props:
                                beh_props[key] = bp
                effects = [e[0] if isinstance(e, list) and e else e for e in (ly[15] if len(ly) > 15 and isinstance(ly[15], list) else [])]
                layers.append({"name": ly[0], "bg": ly[4] if len(ly) > 4 else None, "transparent": ly[5] if len(ly) > 5 else None,
                               "parallax": [ly[6], ly[7]] if len(ly) > 7 else None, "opacity": ly[8] if len(ly) > 8 else None,
                               "instances": len(insts), "effects": effects})
            layouts.append({"name": L[0], "size": [L[1], L[2]], "sheet": L[7] if len(L) > 7 else None,
                            "layers": layers, "top_objects": sorted(counts.items(), key=lambda kv: -kv[1])[:12]})
        return {
            "name": p[0], "first_layout": p[1], "viewport": [p[10], p[11]] if len(p) > 11 else None,
            "sampling": p[14] if len(p) > 14 else None, "runtime_tables": bool(self.refs),
            "objects": objs, "families": [[self.objname.get(i, i) for i in f] for f in p[4]],
            "layouts": layouts, "instance_tints": sorted(tints.items(), key=lambda kv: -kv[1])[:40],
            "behavior_instance_props": beh_props,
            "sheets": [s[0] for s in p[6]], "sounds": [s[0] for s in p[7]] if len(p) > 7 and isinstance(p[7], list) else [],
            "timelines": p[33] if len(p) > 33 and isinstance(p[33], list) else [],
        }


def decode(folder: Path) -> str:
    g = Game(folder)
    out = DECODED / folder.name
    sheets = out / "sheets"
    sheets.mkdir(parents=True, exist_ok=True)
    total = 0
    for sheet in g.p[6]:
        lines = [f"===== SHEET {sheet[0]} ====="]
        g.walk(sheet[1], 0, sheet[0], None, lines)
        name = re.sub(r"[^\w]+", "_", sheet[0]).strip("_") or "sheet"
        (sheets / f"{name}.txt").write_text("\n".join(lines), encoding="utf-8")
        total += len(lines)
    s = g.summary()
    (out / "summary.json").write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")
    with (out / "aces.jsonl").open("w", encoding="utf-8") as fh:
        for a in g.aces:
            fh.write(json.dumps(a, ensure_ascii=False) + "\n")
    md = [f"# {s['name']}", "", f"viewport {s['viewport']}, sampling {s['sampling']}, readable ACE names: {s['runtime_tables']}",
          f"{len(s['objects'])} object types, {len(s['layouts'])} layouts, {len(s['sheets'])} sheets, {total} event lines", "",
          "## Objects", ""]
    for o in s["objects"]:
        if o["family"]:
            continue
        bits = [o["plugin"]]
        if o["behaviors"]:
            bits.append("behaviors " + ", ".join(b["name"] for b in o["behaviors"]))
        if o["animations"]:
            bits.append("anims " + "; ".join(f"{a['name']} {a['frames']}f @{a['speed']}{' loop' if a['loop'] else ''}" for a in o["animations"][:6]))
        if o["effects"]:
            bits.append("effects " + ", ".join(o["effects"]))
        md.append(f"- {o['name']}: " + " | ".join(bits))
    md += ["", "## Layouts", ""]
    for L in s["layouts"]:
        layers = "; ".join(f"{ly['name']} bg{ly['bg']}{'' if ly['transparent'] else ' opaque'} px{ly['parallax']}" for ly in L["layers"])
        md.append(f"- {L['name']} {L['size']} sheet={L['sheet']}: {layers}")
    md += ["", "## Instance tints", "", ", ".join(f"{c}×{n}" for c, n in s["instance_tints"])]
    (out / "summary.md").write_text("\n".join(md), encoding="utf-8")
    return f"{folder.name}: tables={s['runtime_tables']} objects={len(s['objects'])} layouts={len(s['layouts'])} sheets={len(s['sheets'])} lines={total} aces={len(g.aces)}"


def main() -> None:
    for arg in sys.argv[1:]:
        folder = Path(arg)
        if not (folder / "data.json").exists() and not (folder / "data.js").exists():
            print(f"{folder.name}: no data.json or data.js")
            continue
        try:
            print(decode(folder))
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            print(f"{folder.name}: FAILED {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()

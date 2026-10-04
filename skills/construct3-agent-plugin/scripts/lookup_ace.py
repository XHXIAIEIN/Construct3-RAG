"""Look up conditions, actions and expressions, with the JSON to write.

    python scripts/lookup_ace.py OBJECT [WORD ...] [--limit CHARS] [--project FOLDER] [--rag FOLDER]
                                 [--locale en-US]

OBJECT is an object type or family of the project, which searches its plugin,
the ACEs every world object shares and its behaviors under the names they
have on the object; `System`; or a plugin or behavior by id or display name
("8 Direction"), which needs no project. Every WORD must occur in the id, the
list name or the script name, or name where the ACE lives: the behavior, the
addon, its category (`time`, `loops`, `size-position`), `condition`, `action`
or `expression`. A word is matched as written, not by meaning: `every`,
`seconds` or the category `time` finds *Every X seconds*, `timer` does not.
When no name has every word, a parameter name or a value of a combo parameter
counts: `Tween color` finds *Tween (one property)*, whose property
`offsetColor` is Color. Looked up on a plugin or a behavior, the ACEs every
world object shares are printed too, *Set color* and *Is overlapping* among
them; they are in `plugins/_common.json`, not in the plugin's own file. Of
those, a plugin gets only the ones its schema lists under `commonAces`: Text
has no *Set color*, the editor refuses it there, and its colour is *Set font
color*.

OBJECT may also be an effect by id or display name (`Bulge`, `Glow
horizontal`): that prints the effect and its parameters, those with every
WORD when words are given. Effects have parameters, no ACEs.

What the editor has deprecated is named so, from
`Construct3-RAG/data/c3-schemas/{locale}/_deprecated.json`: a deprecated
plugin, behavior or effect given as OBJECT (`NW.js`) prints that it is one; a
deprecated ACE the schema kept prints after the current ones, marked
<deprecated>, with the current ACE of the same name when there is one; a
deprecated ACE the schema left out is listed when it has every word, so that
an id from an old project does not read as a typo.

The schema files run to thousands of lines, more than most tools read at
once, and an ACE below the cut looks as if it did not exist; this prints the
part that was asked for. Six matches or fewer print in full, each parameter
with what it is and the way it is written; more print one line each, and more than fit
--limit print as counts per category. When no entry has every word, the
entries that have some of them are listed.
"""
import json
import sys

import c3project as c3
from c3project import LOWER, closest, squash

KINDS = ("conditions", "actions", "expressions")
PARAM_LINE = 150    # a longer parameter line puts the way to write the value on a line of its own

# How each parameter type is written in an event sheet file, and a value that loads.
WRITING = {
    "number": ('"0"', "expression string, in the unit its description names: \"100\""),
    "string": ('"\\"\\""', "expression string, text in inner quotes: \"\\\"hello\\\"\""),
    "any": ('"0"', "expression string, a number or a text in inner quotes"),
    "boolean": ("false", "JSON true or false"),
    "cmp": ("0", "JSON number: 0 =, 1 ≠, 2 <, 3 ≤, 4 >, 5 ≥"),
    "object": ('"<object>"', "bare name of an object type or family"),
    "layer": ('"0"', "expression string: an index \"0\" or a name in inner quotes \"\\\"HUD\\\"\""),
    "layout": ('"<layout>"', "bare layout name"),
    "keyb": ("32", "key code as a JSON number: 32 Space, 13 Enter, 37-40 arrows, 65-90 A-Z"),
    "instancevar": ('"<variable>"', "bare name of an instance variable of the object"),
    "instancevarbool": ('"<variable>"', "bare name of a boolean instance variable of the object"),
    "objinstancevar": ('{"name": "<variable>", "objectClass": "<object>"}', "an instance variable of another object"),
    "eventvar": ('"<variable>"', "bare name of a global or local variable in scope"),
    "eventvarbool": ('"<variable>"', "bare name of a boolean variable in scope"),
    "eventvarany": ('"<variable>"', "bare name of a variable in scope"),
    "animation": ('"\\"\\""', "expression string, the animation name in inner quotes"),
    "groupname": ('"\\"\\""', "expression string, the group title in inner quotes"),
    "ease": ('"easeinoutsine"', "bare id of a built-in ease: noease, easeinoutsine, easeoutback ..."),
    "projectfile": ('"<file>"', "bare file name under files/"),
    "timeline": ('"<timeline>"', "bare timeline name"),
    "flowchart": ('"<flowchart>"', "bare flowchart name"),
    "template": ('"\\"\\""', "expression string, the template name in inner quotes, \"\\\"\\\"\" for none"),
    "audiofile": ('"<sound>"', "bare name of a sound or music file of the project, without its extension"),
    "function": ('"<function>"', "bare name of a function of the project"),
    "tilemapbrush": ('{"objectClassName": "<tilemap>", "brushName": "<brush>"}', "a brush of a Tilemap object"),
    "objecteffect": ('"\\"\\""', "expression string, the effect's name in inner quotes: \"\\\"AdjustHSL\\\"\""),
    "layereffect": ('"\\"\\""', "expression string, the effect's name in inner quotes: \"\\\"AdjustHSL\\\"\""),
    "layouteffect": ('"\\"\\""', "expression string, the effect's name in inner quotes: \"\\\"AdjustHSL\\\"\""),
    "objectinsttags": ('"\\"\\""', "expression string, the tags in inner quotes"),
    "objectname": ('"\\"\\""', "expression string, the object type's name as text: \"\\\"Enemy\\\"\""),
    "model3d-animation-string": ('"\\"\\""', "expression string, the animation name in inner quotes"),
}
# A parameter's initialValue in the schema is the editor's default: expression text, or a
# JSON number for a few such as Set opacity's 100, and "true" or "false" for a boolean. A
# project file writes every expression as text, "opacity": "100", and the checker refuses a
# number there. These types write it; a layer's default "" names no layer.
EDITOR_DEFAULT = {
    "boolean": lambda v: "true" if str(v).lower() == "true" else "false",
    "number": lambda v: json.dumps(str(v)),
    "string": lambda v: json.dumps(str(v)),
    "any": lambda v: json.dumps(str(v)),
}


def sources_of(p: c3.Project, target: str) -> list[tuple[str, str | None, dict]]:
    """(objectClass to write, behaviorType, schema). Of a project object: its
    plugin, the shared world-object ACEs and its behaviors under the names they
    have on the object. Of anything else: the plugin or behavior with that id
    or display name, spelled as it is apart from case, spaces and punctuation.
    A near name is not taken for it: `Platform` would read as Platform Info."""
    obj = p.objects_lower.get(LOWER(target))
    if obj == "System" or LOWER(target) == "system":
        return [("System", None, p.system)]
    if obj and LOWER(obj) == LOWER(p.functions_object):
        # The built-in Functions object has the System schema's Set return value and function maps, nothing else.
        own = {**p.system, **{kind: [it for it in p.system.get(kind, []) if c3.is_functions_ace(it)] for kind in KINDS}}
        return [(p.functions_object, None, own)]
    if obj:
        own = p.schema("plugins", p.plugin_of[obj]) or {}
        sources = [(obj, None, own)]
        if "singleglobal-inst" not in p.types.get(obj, {}):     # Keyboard, Touch, Audio: nothing of a world object
            sources.append((obj, None, p.common_of(own)))
        return sources + [(obj, name, p.schema("behaviors", b) or {}) for name, b in p.behaviors_of(obj).items()]
    sources = []
    for kind in ("plugins", "behaviors"):
        addon = p.addon_names(kind).get(squash(target))
        if addon and addon != "_common":
            behavior = "<behavior name on the object>" if kind == "behaviors" else None
            sources.append(("<object>", behavior, p.schema(kind, addon) or {}))
    if not sources:
        retired = p.deprecated_addon_named(target)
        if retired:
            # An answer, not a failure to run: on stdout, like a miss.
            kind, addon_id, entry = retired
            print(f"{entry.get('originalId', addon_id)} ({entry.get('name', addon_id)}) is a deprecated "
                  f"{kind[:-1]}: {c3.DEPRECATED}. The clone has no schema for it; do not add it to a project")
            sys.exit(1)
        names = [v.get("name", k) for kind in ("plugins", "behaviors", "effects")
                 for k, v in c3.load(p.schemas / "_index.json").get(kind, {}).items()]
        sys.exit(f"{target!r} is not an object of this project, System, or the id or display name of a plugin, "
                 f"behavior or effect" + closest(target, [*p.plugin_of, *names, *p.index["plugins"],
                                                           *p.index["behaviors"], *p.index["effects"]]))
    return sources


def shared_matches(p: c3.Project, words: list[str], plugins: list[dict]) -> list[tuple[str, dict]]:
    """The ACEs of plugins/_common.json that have every word in their names and
    that one of `plugins` gets; any of them when `plugins` is empty (a behavior)."""
    out = []
    shared = [p.common_of(s) for s in plugins] or [p.common]
    for kind in KINDS:
        allowed = {it["id"] for s in shared for it in s.get(kind, [])}
        for it in p.common.get(kind, []):
            if it["id"] not in allowed:
                continue
            names = squash(" ".join([*(str(it.get(k, "")) for k in ("id", "list-name", "translated-name", "scriptName")),
                                     kind, it.get("category", "")]))
            if all(squash(w) in names for w in words):
                out.append((kind, it))
    return out


def brief(owner: str, behavior: str | None, addon: str, kind: str, it: dict) -> str:
    title = it.get("list-name") or it.get("translated-name")
    via = f" [behavior {behavior}, {addon}]" if behavior else f" [{addon}]"
    params = it.get("params") or {}
    return (f"{kind[:-1]:<10} {it['id']:<34} {title}{via}" + (f"  ({', '.join(params)})" if params else "")
            + ("  <deprecated>" if it.get("isDeprecated") else ""))


def in_full(owner: str, behavior: str | None, addon: str, kind: str, it: dict, written: str | None = None) -> list[str]:
    """written: the name an expression has in a project file, English in every locale."""
    title = it.get("list-name") or it.get("translated-name")
    flags = [f for f in ("isTrigger", "isLooping", "isAsync") if it.get(f)] + \
            (["not invertible"] if it.get("isInvertible") is False else []) + \
            (["deprecated"] if it.get("isDeprecated") else [])
    via = f" [behavior {behavior}, {addon}]" if behavior else f" [{addon}]"
    params = it.get("params") or {}
    lines = [f"{kind[:-1]} {it['id']} - {title}{via}" + (f"  <{', '.join(flags)}>" if flags else ""),
             f"  {it.get('description', '')}"]
    if it.get("isDeprecated"):
        lines.append(f"  deprecated: {c3.DEPRECATED}"
                     + (f"; the current {kind[:-1]} of the same name is {it['current']}" if it.get("current") else ""))
    if kind == "expressions":
        call = f"({', '.join(params)}{', ...' if it.get('isVariadicParameters') else ''})" if params else ""
        path = f"{owner}.{behavior}." if behavior else ("" if owner == "System" else f"{owner}.")
        lines.append(f"  write: {path}{written or it['translated-name']}{call}  -> {it.get('returnType', 'any')}")
    else:
        values = {}
        for key, spec in params.items():
            items = spec.get("items")
            if items:
                first = spec.get("initialValue") if spec.get("initialValue") in items else next(iter(items))
                values[key] = json.dumps(first)
            elif spec.get("initialValue") is not None and spec["type"] in EDITOR_DEFAULT:
                # What the editor fills in, so a copied template behaves like an ACE added
                # there: Wait follows the time scale, "use-timescale": true.
                values[key] = EDITOR_DEFAULT[spec["type"]](spec["initialValue"])
            else:
                values[key] = WRITING.get(spec["type"], ('"0"', ""))[0]
        head = f'{{"id": "{it["id"]}", "objectClass": "{owner}"' \
               + (f', "behaviorType": "{behavior}"' if behavior else "") + ', "sid": <new sid>'
        body = ", ".join(f'"{k}": {v}' for k, v in values.items())
        lines.append("  write: " + head + (f', "parameters": {{{body}}}}}' if params else "}"))
    for key, spec in params.items():
        # A combo item is written by its id and shown in the editor by its name, which a model named
        # from the id when only the id was printed ("上方" for top, whose zh-CN name is "顶部").
        how = " | ".join(k if squash(k) == squash(v) else f"{k}: {v}" for k, v in spec["items"].items()) \
            if spec.get("items") else WRITING.get(spec["type"], ("", "expression string"))[1]
        if spec.get("type") == "boolean" and spec.get("initialValue") is not None:
            how += "; the editor ticks it by default" if EDITOR_DEFAULT["boolean"](spec["initialValue"]) == "true" \
                else "; the editor leaves it unticked by default"
        # What the parameter is, from the schema: find(text, find) searches `text` for `find`,
        # which the type alone does not say, and a model wrote it the other way round.
        desc = " ".join(str(spec.get("desc") or "").split())
        line = f"    {key:<22} {spec['type']:<10} "
        if not desc:
            lines.append(line + how)
        elif len(line) + len(desc) + len(how) + 4 <= PARAM_LINE:
            lines.append(f"{line}{desc}  ({how})")
        else:
            lines += [line + desc, " " * len(line) + f"({how})"]
    return lines


def print_in_full(blocks: list[list[str]], ids: list[str], limit: int) -> None:
    """Prints the entries in full while they fit --limit and names the rest: six entries
    of Audio, each parameter described, run past 10 000 characters."""
    # The note on the rest takes a few hundred characters of the limit.
    room = c3.fitting([line for block in blocks for line in block], max(limit - 400, 1) if limit else 0)
    for n, block in enumerate(blocks):
        if len(block) > room and n:
            print(f"{len(blocks) - n} more did not fit {limit} characters (--limit): {', '.join(ids[n:])}; "
                  f"add a word to narrow them or raise --limit")
            return
        print("\n".join(block))
        room -= len(block)


def effects_of(p: c3.Project, target: str) -> list[str]:
    """The ids of the effects `target` names, when it names no object, System, plugin or behavior.
    One name can be two effects: the zh-CN pack calls both Brightness and Lighten 亮度."""
    if LOWER(target) == "system" or p.objects_lower.get(LOWER(target)):
        return []
    if any(p.addon_names(kind).get(squash(target)) for kind in ("plugins", "behaviors")):
        return []
    ids = []
    for locale in dict.fromkeys((p.locale, "en-US")):
        names = c3.load(p.rag / "data" / "c3-schemas" / locale / "_index.json").get("effects", {})
        ids += [k for k, v in names.items() if squash(target) in (squash(k), squash(v.get("name", "")))]
    return list(dict.fromkeys(ids))


def effect_lookup(p: c3.Project, effect_id: str, words: list[str]) -> int:
    effect = p.schema("effects", effect_id) or {}
    params = effect.get("parameters", [])
    print(f"effect {effect_id} - {effect.get('name', effect_id)} [{effect.get('category', '')}]")
    print(f"  {effect.get('description', '')}")
    if not params:
        print("  no parameters")
        return 0
    chosen = [q for q in params
              if all(squash(w) in squash(q.get("id", "") + q.get("name", "")) for w in words)]
    missed = not chosen
    if missed:
        print(f"no parameter of {effect_id} has every word of {' '.join(words)!r}; its parameters:")
        chosen = params
    for q in chosen:
        print(f"    {q.get('id', ''):<22} {q.get('type', ''):<10} {q.get('name', '')}: {q.get('desc', '')}")
    return 1 if missed else 0


def retired_note(p: c3.Project, sources: list[tuple[str, str | None, dict]], words: list[str]) -> list[str]:
    """The deprecated ACEs of these addons that the schema left out and that have
    every word, for a project that still uses one. None without words."""
    hits = []
    for _, behavior, s in sources if words else []:
        if not s:
            continue
        kept = {(kind, it["id"]) for kind in KINDS for it in s.get(kind, [])}
        for kind in KINDS:
            for ace_id, entry in p.deprecated_aces(f"{s.get('type')}s", s.get("id", ""), kind).items():
                title = entry.get("list-name") or entry.get("translated-name") or ace_id
                names = squash(" ".join([ace_id, title, behavior or "", s.get("id", ""), s.get("name", ""), kind]))
                if (kind, ace_id) not in kept and all(squash(w) in names for w in words):
                    hits.append(f"  {kind[:-1]:<10} {ace_id:<34} {title} [{s.get('id', '')}]"
                                + (f"  current of the same name: {entry['current']}" if entry.get("current") else ""))
    hits = list(dict.fromkeys(hits))
    if not hits:
        return []
    return ["deprecated, and not in the schema: Construct 3 no longer offers these and keeps them only so that "
            "old projects open", *hits[:6]] + ([f"  ... and {len(hits) - 6} more"] if len(hits) > 6 else [])


def addon_word_lines(p: c3.Project, sources: list[tuple[str, str | None, dict]], target: str,
                     words: list[str]) -> list[str]:
    """A word that names a behavior or plugin `target` does not have: `System timer` looks for
    the Timer behavior under System, which has none of its ACEs. The way to them, for the
    first line of a miss, which is all a small model reads of it."""
    have = {squash(s.get("id", "")) for _, _, s in sources}
    lines = []
    # A quoted argument holds several: `System "start timer"`.
    for word in dict.fromkeys(w for arg in words for w in [arg, *arg.split()]):
        for kind in ("behaviors", "plugins"):
            addon = p.addon_names(kind).get(squash(word))
            if not addon or squash(addon) in have or addon == "_common":
                continue
            name = (p.schema(kind, addon) or {}).get("name", addon)
            arg = f'"{name}"' if " " in name else name
            rest = " ".join(w for w in " ".join(words).split() if squash(w) != squash(word))
            if kind == "behaviors":
                owners = [o for o in p.plugin_of if squash(addon) in map(squash, p.behaviors_of(o).values())]
                if owners:
                    lines.append(f"{name} is a behavior, not part of {target}; {', '.join(owners[:4])} "
                                 f"{'has' if len(owners) == 1 else 'have'} it: lookup_ace.py {owners[0]} {' '.join(words)}")
                else:
                    lines.append(f"{name} is a behavior, not part of {target}, and no object of the project has it: "
                                 f"lookup_ace.py {arg} {rest}".rstrip() + f" lists its ACEs; add it to the "
                                 f"behaviorTypes of the object that uses them first")
            else:
                owners = [o for o, plugin in p.plugin_of.items() if squash(plugin) == squash(addon)]
                lines.append(f"{name} is a plugin, not part of {target}: lookup_ace.py "
                             f"{owners[0] if owners else arg} {rest}".rstrip()
                             + (f", a {name} object of the project" if owners and owners[0] != name else ""))
            break
    return list(dict.fromkeys(lines))


def ace_lookup(p: c3.Project, target: str, words: list[str], limit: int) -> int:
    sources = sources_of(p, target)
    if LOWER(target) == LOWER(p.functions_object):
        # A model that has not met it writes an object type and a usedAddons entry, and the editor
        # reports a missing legacy addon.
        print(f"note: {p.functions_object} is built in: project.c3proj names it in \"functionsName\", with no "
              f"object type file and no usedAddons entry")
    entries = []        # (its names, its names and category, owner, behavior, addon, kind, entry)
    param_text = []     # parameter names and combo values, in step with entries
    written = {}        # (behavior, addon, expression id) -> the name it is written under
    for owner, behavior, s in sources:
        written.update({(behavior, s.get("id", ""), ace): name for ace, name in p.expression_names(s).items()})
        for kind in KINDS:
            for it in s.get(kind, []):
                if it.get("isDeprecated"):
                    current = p.deprecated_aces(f"{s.get('type')}s", s.get("id", ""), kind).get(it["id"], {}).get("current")
                    it = {**it, "current": current} if current else it
                # A word may also name where the ACE lives: the behavior, the addon, "condition".
                names = squash(" ".join([*(str(it.get(k, "")) for k in ("id", "list-name", "translated-name", "scriptName")),
                                         behavior or "", s.get("id", ""), s.get("name", ""), kind]))
                # Set return value and the function maps are in the System schema, and a
                # project writes them under the Functions object's name.
                writer = p.functions_object if s.get("id") == "system" and c3.is_functions_ace(it) else owner
                entries.append((names, names + " " + squash(it.get("category", "")), writer, behavior, s.get("id", ""), kind, it))
                params = it.get("params") or {}
                # Tween Color is Tween (one property) with the property offsetColor: the word is a
                # combo value, and a search of the names alone answers that Tween has no color.
                param_text.append(squash(" ".join([*params, *(str(v) for spec in params.values()
                                                              for v in (spec.get("items") or {}).values())])))
    if not entries:
        obj = p.objects_lower.get(LOWER(target))
        retired = p.deprecated_addon("plugins", p.plugin_of[obj]) if obj else None
        if retired:
            print(f"{target} is a {retired.get('originalId')} ({retired.get('name')}) object, a deprecated plugin: "
                  f"{c3.DEPRECATED}. The clone has no schema for it: nothing to look up")
            return 1
        sys.exit(f"the clone has no schema for {target}, a third-party addon: nothing to look up")
    retired_lines = retired_note(p, sources, words)
    # By name first, so that a category which shares a word with a name does not
    # turn six entries printed in full into a list: `Physics force` is the three
    # Apply force actions, and the rest of the category `forces` is named below them.
    named = [all(squash(w) in e[0] for w in words) for e in entries]
    wider = [all(squash(w) in e[1] for w in words) for e in entries]
    found = [e[2:] for e, n in zip(entries, named) if n]
    by_category = [e[2:] for e, n, w in zip(entries, named, wider) if w and not n]
    if not found or len(found) > 6:
        found, by_category = [e[2:] for e, w in zip(entries, wider) if w], []
    found.sort(key=lambda e: bool(e[4].get("isDeprecated")))     # the current ones first

    if not found:
        query = " ".join(words)
        for line in addon_word_lines(p, sources, target, words):
            print(line)
        # A deprecated id of an old project would otherwise read as a typo.
        for line in retired_lines:
            print(line)
        # Pick nearest/furthest, Is overlapping, Set color ... are not System's and not the
        # plugin's: every world object has them, so they are looked up on an object.
        # A plugin with no shared ACEs at all (System, Keyboard) points to the world objects that have them.
        plugins = [s for _, _, s in sources if s.get("type") == "plugin" and s.get("id") != "_common"
                   and any(p.common_of(s).get(kind) for kind in KINDS)]
        shared = [] if any(s.get("id") == "_common" for _, _, s in sources) else shared_matches(p, words, plugins)
        in_params = [e[2:] for e, t in zip(entries, param_text) if all(squash(w) in t for w in words)]
        if shared or in_params:
            # The entry before the miss: a model that stops at the first line read "nothing under
            # Sprite has every word of 'color'" as a Sprite having no color action, and went to
            # the manual, which does not list the shared ACEs either, to confirm it.
            if shared:
                print(f"{target} has these, in plugins/_common.json rather than in its own plugin:" if plugins
                      else "every world object has these, in plugins/_common.json rather than in its own plugin:")
                # <Object>, not the <object> a parameter of that type is written with.
                print_in_full([in_full("<Object>", None, "_common", kind, it) for kind, it in shared],
                              [it["id"] for _, it in shared], limit)
                print(f"<Object> is {'a ' + target + ' object' if plugins else 'any object'} of the project; "
                      f"lookup_ace.py <Object> {query} writes its name in")
            if in_params:
                print(f"no name under {target} has every word of {query!r}; a parameter of these takes it as a value:")
                if len(in_params) <= 6:
                    print_in_full([in_full(*e, written.get((e[1], e[2], e[4]["id"])) if e[3] == "expressions" else None)
                                   for e in in_params], [e[4]["id"] for e in in_params], limit)
                else:
                    for e in in_params[:20]:
                        print("  " + brief(*e))
                    print(f"{len(in_params)} entries; add a word to narrow them, six or fewer print with the JSON to write")
            return 0
        # The most words first, a word in a name before a word in a category.
        some = sorted(((sum(squash(w) in e[0] for w in words), sum(squash(w) in e[1] for w in words), e[2:])
                       for e in entries), key=lambda x: (-x[0], -x[1]))
        some = [e for _, n, e in some if n]
        entries = [e[1:] for e in entries]
        # The miss is the answer, on stdout like a hit: a harness that shows stdout alone
        # would print nothing, and PowerShell wraps every stderr line in an error record.
        print(f"nothing under {target} has every word of {query!r}")
        if some:
            print("entries with some of them, the most first:")
            for e in some[:12]:
                print("  " + brief(*e))
            if len(some) > 12:
                print(f"  ... and {len(some) - 12} more")
        else:
            near = closest(" ".join(words), [e[5]["id"] for e in entries], n=6)
            categories = sorted({e[5].get("category", "") for e in entries} - {""})
            print((near.lstrip("; ") + "\n" if near else "") + f"categories, each a word too: {', '.join(categories)}")
        return 1

    if len(found) <= 6:
        print_in_full([in_full(*e, written.get((e[1], e[2], e[4]["id"])) if e[3] == "expressions" else None)
                       for e in found], [e[4]["id"] for e in found], limit)
        if by_category:
            print(f"by category, not by name: {', '.join(e[4]['id'] for e in by_category[:20])}"
                  + (" ..." if len(by_category) > 20 else ""))
        for line in retired_lines:
            print(line)
        return 0
    lines = [brief(*e) for e in found]
    if c3.fitting(lines, limit) == len(lines):
        print("\n".join(lines))
        print(f"{len(found)} entries; add a word to narrow them, six or fewer print with the JSON to write")
        for line in retired_lines:
            print(line)
        return 0
    print(f"{len(found)} entries, more than fit {limit} characters (--limit). Entries per category:")
    for kind in KINDS:
        counts: dict[str, int] = {}
        for _, behavior, addon, its_kind, it in found:
            if its_kind == kind:
                where = it.get("category") or behavior or addon     # a behavior's own ACEs carry no category
                counts[where] = counts.get(where, 0) + 1
        if counts:
            print(f"  {kind:<12} " + ", ".join(f"{name} {n}" for name, n in counts.items()))
    behaviors = list(dict.fromkeys(b for _, b, _ in sources if b and not b.startswith("<")))
    if behaviors:
        print(f"  behaviors    {', '.join(behaviors)}")
    print("add a word: a category, a behavior, condition, action or expression, or part of a name; "
          "six entries or fewer print with the JSON to write")
    return 0


def main() -> int:
    ap = c3.argument_parser(
        "Look up conditions, actions and expressions of an object of the project, of System, or of a plugin or "
        "behavior by id or display name, and print each with its parameters and the JSON to write. Use it "
        "instead of reading plugins/system.json or plugins/_common.json, which are longer than most tools read.",
        "examples:\n"
        "  python scripts/lookup_ace.py Coin tween two         an object of the project: plugin, shared ACEs, behaviors\n"
        "  python scripts/lookup_ace.py System wait\n"
        "  python scripts/lookup_ace.py System time            a category: Every X seconds, Wait, dt, time ...\n"
        "  python scripts/lookup_ace.py \"8 Direction\" speed    a plugin or behavior by id or display name\n"
        "  python scripts/lookup_ace.py Coin tween condition   a word may be condition, action or expression\n"
        "  python scripts/lookup_ace.py Bulge                  an effect by id or display name: its parameters\n"
        "  python scripts/lookup_ace.py Mouse set-cursor-style an id from an old project: deprecated, and the current one\n\n"
        "exit codes: 0 found, 1 no entry has every word (those with some are listed), OBJECT is unknown (the\n"
        "nearest names are listed) or deprecated, or the clone was not found")
    ap.add_argument("object", metavar="OBJECT",
                    help="an object type or family of the project, System, a plugin or behavior id or display "
                         "name, or an effect id or display name")
    ap.add_argument("words", nargs="*", metavar="WORD",
                    help="every word must occur in the id, the list name or the script name, or name the "
                         "behavior, the addon, the category, or the kind: condition, action, expression")
    args = ap.parse_args()
    c3.utf8_output()
    findings = c3.Findings()
    c3.stop_with_a_sentence("lookup_ace.py", findings)
    project = c3.Project.open(args, findings, needs_project=False)
    drift = c3.skill_drift(project.rag)
    if drift:
        print(f"note: {drift}")
    effects = effects_of(project, args.object)
    if effects:
        return max(effect_lookup(project, effect, args.words) for effect in effects)
    return ace_lookup(project, args.object, args.words, args.limit)


if __name__ == "__main__":
    sys.exit(main())

"""Static checks for a Construct 3 folder project, run without the editor.

    python scripts/check_project.py [--project FOLDER] [--rag FOLDER] [--locale en-US]

Reads project.c3proj and every object type, family, layout and event sheet it
lists, and checks them against the schemas in Construct3-RAG and against the
rules the editor applies when it opens or previews a project. What is
checked, and where each rule comes from: references/checker-rules.md.

It cannot run the events: picking, timing and the meaning of an expression
are the editor's and the preview's to judge.

Findings in event sheets are placed as `sheet Game event 15 action 2`, the
number the editor prints in the margin; print_sheet.py prints that numbering.
Under --limit the findings that fit are printed and the rest counted; the
last line, `ok:` or the number of problems, always prints.

Exit 0: no errors; warnings do not fail the run. Exit 1: findings, or the
project or the clone was not found. Exit 2: a project file lacks a key the
editor always writes, and the run stopped there.
"""
import difflib
import json
import math
import re
import sys
import unicodedata
from pathlib import Path
from typing import NamedTuple

import c3project as c3
from c3project import LOWER, NUMBERED, STRING_LITERAL, closest, describe, folder_items, squash

# Names. The editor passes every name through a filter when it opens the
# project and keeps the result, so a name the filter changes no longer matches
# the events that use it. After the open it also renames an object type or
# family whose name is reserved, Floor to Floor2. It refuses a name already
# taken in the object's namespace, where instance variables, behaviors, effects
# and the plugin's expressions live side by side, compared without case.
NAME_DROPS = set(".。,，\"“”(（)）?？:：\\/;*|'-`!¬£$%^&+=<>{}[]@#~­​")
VARIABLE_TYPES = ("number", "string", "boolean")
# Event keys the editor reads as text and stops on when missing, with its message.
EVENT_TEXT = (("comment", "text", "Cannot read properties of undefined (reading 'endsWith')"),
              ("group", "description", "expected string"),
              ("variable", "comment", "expected string"))
FUNCTION_RETURN_TYPES = ("none", "number", "string", "any")
# rootFileFolders kind -> the folder the editor saves its files in, as Scirra's guide
# "Construct's project format" lists them.
ROOT_FILE_FOLDERS = {"general": "files", "icon": "icons", "sound": "sounds", "music": "music",
                     "video": "videos", "font": "fonts", "script": "scripts"}
# The folders whose files project.c3proj lists by name, one JSON file each. The editor reads only
# what the project lists and ignores any other file there; scripts/ is left out of that check,
# since the editor keeps unlisted TypeScript copies and definitions in it for an external editor.
RESOURCE_FOLDERS = ("objectTypes", "families", "layouts", "eventSheets", "timelines", "flowcharts")
UNLISTED_ROOT_FILES = ("general", "icon", "sound", "music", "video", "font")
# Sound and music are WebM Opus; the editor converts what it imports.
AUDIO_TYPE = "audio/webm; codecs=opus"
# how a layout instance writes the value of an instance variable of each type
JSON_TYPES = {"number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
              "string": lambda v: isinstance(v, str), "boolean": lambda v: isinstance(v, bool)}
JSON_EXAMPLES = {"number": "a number such as 1", "string": "text such as \"a\"", "boolean": "true or false"}
FULL_TURN = 2 * math.pi + 1e-6      # the largest world angle the official examples hold is 2π
# Names the editor reserves for an object besides the system expressions, compared without case.
# "system" is not among them: it is the System object's own name, and an object of that name
# stops the open.
RESERVED_WORDS = {"self", "true", "false"}
DEVICE_NAMES = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}

# project.c3proj. Opening a project reads the whole properties block before it
# reads a single file of the project, and each of these is asserted as it is
# read: a missing one throws "TypeError: expected string" and a wrong one names
# the property. The value sets are the editor's; the defaults are what it
# writes into a new project.
PROJECT_TEXT = {"description": "", "version": "1.0.0.0", "author": "", "authorEmail": "",
                "authorWebsite": "", "appId": ""}
PROJECT_OPTIONS = {"fullscreenMode": ("letterbox-scale", "letterbox-integer-scale", "scale-inner",
                                      "integer-scale-inner", "scale-outer", "integer-scale-outer", "off"),
                   "fullscreenQuality": ("high", "low"),
                   "orientations": ("any", "portrait", "landscape"),
                   "sampling": ("trilinear", "bilinear", "nearest"),
                   "downscaling": ("medium", "low", "high"),
                   "loaderStyle": ("splash", "progress-logo", "progress", "percent", "none")}
PROJECT_ALSO = {"sampling": ("linear", "point")}    # older ids the editor maps as it reads them
# Plugins whose object type carries an animations folder: the editor reads it as
# it opens the type and stops with "TypeError: expected object" when it is not
# there. The 2930 Sprite and 785 Shape3D types of the official examples all have
# one, and no other plugin there does.
ANIMATED_PLUGINS = ("Sprite", "Shape3D")
# Plugins whose object type carries one image instead: without the "image" block the
# editor stops the same way. The 872 TiledBg, 392 Spritefont2, 223 Particles, 153
# Tilemap and 106 NinePatch types of the official examples all have one, and no
# other plugin there does.
IMAGE_PLUGINS = ("TiledBg", "Spritefont2", "Particles", "Tilemap", "NinePatch")
# A layer's blend mode, read as it opens: the editor's own map, "xor" is not in it.
BLEND_MODES = ("normal", "additive", "copy", "destination-over", "source-in", "destination-in",
               "source-out", "destination-out", "source-atop", "destination-atop", "lighten",
               "darken", "multiply", "screen")
# The numbers the editor reads out of a layer and a world instance as it places it.
LAYER_NUMBERS = ("parallaxX", "parallaxY", "scaleRate")
WORLD_NUMBERS = ("x", "y", "width", "height", "originX", "originY")
# Below this release the editor reads an object type from objectTypes\<name in
# lower case>.json, the layout of a project from 2016, and finds nothing.
FOLDER_PROJECT_RELEASE = 30900

# Object and behavior names may start with a digit (3DCamera, 8Direction), so a
# token is any run of word characters and numeric literals are skipped by value.
# Word characters are Unicode ones: the editor takes names in any script, and an
# ASCII class skips them, or cuts a mixed name down to its ASCII part.
# Sprite(2).X picks an instance by IID; the index is checked as an expression.
IDENT = re.compile(r"\w+")
NUMBER = re.compile(r"\d+(\.\d+)?(e[+-]?\d+)?", re.I)
EMPTY_CALL = re.compile(r"\s*\(\s*\)")
MEMBER = re.compile(r"(\w+)(?:\([^()]*\))?\s*\.\s*(\w+)(?:\s*\.\s*(\w+))?")
# C-style operators the expression parser refuses, with the Construct operator for each; the power
# of JavaScript's ** is ^, which in C would be exclusive or. A lone ! has none: the editor calls it
# an unknown character, and the test is written as a comparison.
C_OPERATORS = {"==": "=", "!=": "<>", "&&": "&", "||": "|", "**": "^"}
C_OPERATOR = re.compile(r"==|!=|&&|\|\||\*\*|!")
# What a variable or parameter named like another one, compared without case, can be called instead.
SHADOW_SUFFIX = {"string": "Text", "number": "Value", "boolean": "Flag"}
# Instances created in a top-level event or trigger join the instance lists when it ends: until then only
# Pick by unique ID finds them outside the creating event (prompts/pitfalls/creating-objects.md). The
# actions that create an instance of a named type, with the parameter that names it; spawn-another-object
# is on every world object. Create object by name is left out: its type is an expression.
CREATING = {("System", "create-object"): "object-to-create", ("System", "recreate-initial-objects"): "object"}
# System conditions that pick among the instances of the type in their object parameter.
SYSTEM_PICKS = {"for-each", "for-each-ordered", "pick-nth-instance", "pick-random-instance", "pick-all",
                "pick-by-comparison", "pick-by-evaluate", "pick-by-highest-lowest-value",
                "pick-overlapping-point"}
# Conditions on an object that find a created instance anyway, or pick another object than their own.
NOT_PICKING = {"pick-by-unique-id", "pick-parent", "pick-children", "pick-nth-child", "on-created"}
# After one of these the rest of the actions run later, once the instances have joined.
WAITS = {"wait", "wait-for-signal", "wait-for-previous-actions"}


def editor_name(name: str, is_object: bool) -> str:
    """What the editor keeps of a name: the letter after a space is capitalised,
    spaces and punctuation go, leading underscores go. An object or behavior
    name may start with a digit but not be all digits; an instance variable
    name loses its leading digits too."""
    chars = list(unicodedata.normalize("NFC", name))
    for i in range(len(chars) - 1):
        if chars[i] == " ":
            chars[i + 1] = chars[i + 1].upper()
    chars = [c for c in chars if c not in NAME_DROPS and not c.isspace()]
    if is_object:
        while chars and chars[0] == "_":
            chars.pop(0)
        if all(c.isdigit() for c in chars):
            chars = []
    else:
        while chars and (chars[0].isdigit() or chars[0] == "_"):
            chars.pop(0)
    return "".join(chars)


def next_name(name: str) -> str:
    """The name the editor gives an object whose name it cannot keep: the number at its end plus
    one, or a 2 added when it has none."""
    stem = name.rstrip("0123456789")
    number = name[len(stem):]
    return stem + (str(int(number) + 1) if number else "2")


def free_name(name: str, taken) -> str:
    """The name the editor gives a variable, parameter or function it renames: next_name,
    repeated until no name taken matches it without case (Amount3 when amount2 is taken)."""
    low = {LOWER(t) for t in taken if isinstance(t, str)}
    new = next_name(name)
    while LOWER(new) in low:
        new = next_name(new)
    return new


def variable_kind(var: dict) -> str:
    """What a finding calls a declaration; a function parameter carries no eventType."""
    if "eventType" not in var:
        return "parameter"
    return "constant" if var.get("isConstant") else "static variable" if var.get("isStatic") else "variable"


def case_aside(name: str, other: str) -> str:
    """' once case is ignored' when the two names differ, else ''."""
    return "" if name == other else " once case is ignored"


def params_of(ace: dict) -> dict:
    """An ACE's parameters by id; a function call keeps its arguments in a list, which names none."""
    params = ace.get("parameters")
    return params if isinstance(params, dict) else {}


def is_literal(v) -> bool:
    return isinstance(v, str) and STRING_LITERAL.fullmatch(v) is not None


def unquote(v: str) -> str:
    return v[1:-1].replace('""', '"')


# JavaScript text with its strings and comments blanked, for names in the code itself
JS_SKIPPED = re.compile(r"//[^\n]*|/\*.*?\*/|'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"|`(?:\\.|[^`\\])*`", re.S)
JS_SIGNAL = re.compile(r"runtime\s*\.\s*signal\s*\(\s*(?:(['\"])(.*?)\1\s*\))?")

# Actions the browser refuses unless the player has just touched, clicked or pressed a key: the manual asks
# for each in a user input trigger, on the plugin-reference page named here. Request MIDI access is not
# among them: its page says some browsers allow it on startup, and the MIDI examples ask there first.
GESTURE_ACTIONS = {
    ("browser", "request-fullscreen"): "browser", ("browser", "request-install"): "browser",
    ("touch", "request-permission"): "touch", ("platforminfo", "request-wake-lock"): "platform-info",
    ("mouse", "request-pointer-lock"): "mouse", ("share", "share-text"): "share",
    ("clipboard", "request-paste-text"): "clipboard", ("clipboard", "request-paste-binary"): "clipboard",
    ("filechooser", "click"): "file-chooser", ("filesystem", "show-open-file-picker"): "filesystem",
    ("filesystem", "show-save-file-picker"): "filesystem", ("filesystem", "show-folder-picker"): "filesystem",
    ("bluetooth", "request-device"): "bluetooth", ("bbcmicrobit", "request-device"): "bbc-micro-bit",
    ("gamerecorder", "start-screen-recording-2"): "video-recorder",
    ("speechrecognition", "request-speech-recognition"): "speech-recognition", ("googleplay", "sign-in"): "google-play",
}
INPUT_PLUGINS = {"touch", "mouse", "keyboard", "button", "textbox", "list", "sliderbar", "htmlelement"}

# Pathfinding (manual: behavior-reference/pathfinding.md). With Obstacles set to Solids the obstacle map is
# built once at startup, so creating, destroying, moving or resizing a Solid, switching its Solid off or
# changing a Solid tilemap's tiles leaves paths routed round the old map until a Regenerate action runs.
SOLID_CHANGES = {"destroy", "set-x", "set-y", "set-position", "set-position-to-another-object", "move-forward",
                 "move-at-angle", "set-width", "set-height", "set-size", "erase-tile", "set-tile", "erase-tile-range",
                 "set-tile-range", "set-tile-with-brush", "erase-tile-with-brush", "set-tile-with-brush-by-name",
                 "erase-tile-with-brush-by-name", "set-tile-with-patch-brush", "erase-tile-with-patch-brush",
                 "set-tile-with-patch-brush-by-name", "erase-tile-with-patch-brush-by-name"}
REGENERATE = {"regenerate-obstacle-map", "regenerate-region", "regenerate-region-around-object"}
# A found path is there only after On path found: Move along path, and the node expressions, in the same
# actions as Find path read the previous path, unless Wait for previous actions to complete stands between.
PATH_NODES = re.compile(r"(\w+)\s*\.\s*(\w+)\s*\.\s*(?:nodecount|nodexat|nodeyat)\b", re.I)
# Conditions that keep an event from running every tick, beside the triggers.
PACING = {("system", "every-x-seconds"), ("system", "trigger-once-while-true")}
# Simulate control holds a control for the tick it runs in (manual: behavior-reference.md "Custom controls", the
# input events must be continually true), so under a trigger the object moves one tick and stops. Behavior id ->
# the controls held, None for all. A Platform jump starts on one tick, and Tile movement takes one tick as a move
# to the next tile: the official examples simulate both under On key pressed.
HELD_CONTROLS = {"platform": {"left", "right"}, "eightdir": None, "car": None}
# The trigger a held control was put under -> the condition that holds while the input is held, and the
# trigger's parameters it keeps.
HOLDING = {("keyboard", "on-key-pressed"): ("key-is-down", ("key",)),
           ("keyboard", "on-key-code-pressed"): ("key-code-is-down", ("keycode",)),
           ("gamepad", "on-button-pressed"): ("is-button-down", ("gamepad", "button")),
           ("touch", "on-touched-object"): ("is-touching-object", ("object",))}
# Conditions that test values, which hold until an event changes them; an overlap, a key held or a running timer
# change as the game plays. A Start timer under these alone, in an event that runs every tick, starts over each tick.
# Else is left out: it holds while the event before it fails, which may test anything.
VALUE_TESTS = {("System", "compare-two-values"), ("System", "compare-eventvar"), ("System", "compare-boolean-eventvar"),
               ("System", "evaluate-expression"), ("System", "is-between-values"), ("System", "every-tick"),
               ("System", "for-each"), ("System", "for-each-ordered"), ("System", "pick-by-evaluate"),
               ("System", "pick-by-comparison"), ("System", "pick-all")}
INSTANCE_VALUE_TESTS = {"compare-instance-variable", "is-boolean-instance-variable-set"}
# An object's expression in a value test, Player.X or Functions.canMove, reads what changes as the game plays;
# only Count and the variables wait for an event to change them.
OBJECT_EXPRESSION = re.compile(r"(?<![\w.])([A-Za-z_]\w*)\s*\.\s*([A-Za-z_]\w*)")
# Actions that change what a value test reads: a variable set or toggled, keyed by the parameter that names it.
# Add and Subtract are left out: a count stepped each tick still starts the timer over on every tick until its
# test fails.
SETS = {"set-eventvar-value": "variable", "set-boolean-eventvar": "variable", "toggle-boolean-eventvar": "variable",
        "set-instvar-value": "instance-variable", "set-boolean-instvar": "instance-variable",
        "toggle-boolean-instvar": "instance-variable"}
# What an object action changes and a condition tests, as the words an expression reads it by: the state a
# switch is kept in (check_undone).
STATE_SETS = {"set-animation-frame": "animationframe", "set-animation": "animationname", "set-visible": "isvisible",
              "set-instvar-value": None, "add-to-instvar": None, "subtract-from-instvar": None,
              "set-boolean-instvar": None, "toggle-boolean-instvar": None}
STATE_TESTS = {"compare-animation-frame": "animationframe", "is-animation-playing": "animationname",
               "is-visible": "isvisible"}
# System actions after which the event does not run again in the next tick.
LEAVES = {"set-group-active", "go-to-layout", "go-to-layout-by-name", "restart-layout", "go-to-nextprevious-layout"}
# Actions that flip a variable between two values: Toggle, and a Set of the variable to N - x, -x, x * -1,
# x = a ? b : a or x <> a ? a : b, with literal values. An event that runs every tick flips it back on the
# next tick.
TOGGLES = {"toggle-boolean-eventvar": "variable", "toggle-boolean-instvar": "instance-variable"}
FLIPS = {"set-eventvar-value": "variable", "set-instvar-value": "instance-variable"}
LITERAL = r'-?\d+(?:\.\d+)?|"(?:[^"]|"")*"'
# The comparison ids of Compare two values: 0 =, 1 ≠, 2 <, 3 ≤, 4 >, 5 ≥.
COMPARISONS = {0: "=", 1: "<>", 2: "<", 3: "<=", 4: ">", 5: ">="}
# How a condition tests that none of a type is left: X.Count or X.PickedCount = 0, ≤ 0 or < 1, with the operands
# in either order.
NONE_LEFT = re.compile(r"(\w+)\.(count|pickedcount)(?:=0|<=0|<1)|(?:0=|0>=|1>)(\w+)\.(count|pickedcount)", re.I)
# Sprite Font (manual: plugin-reference/sprite-font.md) draws a character outside its Character set as an
# empty space; with Enable BBCode on, the tags are markup, not characters, and \[ is a bracket.
SPRITE_FONT_TEXT = ("set-text", "append-text", "typewriter-text")
BBCODE_TAG = re.compile(r"(?<!\\)\[/?[a-z]+(?:=[^\]]*)?\]", re.I)
# Set text to replace(Self.Text, "###", ProjectVersion): the object's own text is a template, and "###" is
# replaced before the font draws it.
OWN_TEXT_REPLACED = re.compile(r'replace\s*\(\s*(\w+)\s*\.\s*text\s*,\s*("(?:[^"]|"")*")', re.I)
# What the r495.2 editor reads for a Sprite Font instance that leaves these properties out, asked of the
# editor on 2026-10-03. They fit the editor's own font image; the Character set maps its cells from the
# top-left. Enable BBCode left out reads as off.
SPRITE_FONT_DEFAULTS = {
    "character-set": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:?!-_~#\"'&()[]|`\\/@"
                     "°+=*$£€<>",
    "character-width": 16,
    "character-height": 16,
}
# Actions that name an effect by its name on the object, the layer or the layout. A name the target lacks
# runs and changes nothing.
EFFECT_ACTIONS = {"set-effect-parameter", "set-effect-enabled", "set-layer-effect-parameter", "set-layer-effect-enabled",
                  "set-layout-effect-parameter", "set-layout-effect-enabled"}


def call_arguments(text: str, end: int) -> int:
    """How many arguments the call that follows text[:end] passes, counting the commas
    outside nested parentheses; 0 when no parenthesis follows. Text literals are
    blanked to "" first, so a comma inside one is not counted."""
    i = end
    while i < len(text) and text[i].isspace():
        i += 1
    if i >= len(text) or text[i] != "(":
        return 0
    depth, count, start = 0, 1, i + 1
    for j in range(i, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return count if text[start:j].strip() else 0
        elif text[j] == "," and depth == 1:
            count += 1
    return count     # not closed: the editor names that syntax error itself


# find(text, find) and findcase take the text to search first. A one-character literal there
# with an expression after it is the other way round: find("^", LASTPOP) is -1 unless LASTPOP
# is "^" or empty. None of the 23 find calls of the 524 official examples has a literal first.
FIND_CALL = re.compile(r'(?<![\w.])(find|findcase)\s*\(\s*("(?:[^"]|"")*")\s*,', re.I)


def argument_at(expr: str, i: int) -> str:
    """The argument that starts at expr[i], up to the comma or parenthesis that ends it
    outside text literals and nested calls."""
    depth, j = 0, i
    while j < len(expr):
        c = expr[j]
        if c == '"':
            lit = STRING_LITERAL.match(expr, j)
            j = lit.end() if lit else len(expr)
            continue
        if c == "(":
            depth += 1
        elif c in "),":
            if depth == 0:
                break
            if c == ")":
                depth -= 1
        j += 1
    return expr[i:j].strip()


def arguments_from(expr: str, i: int) -> list[str]:
    """Every argument of the call whose opening parenthesis ends just before expr[i]."""
    args = []
    while True:
        arg = argument_at(expr, i)
        args.append(arg)
        j = expr.index(arg, i) + len(arg) if arg else i
        while j < len(expr) and expr[j] not in ",)":
            j += 1
        if j >= len(expr) or expr[j] == ")":
            return args
        i = j + 1


def outside_literals(expr: str, matches) -> list:
    """The regex matches that do not start inside a text literal of expr."""
    literals = [m.span() for m in STRING_LITERAL.finditer(expr)]
    return [m for m in matches if not any(a < m.start() < b for a, b in literals)]


def top_level_operator(expr: str) -> bool:
    """Whether expr has a comparison or a logical operator outside literals and parentheses,
    after its outer parentheses are taken off: a value that is true or false."""
    text = STRING_LITERAL.sub('""', expr).strip()
    while text.startswith("(") and text.endswith(")") and argument_at(text, 1) == text[1:-1].strip():
        text = text[1:-1].strip()
    depth = 0
    for c in text:
        depth += (c == "(") - (c == ")")
        if depth == 0 and c in "=<>&|":
            return True
    return False


# Three habits of a generated card game, none in the 565 event sheets of the 524 official
# examples (event-sheet-design-guidance.md, 2026-10-04): chooseindex(condition, a, b) as an
# if-else, which the examples write condition ? b : a; sibling events dispatching on
# find(<same text>, "<code>"); and a value looked up through two text literals,
# mid("FEMAW", find("WFAEM", X), 1), where the examples step a number with %.
CHOOSEINDEX_CALL = re.compile(r'(?<![\w.])chooseindex\s*\(', re.I)
FIND_LITERAL_SECOND = re.compile(r'(?<![\w.])(find|findcase)\s*\(', re.I)
MID_OF_LITERAL = re.compile(r'(?<![\w.])mid\s*\(\s*("(?:[^"]|"")*")\s*,', re.I)


def script_text(script) -> str:
    return "\n".join(script) if isinstance(script, list) else script if isinstance(script, str) else ""


def bare_name_in(code: str, name: str) -> bool:
    """name read as a variable of the script: not a member, a key or the script's own declaration."""
    n = re.escape(name)
    declared = (rf"\b(?:let|const|var|function|class)\s+{n}\b|(?<![\w$.]){n}\s*=>"
                rf"|\((?:\s*[\w$]+\s*,)*\s*{n}\s*(?:,\s*[\w$]+\s*)*\)\s*=>")
    if re.search(declared, code):
        return False
    return re.search(rf"(?<![\w$.]){re.escape(name)}(?![\w$])(?!\s*:(?!:))", code) is not None


def replaced_in_own_text(sheets: dict, families: dict) -> dict[str, set[str]]:
    """Object type -> the parts of its own text that a Set text replaces, "###" for
    replace(Self.Text, "###", ProjectVersion): a layout text that holds them is a template the events fill in.
    An action of a family replaces them in each member."""
    found: dict[str, set[str]] = {}

    def walk(events: list) -> None:
        for ev in events:
            if not isinstance(ev, dict):
                continue
            for a in ev.get("actions") or []:
                obj = a.get("objectClass") if isinstance(a, dict) and a.get("id") == "set-text" else None
                text = (a.get("parameters") or {}).get("text") if obj else None
                if not isinstance(obj, str) or not isinstance(text, str):
                    continue
                for m in OWN_TEXT_REPLACED.finditer(text):
                    if m.group(1).lower() in ("self", obj.lower()):
                        for t in families[obj].get("members", []) if obj in families else [obj]:
                            found.setdefault(t, set()).add(unquote(m.group(2)))
            if isinstance(ev.get("children"), list):
                walk(ev["children"])

    for sheet in sheets.values():
        if isinstance(sheet.get("events"), list):
            walk(sheet["events"])
    return found


def joined_literals(expr: str) -> list[str]:
    """The text literals an expression joins with & at its top level, unquoted: "Score: " & Score gives
    ["Score: "]; a literal that is an argument or a branch of a condition is left out."""
    parts, depth, start, quoted = [], 0, 0, False
    for i, ch in enumerate(expr):
        if ch == '"':
            quoted = not quoted     # a doubled quote inside a literal toggles twice
        elif not quoted and ch == "(":
            depth += 1
        elif not quoted and ch == ")":
            depth -= 1
        elif not quoted and depth == 0 and ch == "&":
            parts.append(expr[start:i])
            start = i + 1
    parts.append(expr[start:])
    return [unquote(p.strip()) for p in parts if is_literal(p.strip())]


def bare(value, options) -> str:
    """A combo item, a layout, an object and a variable are written bare; only an
    expression carries quotes. Says so when stripping the quotes gives a match."""
    if isinstance(value, str) and len(value) > 1 and value[0] == value[-1] == '"' and value[1:-1] in options:
        return f"; write it bare, \"{value[1:-1]}\": only an expression parameter carries inner quotes"
    return ""


def number_of(value) -> float | None:
    """A parameter written as a plain number, "1" or 1.0; None for any other expression."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def effect_names(holder: dict) -> set[str]:
    """The names of the effects an object type, family, layer or layout carries."""
    return {e["name"] for e in holder.get("effectTypes", []) if isinstance(e.get("name"), str)}


def layer_instances(layers: list):
    """Every instance on these layers and their sublayers, in the order the file lists them."""
    for layer in layers if isinstance(layers, list) else []:
        if isinstance(layer, dict):
            yield from (i for i in layer.get("instances") or [] if isinstance(i, dict))
            yield from layer_instances(layer.get("subLayers"))


def frames_of(folder, prefix=""):
    """(file name without its extension, frame) for every frame of an animations folder."""
    for anim in folder.get("items", []):
        for i, fr in enumerate(anim["frames"]):
            yield f"{prefix}{anim['name'].lower()}-{i:03d}", fr
    for sub in folder.get("subfolders", []):
        yield from frames_of(sub, prefix)


STYLE_RUN = 8      # actions in a row without a comment action
STYLE_TREE = 3     # sub-event levels below an event, when every leaf calls the same function
STYLE_LADDER = 5   # sibling events of one shape, their conditions and actions the same, only the values differ
COUNTDOWN_ON_INSTANCE = ("subtract-from-instvar", "add-to-instvar", "set-instvar-value")


def declarations(events: list):
    """Every variable and function parameter declared in a list of events and its sub-events."""
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if ev.get("eventType") == "variable":
            yield ev
        yield from ev.get("functionParameters") or []
        if isinstance(ev.get("children"), list):
            yield from declarations(ev["children"])


class Holder(NamedTuple):
    """What holds the trigger of an event branch."""
    name: str       # "Touch:on-touched-object", or "the function AddScore"
    fires: bool     # a trigger condition, as opposed to a function standing in for one

    @property
    def text(self) -> str:
        return f"an event that already has the trigger {self.name}" if self.fires \
            else f"{self.name}, which counts as a trigger"


class Checker:
    """The checks in the order run() calls them. A later one reads what an
    earlier one collected: the layers and template instances of the layouts,
    the functions and groups of every sheet."""

    def __init__(self, p: c3.Project, limit: int = 0, sheets: dict[str, dict] | None = None,
                 style: bool = False, review: bool = False) -> None:
        self.p = p
        self.review = review            # someone else's project: no omitted parameters, no next steps
        self.limit = limit
        self.unsaved = sheets or {}     # edit_sheet.py checks a sheet before it writes it
        self.style = style              # the warnings of check_style, off unless asked
        self.err, self.warn = p.err, p.warn
        self.layouts: dict[str, dict] = {}
        self.sheets: dict[str, dict] = {}
        self.layers: set[str] = set()
        self.templates: set[str] = set()      # types with an instance in some layout
        self.world_types: set[str] = set()    # types with an instance on a layer: they have X, Width, Angle ...
        self.uids: list[int] = []
        self.sids: list[int] = []        # sids of events, variables, object types, instances, files
        self.ace_sids: list[int] = []    # sids of condition and action entries
        self.class_sids: dict[int, list[str]] = {}    # sid -> the object types and families that have it
        self.group_titles: set[str] = set()
        self.functions: dict[str, int] = {}                     # name -> parameter count
        self.returns: dict[str, str] = {}                       # lowercase name -> functionReturnType
        self.custom_actions: dict[tuple[str, str], int] = {}    # (owner, name) -> parameter count
        self.pending_calls: list[tuple] = []
        self.created: set[str] = set()
        self._eases: set[str] = set()
        self.deprecated_uses: dict[str, list[str]] = {}      # warning -> where each use is
        self.global_ids: set[int] = set()     # the top-level variables of every sheet
        self.variable_names: set[str] = set()     # every variable and parameter name, as written
        self.load_order: dict[int, int] = {}     # id of a local or parameter -> its place in the sheets' order
        self.declared: dict[int, tuple[str, str, str]] = {}     # id -> (where, what a finding calls it, its scope)
        self.renamed: set[int] = set()     # ids of the locals and parameters the editor renames
        self.callables: dict[tuple[str, str], tuple[str, str]] = {}  # (owner or "", lower name) -> (name, where)
        self.numbers_on_disk = True      # whether the sheet being walked is the file, whose numbers a plan can name
        self.signalled: set[str] | None = set()     # literal tags a Signal raises; None once one is not literal
        self.awaited: list[tuple[str, str, str]] = []     # (tag, ACE id, where) of each Wait for signal and On signal
        self.layer_effects: dict[str, set[str]] = {}     # layer name -> its effects' names, in any layout
        self.layout_effects: set[str] = set()             # the effects of every layout
        # Sprite Font type -> the characters its instances draw, whether any has BBCode on
        self.font_sets: dict[str, tuple[set[str], bool]] = {}
        self.font_templates: dict[str, set[str]] = {}     # type -> the parts of its text a Set text replaces
        self.solid_obstacles = False      # a Pathfinding instance takes its obstacles from Solids
        self.solid_changes: list[str] = []    # where an action changes a Solid
        self.regenerated = False          # some action regenerates the obstacle map or a region of it
        self.function_blocks: dict[str, dict] = {}                 # name -> function block
        self.custom_blocks: dict[tuple[str, str], dict] = {}       # (owner, name) -> custom action block
        self.event_where: dict[int, str] = {}       # id(event) -> where it is, for a finding about another event
        self.answered: dict[int, dict] = {}         # id(event that starts with Else) -> the event before it
        self.action_lists: list[tuple[list, str]] = []     # (actions, where) of every block
        self._summaries: dict[int, tuple | None] = {}

    def check(self) -> None:
        self.check_project_file()
        self.check_names()
        self.check_animations()
        self.check_images()
        self.check_layouts()
        for obj in list(self.p.types) + list(self.p.families):
            self.check_namespace(obj)
        self.check_sheets()
        self.check_calls()
        self.check_uniqueness()
        self.check_files_and_addons()
        self.check_secrets()
        self.warn_deprecated()

    def deprecated_use(self, where: str, what: str) -> None:
        self.deprecated_uses.setdefault(what, []).append(where)

    def warn_deprecated(self) -> None:
        """One warning per deprecated ACE or expression, at its first use: a model
        writing from memory repeats `rgb` a dozen times, and a line for each would
        push the project's errors out of the report."""
        for what, wheres in self.deprecated_uses.items():
            more = len(wheres) - 1
            self.warn(f"{wheres[0]}: {what}" + (f"; used {more} more time{'s' if more > 1 else ''} after this" if more else ""))

    def run(self) -> int:
        self.check()
        return self.report()

    # --- project.c3proj -----------------------------------------------------------------
    def check_project_file(self) -> None:
        """What the editor reads before it opens a single file of the project. A
        hand-written project.c3proj that keeps only the keys the tools read opens
        as `TypeError: expected string`, a message that names neither the key nor
        the file; the editor writes all of these into every project it saves."""
        data = self.p.data
        props = data.get("properties")
        if not isinstance(props, dict):
            self.err("project.c3proj: no \"properties\" block; copy the one from a project the editor saved, "
                     f"or from {(self.p.rag / 'data' / 'c3-new-project' / 'project.c3proj').as_posix()}")
            props = {}
        missing = [k for k in PROJECT_TEXT if not isinstance(props.get(k), str)]
        if missing:
            written = ", ".join(f'"{k}": {json.dumps(PROJECT_TEXT[k])}' for k in missing)
            self.err(f"project.c3proj properties: {', '.join(missing)} "
                     f"{'is' if len(missing) == 1 else 'are'} missing or not text; the editor reads every "
                     f"property as it opens the project and stops with \"TypeError: expected string\" before "
                     f"it names a file. Write {written}")
        for key, options in PROJECT_OPTIONS.items():
            value = props.get(key)
            if value is None:
                rest = ", ".join(options[1:])
                self.err(f"project.c3proj properties: no \"{key}\"; the editor reads it on open and stops. "
                         f"Write \"{key}\": \"{options[0]}\", or "
                         f"{rest if len(options) == 2 else 'one of ' + rest}")
            elif value not in options and value not in PROJECT_ALSO.get(key, ()):
                name, labels = self.project_property_wording(key)
                listed = ", ".join(f"{o} ({labels[o]})" if o in labels else o for o in options)
                self.err(f"project.c3proj properties: {key}{f' ({name})' if name else ''} {value!r} is not one of "
                         f"{listed}; the editor stops with \"invalid {key}\" before the project opens, so it "
                         f"cannot be changed there. Write \"{key}\": \"{options[0]}\" in project.c3proj, or "
                         f"another of these")
        for key in ("viewportWidth", "viewportHeight"):
            value = data.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 2:
                self.err(f"project.c3proj: {key} is {value!r}; the editor reads it as a number of at least 2 "
                         f"and stops with \"invalid {'viewport width' if key.endswith('Width') else 'viewport height'}\"")
        self.check_project_index()
        fmt = data.get("projectFormatVersion")
        if fmt is not None and (not isinstance(fmt, int) or fmt > 1):
            self.err(f"project.c3proj: projectFormatVersion is {fmt!r}; the editor refuses anything above 1 with "
                     f"\"project from a future version of C3\". Write \"projectFormatVersion\": 1")
        self.check_saved_with_release()

    def check_project_index(self) -> None:
        """The lists project.c3proj keeps of what the project holds. The editor
        walks each one's items and subfolders as it opens, and reads containers as
        an array before it has read a file, so a list that is missing rather than
        empty stops the open with a type and nothing else."""
        data = self.p.data
        for key in ("objectTypes", "families", "layouts", "eventSheets"):
            block = data.get(key)
            if not isinstance(block, dict):
                folder = self.p.root / key
                found = sorted(f.stem for f in folder.glob("*.json")) if folder.is_dir() else []
                self.err(f"project.c3proj: no \"{key}\"; the editor reads the list before it reads a file and "
                         f"stops with \"TypeError: expected object\". Write \"{key}\": "
                         f"{{\"items\": {json.dumps(found)}, \"subfolders\": []}}")
                continue
            for part in ("items", "subfolders"):
                if not isinstance(block.get(part), list):
                    self.err(f"project.c3proj {key}: {part} is {block.get(part)!r}; the editor walks both lists "
                             f"as it opens the project. Write \"{part}\": []")
        # The editor opens every listed timeline and flowchart; a list copied from a new
        # project without its folders stops it with "missing file path 'timelines\Timeline 1.json'".
        for key in ("timelines", "flowcharts"):
            if isinstance(data.get(key), dict):
                for name, folder in folder_items(data[key]):
                    if isinstance(name, str) and self.p.project_file(key, name, folder) is None:
                        shown = Path(key) / folder / f"{name}.json"
                        self.err(f"{key}: {name} is listed in project.c3proj but {shown.as_posix()} is missing; the "
                                 f"editor stops with \"missing file path '{shown}'\". Take \"{name}\" out of the "
                                 f"\"{key}\" items, or copy the file from the project the list came from")
        if not isinstance(data.get("containers"), list):
            self.err(f"project.c3proj: containers is {data.get('containers')!r}; the editor reads it as an array "
                     f"before it has read a file and stops with \"TypeError: expected array\". A project with no "
                     f"container writes \"containers\": []")

    def check_saved_with_release(self) -> None:
        """The release decides where the editor looks for an object type: under
        r309 it reads objectTypes\\<name in lower case>.json, the layout of a
        project from 2016, and a project without the key is read as r86."""
        release = self.p.data.get("savedWithRelease")
        if not isinstance(release, int) or isinstance(release, bool):
            self.err(f"project.c3proj: savedWithRelease is {release!r}; without the release the editor reads the "
                     f"project as r86 and looks for objectTypes\\{'coin' if 'Coin' in self.p.types else 'name'}"
                     f".json in lower case. Write \"savedWithRelease\": 49502, or the release the editor that "
                     f"saved the project shows; a release newer than the editor opening it asks the user first")
            return
        if release < FOLDER_PROJECT_RELEASE:
            # by the name the folder holds, not by Path.exists(): a Windows file
            # system answers for Coin.json when the editor asks for coin.json
            folder = self.p.root / "objectTypes"
            have = {f.name for f in folder.glob("*.json")} if folder.is_dir() else set()
            wrong = [n for n in self.p.types if f"{n.lower()}.json" not in have]
            if wrong:
                self.err(f"project.c3proj: savedWithRelease {release} is below r309, so the editor reads an object "
                         f"type from objectTypes/<name in lower case>.json; {', '.join(sorted(wrong)[:3])} "
                         f"{'has' if len(wrong) == 1 else 'have'} no such file. Write the release that saved the "
                         f"project, for example \"savedWithRelease\": 49502")

    # --- names, addon ids, families -----------------------------------------------------
    def check_name(self, where: str, what: str, name: str, is_object: bool) -> None:
        kept = editor_name(name, is_object)
        if kept != name:
            self.err(f"{where}: the editor does not keep the {what} name {name!r} as written"
                     + (f", it becomes {kept!r}" if kept else "")
                     + "; use letters, digits and underscores, starting with a letter")

    def check_addon_id(self, kind: str, addon_id: str, where: str) -> None:
        """The editor looks an addon up by its exact id, so 'sprite' or 'Tiledbg'
        fails to open even though the schema file is found case-insensitively."""
        exact = self.p.index.get(kind, {}).get(addon_id.lower(), {}).get("originalId")
        if exact and exact != addon_id:
            self.err(f"{where}: {kind[:-1]} id {addon_id!r} must be written {exact!r}; addon ids are case-sensitive")

    def reserved(self, name: str) -> str:
        """Why the editor reserves an object type's or family's name, or "" when it does not."""
        low = LOWER(name)
        if low in RESERVED_WORDS:
            return f"{low} is a reserved word"
        if low in DEVICE_NAMES:
            return f"{low} is a device name that Windows reserves"
        if low in self.p.system_expression_names:
            return f"{low} is a system expression"
        return ""

    def check_reserved(self, kind: str, name: str, used: set[str]) -> None:
        """A reserved name: the editor opens the project and renames the object, and an expression
        that names it by the old name fails."""
        if LOWER(name) == "system":
            what = "object type" if kind == "object type" else "object class"
            self.err(f"{kind} {name} has the name of the System object, compared without case; the editor stops "
                     f"with \"{what} name '{name}' already used\". Rename it, for example {name}Object")
            return
        why = self.reserved(name)
        if not why:
            return
        new = next_name(name)
        while LOWER(new) in used and not self.reserved(new):
            new = next_name(new)
        if self.reserved(new):
            self.err(f"{kind} {name}: {why}. The editor renames it to {new} when it opens the project, and {new} "
                     f"is reserved too, so the open stops with \"name is reserved\". Rename it, for example "
                     f"{name}Object")
            return
        if LOWER(name) == "self":   # in an expression the word is Self, whatever object has the name
            lost = (f"{name}.X in an expression reads as Self, and in a System action the editor stops with "
                    f"\"Invalid use of 'self'\"")
        else:
            lost = (f"an expression that names {name}, such as {name}.X, stops the open with \"Not an object: "
                    f"'{name}' is not an object name\"")
        self.err(f"{kind} {name}: {why}, so the editor renames it to {new} when it opens the project. Its "
                 f"conditions and actions follow the new name, but {lost}. A script finds no "
                 f"runtime.objects.{name}. Rename it, for example {name}Object")

    def check_names(self) -> None:
        p = self.p
        used = {LOWER(n) for n in (*p.types, *p.families, p.functions_object, "system")}
        for kind, listed in (("object type", p.types), ("family", p.families)):
            for name, t in listed.items():
                if t.get("name") != name:
                    self.err(f"{kind} {name}: the file says \"name\": {t.get('name')!r}; "
                             f"it must be the name listed in project.c3proj")
                self.check_name(f"{kind} {name}", kind, name, True)
                self.check_reserved(kind, name, used)
                self.check_addon_id("plugins", t["plugin-id"], f"{kind} {name}")
                for b in t.get("behaviorTypes", []):
                    self.check_addon_id("behaviors", b["behaviorId"], f"{kind} {name} behavior {b['name']}")
                    self.check_name(f"{kind} {name}", "behavior", b["name"], True)
                for v in t.get("instanceVariables", []):
                    self.check_name(f"{kind} {name}", "instance variable", v["name"], False)
                    if v.get("type") not in VARIABLE_TYPES:
                        self.err(f"{kind} {name}: instance variable {v['name']}: type {v.get('type')!r} is not "
                                 f"number, string or boolean; the editor's Text type is written \"string\"")
        for a in p.data.get("usedAddons", []):
            if a.get("type") in ("plugin", "behavior"):
                self.check_addon_id(a["type"] + "s", a["id"], "project.c3proj usedAddons")
                p.schema(a["type"] + "s", a["id"])     # an id by Scirra that no addon has is reported here
        for name in p.types:
            if LOWER(name) == LOWER(p.functions_object):
                self.err(f"object type {name} has the name of the built-in {p.functions_object} object, which "
                         f"project.c3proj names in \"functionsName\", compared without case. Functions are "
                         f"built in: delete "
                         f"objectTypes/{name}.json, its name in the objectTypes items and its usedAddons entry; "
                         f"an action of a function writes \"objectClass\": \"{p.functions_object}\"")
        # Object types, families and the Functions object share one namespace, without case.
        def listed(folder) -> list[str]:
            folder = folder if isinstance(folder, dict) else {}
            return [n for n in folder.get("items", []) if isinstance(n, str)] + [
                n for sub in folder.get("subfolders", []) for n in listed(sub)]
        seen: dict[str, str] = {}
        for name in listed(p.data.get("objectTypes")):
            if LOWER(name) in seen:
                self.err(f"project.c3proj lists object type {name} twice; the editor stops with \"object type "
                         f"name '{name}' already used\": list it once")
            seen[LOWER(name)] = f"object type {seen.get(LOWER(name), name)}"
        seen.setdefault(LOWER(p.functions_object), f"the {p.functions_object} object")
        for name in listed(p.data.get("families")):
            if LOWER(name) in seen:
                self.err(f"family {name} has the name of {seen[LOWER(name)]}, once case is ignored; the editor stops "
                         f"with \"object class name '{name}' already used\": rename the family")
            seen[LOWER(name)] = f"family {name}"

        for name, t in p.types.items():
            p.schema("plugins", t["plugin-id"])
            for b in t.get("behaviorTypes", []):
                p.schema("behaviors", b["behaviorId"])
        for fam, f in p.families.items():
            p.schema("plugins", f["plugin-id"])
            for b in f.get("behaviorTypes", []):
                p.schema("behaviors", b["behaviorId"])
            for m in f.get("members", []):
                if m not in p.types:
                    self.err(f"family {fam}: member {m} is not an object type")
                elif p.types[m]["plugin-id"] != f["plugin-id"]:
                    self.err(f"family {fam}: member {m} is a {p.types[m]['plugin-id']}, the family is {f['plugin-id']}")
        for c in p.data.get("containers", []):
            for m in c.get("members", []):
                if m not in p.types:
                    self.err(f"container {c.get('members')}: member {m} is not an object type")

    # --- images: {type}-{animation}-{frame:03d}.png per frame, {type}.png for single-image plugins ---
    def check_image(self, stem: str, entry: dict) -> None:
        """The image file of a frame or a single-image type. Its size is not compared with the
        entry's width and height: the editor takes the size from the file. An image imported in a
        lossy format and not edited since keeps that format, which the entry's fileType names."""
        folder = self.p.root / "images"
        file_type = entry.get("fileType") or "image/png"
        if (folder / f"{stem}.png").exists():
            return
        if file_type != "image/png" and folder.is_dir() and any(f.stem.lower() == stem for f in folder.iterdir()):
            return
        shown = f"images/{stem}.png" if file_type == "image/png" else f"images/{stem} as {file_type}"
        self.err(f"missing image {shown}: the editor reads a frame from images/<object type>-<animation>-<frame "
                 f"number, three digits>.png and a single image from images/<object type>.png, in lower case")

    def check_animations(self) -> None:
        for name, t in self.p.types.items():
            if t.get("plugin-id") in ANIMATED_PLUGINS and not isinstance(t.get("animations"), dict):
                self.err(f"object type {name}: a {t['plugin-id']} carries an animations folder and the editor "
                         f"reads it as it opens the type. Write \"animations\": {{\"items\": [{{\"name\": "
                         f"\"Default\", \"frames\": [...], \"sid\": <n>}}], \"subfolders\": []}}")
            if t.get("plugin-id") in IMAGE_PLUGINS and not isinstance(t.get("image"), dict):
                instead = " in place of its animations" if "animations" in t else ""
                self.err(f"object type {name}: a {t['plugin-id']} carries one image and the editor reads it as it "
                         f"opens the type. Write{instead} \"image\": {{\"width\": <w>, \"height\": <h>, "
                         f"\"originX\": 0.5, \"originY\": 0.5, \"originalSource\": \"\", \"exportFormat\": "
                         f"\"lossless\", \"exportQuality\": 0.8, \"imageSpriteId\": <n>, \"useCollisionPoly\": "
                         f"true}}, the size of images/{name.lower()}.png")
            if isinstance(t.get("animations"), dict):
                self.check_collision_polys(name, t["animations"])

    def check_collision_polys(self, name: str, folder: dict) -> None:
        """A frame's collision polygon is three or more x, y pairs; a frame without collisionPoly
        takes the whole image."""
        for anim in folder.get("items", []):
            for i, fr in enumerate(anim.get("frames", [])):
                poly = fr.get("collisionPoly") if isinstance(fr, dict) else None
                points = poly.get("points") if isinstance(poly, dict) else None
                if not isinstance(points, list) or (len(points) >= 6 and len(points) % 2 == 0):
                    continue
                pairs = len(points) % 2 == 0
                held = (f"{len(points) // 2} point{'' if len(points) == 2 else 's'}, {json.dumps(points)}" if pairs
                        else f"{len(points)} numbers, {json.dumps(points)}, which are not x, y pairs")
                said = ("must have at least three points in a collision poly" if pairs
                        else "must have an even number of elements in collision poly points array")
                self.err(f"object type {name} animation {anim.get('name')} frame {i}: collisionPoly holds {held}; "
                         f"the editor opens the project, then stops the preview with \"assertion "
                         f"failure: {said}\". Write three or more x, y pairs from 0 to 1 across the image, or leave "
                         f"collisionPoly out for the whole image")
        for sub in folder.get("subfolders", []):
            self.check_collision_polys(name, sub)

    def check_images(self) -> None:
        sprite_ids: dict[int, list[str]] = {}    # imageSpriteId -> each image or frame that has it
        files = self.p.listed_files("objectTypes")
        for name, t in self.p.types.items():
            shown = (f"{name} ({files[name].relative_to(self.p.root).as_posix()})" if files.get(name)
                     else name)
            if isinstance(t.get("image"), dict):
                self.check_image(name.lower(), t["image"])
                sprite_ids.setdefault(t["image"].get("imageSpriteId"), []).append(f"the image of {shown}")
            for stem, fr in frames_of(t.get("animations", {}), f"{name.lower()}-"):
                self.check_image(stem, fr)
                if isinstance(fr, dict):
                    sprite_ids.setdefault(fr.get("imageSpriteId"), []).append(f"the frame images/{stem}.png of {shown}")
        self.check_sprite_ids(sprite_ids)

    def check_sprite_ids(self, sprite_ids: dict) -> None:
        """Report an imageSpriteId that two images or frames share.
        The editor keeps one set of these ids for the project and stops on a repeated one.
        -1 is skipped, because the editor's loader gives it a new id."""
        taken = {s for s in sprite_ids if isinstance(s, int)}
        for s, owners in sprite_ids.items():
            if not isinstance(s, int) or s < 0 or len(owners) < 2:
                continue
            free = []
            n = s
            while len(free) < len(owners) - 1:
                # seven digits, as the editor and the generator write them
                n = n + 1 if n + 1 < 10**7 else 10**6
                if n not in taken:
                    free.append(n)
                    taken.add(n)
            self.err(f"{' and '.join(owners)} share the imageSpriteId {s}, and the editor stops with \"id already "
                     f"in use\" before the project opens. Keep {s} on one of them. Give "
                     + ("the other" if len(owners) == 2 else "each other one")
                     + " an imageSpriteId that no image or frame of the project has, for example "
                     + ", ".join(str(n) for n in free))

    # --- layouts ----------------------------------------------------------------------------
    def collect_sids(self, obj, in_ace: bool = False) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "sid" and isinstance(v, int):
                    (self.ace_sids if in_ace else self.sids).append(v)
                # instanceFolderItem and scene-graphs-folder-root are editor references that repeat an instance's sid
                if k not in ("instanceFolderItem", "scene-graphs-folder-root"):
                    self.collect_sids(v, in_ace or k in ("conditions", "actions"))
        elif isinstance(obj, list):
            for v in obj:
                self.collect_sids(v, in_ace)

    def check_properties(self, where: str, props: dict, schema_props: dict | None) -> None:
        """A property the schema does not list is a warning: older projects keep
        keys the editor has since renamed (z-height), and the editor drops them."""
        if schema_props is None:
            return
        for k, v in props.items():
            if k not in schema_props:
                self.warn(f"{where}: property {k} is not in the current schema")
                continue
            items = (schema_props[k] or {}).get("items")
            if items and v not in items:
                self.err(f"{where}: {k}={v!r} is not one of {list(items)}")

    def check_effects(self, effect_types: list) -> None:
        """Only whether the effect has a schema; an unknown one is warned about once."""
        for e in effect_types:
            self.p.schema("effects", e.get("effectId", e.get("id", "")))

    def check_instance(self, where: str, inst: dict) -> None:
        p = self.p
        t = inst.get("type")
        if not isinstance(inst.get("uid"), int):
            self.err(f"{where}: instance of {t} has no integer uid")
        else:
            self.uids.append(inst["uid"])
        self.templates.add(t)
        if t not in p.types:
            self.err(f"{where}: instance of unknown type {t}{closest(t or '', p.types)}")
            return
        ivars = p.ivars_of(t)
        ivar_types = p.ivar_types_of(t)
        for iv, value in inst.get("instanceVariables", {}).items():
            if iv not in ivars:
                self.err(f"{where}: {t} has no instance variable {iv}")
            elif ivar_types[iv] in JSON_TYPES and not JSON_TYPES[ivar_types[iv]](value):
                self.err(f"{where}: {t} instance variable {iv} = {value!r}; a {ivar_types[iv]} is written as "
                         f"{JSON_EXAMPLES[ivar_types[iv]]} here, a JSON value, not text")
        angle = inst.get("world", {}).get("angle", 0)
        if isinstance(angle, (int, float)) and abs(angle) > FULL_TURN:
            self.err(f"{where}: {t} world angle {angle} is more than a full turn; the file stores radians, "
                     f"{angle} degrees is {math.radians(angle):.4f}")
        for iv in ivars - set(inst.get("instanceVariables", {})):
            self.err(f"{where}: {t} instance has no value for instance variable {iv}")
        behs = p.behaviors_of(t)
        for b in inst.get("behaviors", {}):
            if b not in behs:
                self.err(f"{where}: {t} has no behavior {b}")
        for b in set(behs) - set(inst.get("behaviors", {})):
            self.err(f"{where}: {t} instance has no properties block for behavior {b}")
        plugin = p.schema("plugins", p.plugin_of[t])
        self.check_properties(f"{where}: {t}", inst.get("properties", {}), plugin.get("properties") if plugin else None)
        for b, block in inst.get("behaviors", {}).items():
            if b in behs and not (isinstance(block, dict) and isinstance(block.get("properties"), dict)):
                bs = p.schema("behaviors", behs[b])
                ids = list((bs or {}).get("properties") or {})
                values = ", ".join(f'"{k}": true' if k == "enabled" else f'"{k}": ...' for k in ids)
                self.err(f"{where}: {t} instance behavior {b} is {json.dumps(block)}, with no \"properties\" "
                         f"block; the editor reads it as it opens the layout. Write \"{b}\": {{\"properties\": "
                         f"{{{values}}}}}")
                continue
            if b in behs:
                bs = p.schema("behaviors", behs[b])
                self.check_properties(f"{where}: {t}.{b}", block.get("properties", {}),
                                      bs.get("properties") if bs else None)
                if behs[b].lower() == "pathfinding" and block.get("properties", {}).get("obstacles", "solids") == "solids":
                    self.solid_obstacles = True
        if p.plugin_of[t].lower() == "spritefont2":
            self.check_sprite_font_instance(where, t, inst.get("properties", {}))
        anims = p.animations_of(t)
        initial = inst.get("properties", {}).get("initial-animation")
        if anims is not None and initial is not None and LOWER(initial) not in anims:
            self.err(f"{where}: {t} has no animation {initial!r} for initial-animation")

    def check_sprite_font_instance(self, where: str, t: str, props: dict) -> None:
        """Records the characters this instance draws, for the type's Set text actions, and checks its own text
        without the parts a Set text replaces. A property the instance leaves out is read as the editor fills it."""
        missing = [k for k in SPRITE_FONT_DEFAULTS if k not in props]
        if missing:
            self.warn(f"{where}: {t} instance has no {', '.join(missing)}; the editor fills "
                      + ", ".join(f"{k} {json.dumps(SPRITE_FONT_DEFAULTS[k], ensure_ascii=False)}" for k in missing)
                      + ", which fit the font image the editor draws for a new Sprite Font. Write what this font "
                        "image has: character-set, the characters in the order its cells draw them, left to right "
                        "and top to bottom; character-width and character-height, one cell in pixels")
        charset = props.get("character-set", SPRITE_FONT_DEFAULTS["character-set"])
        if not isinstance(charset, str):
            return
        bbcode = props.get("enable-bbcode", False) is not False
        chars, any_bbcode = self.font_sets.get(t, (set(), False))
        self.font_sets[t] = (chars | set(charset), any_bbcode or bbcode)
        text = props.get("text")
        if isinstance(text, str):
            for part in self.font_templates.get(t, ()):
                text = text.replace(part, "")
            self.check_sprite_font_text(f"{where}: {t} text", t, text, set(charset), bbcode)

    def check_sprite_font_text(self, where: str, t: str, text: str, charset: set[str], bbcode: bool) -> None:
        shown = BBCODE_TAG.sub("", text).replace("\\[", "[") if bbcode else text
        missing = list(dict.fromkeys(c for c in shown if not c.isspace() and c not in charset))
        if missing:
            self.warn(f"{where}: {', '.join(map(repr, missing))} {'is' if len(missing) == 1 else 'are'} not in "
                      f"the Character set of "
                      f"the Sprite Font {t}, which draws {'it' if len(missing) == 1 else 'each'} as an empty space "
                      f"(manual: plugin-reference/sprite-font.md); add {'it' if len(missing) == 1 else 'them'} to "
                      f"the Character set and the font image, or show the text with a Text object")

    def check_number(self, where: str, what: str, value, least: float | None = None) -> bool:
        """A value the editor reads through its finite-number assertion. Text in
        place of a number stops the open with the assertion and nothing else."""
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            self.err(f"{where}: {what} is {value!r}; the editor reads it as a number and stops with "
                     f'"TypeError: expected finite number"')
            return False
        if least is not None and value < least:
            self.err(f"{where}: {what} is {value}; the editor refuses anything below {least}")
            return False
        return True

    def walk_layers(self, where: str, layer_list: list) -> None:
        for layer in layer_list:
            name = layer.get("name")
            here = f"{where} layer {name}"
            if not (isinstance(name, str) and name):
                self.err(f"{where}: a layer is named {name!r}; the editor reads a layer name as text and "
                         f'stops with "TypeError: expected string"')
            else:
                self.layers.add(name)
                self.layer_effects.setdefault(name, set()).update(effect_names(layer))
            for what in LAYER_NUMBERS:
                self.check_number(here, what, layer.get(what))
            if layer.get("blendMode") not in BLEND_MODES:
                self.err(f"{here}: blendMode is {layer.get('blendMode')!r}; the editor stops with "
                         f'"invalid blend mode". Write "blendMode": "normal", or one of '
                         f"{', '.join(BLEND_MODES[1:])}")
            if not isinstance(layer.get("instances"), list):
                self.err(f"{here}: instances is {layer.get('instances')!r}; the editor walks the list as it "
                         f'opens the layer. A layer with nothing on it writes "instances": []')
            self.check_effects(layer.get("effectTypes", []))
            for inst in layer.get("instances", []) if isinstance(layer.get("instances"), list) else []:
                self.world_types.add(inst.get("type"))
                self.check_world(here, inst)
                self.check_instance(here, inst)
            self.walk_layers(where, layer.get("subLayers", []))

    def check_world(self, where: str, inst: dict) -> None:
        """Where and how big an instance is on the layer. The editor reads the
        block before it reads the instance's own properties."""
        world = inst.get("world")
        if not isinstance(world, dict):
            self.err(f"{where}: {inst.get('type')} has no world block; an instance on a layer carries "
                     f'"world": {{"x": 0, "y": 0, "width": 32, "height": 32, "originX": 0.5, "originY": 0.5}}')
            return
        for what in WORLD_NUMBERS:
            self.check_number(f"{where}: {inst.get('type')}", f"world.{what}", world.get(what))

    def check_layouts(self) -> None:
        p = self.p
        self.layouts = p.load_listed("layouts")
        self.sheets = {**p.load_listed("eventSheets"), **self.unsaved}
        self.font_templates = replaced_in_own_text(self.sheets, p.families)
        for lname, lay in self.layouts.items():
            self.collect_sids(lay)
            if not (isinstance(lay.get("name"), str) and lay["name"]):
                self.err(f"layout {lname}: the file says \"name\": {lay.get('name')!r}; the editor reads it "
                         f"as text and stops with \"TypeError: expected string\"")
            for what in ("width", "height"):
                self.check_number(f"layout {lname}", what, lay.get(what), 2)
            if not isinstance(lay.get("layers"), list):
                self.err(f"layout {lname}: layers is {lay.get('layers')!r}; the editor walks the list as it "
                         f"opens the layout, before it reads anything on it")
                continue
            self.walk_layers(f"layout {lname}", lay["layers"])
            self.check_default_controls(lname, lay["layers"])
            for inst in lay.get("nonworld-instances", []):
                self.check_instance(f"layout {lname}", inst)
            self.check_effects(lay.get("effectTypes", []))
            self.layout_effects |= effect_names(lay)
            if lay.get("eventSheet") and lay["eventSheet"] not in self.sheets:
                self.err(f"layout {lname}: event sheet {lay['eventSheet']} does not exist")

        for name, t in p.types.items():
            if "singleglobal-inst" in t:
                self.uids.append(t["singleglobal-inst"]["uid"])
                plugin = p.schema("plugins", t["plugin-id"])
                self.check_properties(f"{name}", t["singleglobal-inst"].get("properties", {}),
                                      plugin.get("properties") if plugin else None)
            self.check_effects(t.get("effectTypes", []))
            self.collect_sids(t)
            self.class_sids.setdefault(t.get("sid"), []).append(name)
        for fname, f in p.families.items():
            self.collect_sids(f)
            self.class_sids.setdefault(f.get("sid"), []).append(f"family {fname}")
        self.collect_sids(p.data.get("rootFileFolders", {}))

    def check_default_controls(self, lname: str, layers: list) -> None:
        """Default controls is a property of each instance of a movement behavior, and every instance with it
        on moves with the arrow keys. An instance without the property reads as on, as the editor fills it.
        Instances of two or more object types with it on in one layout walk together: a crate given Platform
        to be pushed walks with the player. One type steered on purpose, two knights that move as one, passes."""
        steered: dict[str, tuple[int, list[str]]] = {}     # type -> (instances, behavior names)
        for inst in layer_instances(layers):
            t = inst.get("type")
            behs = self.p.behaviors_of(t) if t in self.p.types else {}
            names = []
            for b, block in (inst.get("behaviors") or {}).items():
                schema = self.p.schema("behaviors", behs[b]) if b in behs else None
                props = block.get("properties") if isinstance(block, dict) else None
                if (schema and "default-controls" in (schema.get("properties") or {}) and isinstance(props, dict)
                        and props.get("default-controls", True) is not False):
                    names.append(b)
            if names:
                n, known = steered.get(t, (0, []))
                steered[t] = (n + 1, known + [b for b in names if b not in known])
        if len(steered) < 2:
            return
        listed = "; ".join(f"{t} ({n} instance{'s' if n > 1 else ''}, {', '.join(bs)})"
                           for t, (n, bs) in steered.items())
        self.warn(f"layout {lname}: {listed} have Default controls on, so all of them move with the arrow keys "
                  f"together. Keep it on for the object the player steers. In every layout, give each instance "
                  f"of the others \"default-controls\": false in its behavior's properties, and move it with "
                  f"Simulate control or the behavior's actions (manual: behavior-reference/platform.md "
                  f"\"Default controls\")")

    def check_namespace(self, obj: str) -> None:
        """`Enemy.Angle` has to mean one thing, so the editor refuses an instance
        variable, behavior or effect named like another one on the object or its
        families, or like an expression of the plugin. Names compare without case:
        instance variables hp and HP of Thing stopped the r495.2 and r504 editors with
        "name 'HP' already in object class 'Thing' namespace", and a family's hp beside
        a member's HP with the family named."""
        p = self.p
        declared: dict[str, tuple[str, str]] = {}     # lower name -> (label, name)
        for owner in [obj] + p.families_of(obj):
            d = p.types.get(owner) or p.families.get(owner) or {}
            entries = ([("instance variable", v["name"], v.get("type")) for v in d.get("instanceVariables", [])]
                       + [("behavior", b["name"], None) for b in d.get("behaviorTypes", [])]
                       + [("effect", e["name"], None) for e in d.get("effectTypes", []) if "name" in e])
            for what, name, vtype in entries:
                label = f"{what} {name}" + (f" of family {owner}" if owner != obj else "")
                if LOWER(name) in declared:
                    other, first = declared[LOWER(name)]
                    rename = f", for example {name}{SHADOW_SUFFIX.get(vtype, 'Value')}" if vtype else ""
                    self.err(f"{obj}: {label} has the same name as {other}{case_aside(name, first)}; the editor "
                             f"stops with \"name '{name}' already in object class '{owner}' namespace\" before the "
                             f"project opens. Rename {name}{rename}")
                declared[LOWER(name)] = (label, name)
        plugin = p.schema("plugins", p.plugin_of[obj])
        expressions = p.expressions_of(plugin)
        members = p.families[obj].get("members", []) if obj in p.families else [obj]
        if any(m in self.world_types for m in members):
            expressions |= p.common_expressions_of(plugin)
        for key, (label, _) in declared.items():
            if key in expressions and " of family " not in label:
                self.err(f"{obj}: {label} collides with the expression {obj}.{key}; rename it")

    # --- event sheets: expressions and parameters -------------------------------------------
    def check_expr(self, where: str, expr, scope: dict, owner: str | None = None,
                   stand_in: str | None = None) -> None:
        """owner: the object of the condition or action the expression belongs to;
        Self names it, so Self in a System parameter names nothing, and the editor
        stops with 'Invalid use of self'. stand_in: the object a System parameter
        of the same ACE names, the one to write instead of Self."""
        p = self.p
        if not isinstance(expr, str):
            return
        if not expr.strip():
            self.err(f"{where}: the expression is empty; the editor stops with \"Empty expression: You must enter an "
                     f"expression\". Empty text is the literal \"\" (\"\\\"\\\"\" in the JSON), a number 0")
            return
        if expr.count('"') % 2:     # a quote inside a literal is doubled, so an odd count leaves one open
            self.err(f"{where}: a text literal is not closed; the editor stops with \"Syntax error: String missing "
                     f"finishing \\\"\". A quote inside text is doubled: \"say \"\"hi\"\"\"")
            return
        text = STRING_LITERAL.sub('""', expr)
        if "\\" in text:
            self.err(f"{where}: a backslash stands outside a text literal; the editor stops with \"Syntax error: "
                     f"Unknown character\". Inside text it is a plain character: Construct has no escapes")
        # A list literal [a, b] of JavaScript: the editor stopped a QQ bot's sheet with it (2026-10-06).
        if "[" in text or "]" in text:
            self.err(f"{where}: a square bracket stands outside a text literal; the editor stops with \"Syntax "
                     f"error: Unknown character\". Expressions have no lists: compare each value on its own, "
                     f"a = 1 & b = 2, or keep the values in an Array object")
        scope_lower = {LOWER(k) for k in scope}
        self.check_find(where, expr)
        if self.style:
            self.check_chooseindex(where, expr, scope)
            self.check_letter_table(where, expr)
        found = [m.group(0) for m in C_OPERATOR.finditer(text)]
        if found:
            # Rewrite outside the string literals only: "a == b" as text is valid.
            parts, last = [], 0
            for lit in STRING_LITERAL.finditer(expr):
                parts += [C_OPERATOR.sub(lambda m: C_OPERATORS.get(m.group(0), m.group(0)), expr[last:lit.start()]),
                          lit.group(0)]
                last = lit.end()
            parts.append(C_OPERATOR.sub(lambda m: C_OPERATORS.get(m.group(0), m.group(0)), expr[last:]))
            fixed = "".join(parts)
            ops = list(dict.fromkeys(found))
            hint = (f"; write {fixed!r}" if "!" not in found
                    else "; = compares, <> is not equal, & is and, | is or, and a negation is a comparison with 0")
            self.err(f"{where}: {', '.join(ops)} {'is not an operator' if len(ops) == 1 else 'are not operators'} "
                     f"of Construct expressions; the editor stops with "
                     f"\"Syntax error\"{hint}")
        # With a variable or parameter named self in scope, a bare self reads as it; self. is still Self.
        variable_self = "self" in scope_lower
        if owner == "System" and any(LOWER(m.group(0)) == "self" and not (
                variable_self and not text[m.end():].lstrip().startswith(".")) for m in IDENT.finditer(text)):
            pattern = r"\bself\b(?=\s*\.)" if variable_self else r"\bself\b"
            fixed = re.sub(pattern, stand_in, expr, flags=re.I) if stand_in else None
            hint = f"; write {fixed!r}" if fixed else "; name the object instead"
            self.err(f"{where}: Self names the object of the condition or action, and here that is System; "
                     f"the editor stops with \"Invalid use of 'self'\"{hint}")
        for m in MEMBER.finditer(text):
            obj, member, sub = m.group(1), m.group(2), m.group(3)
            if LOWER(obj) == "self" or NUMBER.fullmatch(obj):   # a decimal such as 0.5 is not a member access
                continue
            if LOWER(obj) == LOWER(p.functions_object):
                names = p.expression_names(p.system)
                mapped = [e for e in p.system.get("expressions", [])
                          if c3.is_functions_ace(e) and LOWER(names.get(e["id"], "")) == LOWER(member)]
                if mapped and LOWER(member) not in {LOWER(f) for f in self.functions}:
                    # Functions.CallMapped is an expression of the Functions object, not a function of the project
                    self.check_arguments(where, f"{obj}.{member}", [(p.system, {"expressions": mapped})], member,
                                         text, m.end(2))
                elif LOWER(member) not in {LOWER(f) for f in self.functions}:
                    self.err(f"{where}: {obj}.{member} is not a defined function")
                elif self.returns.get(LOWER(member)) == "none":
                    self.err(f"{where}: {obj}.{member} has no return type, and the editor stops with \"The function "
                             f"'{member}' has a return type of 'None' so cannot be used as an expression\": give it a "
                             f"return type and a Set return value, or call it as an action")
                elif EMPTY_CALL.match(text, m.end(2)):
                    # No official example writes an empty pair; the editor stops at it (r504, 2026-10-02).
                    self.err(f"{where}: {obj}.{member}() has an empty pair of parentheses; the editor stops with "
                             f"\"Syntax error: ')' can't go here\". A function without parameters is called "
                             f"without them: {obj}.{member}")
                continue
            obj = p.objects_lower.get(LOWER(obj))
            if obj is None or obj == "System":
                # JSON.Get names the plugin; an expression is reached through the project's object of it.
                users = [n for n, pl in p.plugin_of.items() if squash(pl) == squash(m.group(1)) and pl != "system"]
                hint = f"; {m.group(1)} is the plugin, the object of it here is {', '.join(users)}" if users \
                    else closest(m.group(1), p.plugin_of)
                self.err(f"{where}: unknown object {m.group(1)} in expression{hint}")
                continue
            behs = {LOWER(k): v for k, v in p.behaviors_of(obj).items()}
            if LOWER(member) in behs:
                bs = p.schema("behaviors", behs[LOWER(member)])
                if bs is None:
                    continue
                retired = p.deprecated_expressions("behaviors", behs[LOWER(member)]).get(LOWER(sub or ""))
                if retired:
                    self.deprecated_use(where, self.deprecated_expression(f"{obj}.{member}.{sub}", behs[LOWER(member)], retired))
                elif sub is None or LOWER(sub) not in p.expressions_of(bs):
                    self.err(f"{where}: {obj}.{member}.{sub or ''} is not an expression of behavior "
                             f"{behs[LOWER(member)]}")
                else:
                    self.check_arguments(where, f"{m.group(1)}.{member}.{sub}", [(bs, None)], sub, text, m.end(3))
                continue
            plugin = p.schema("plugins", p.plugin_of[obj])
            if plugin is None:
                continue
            ivars = {LOWER(v) for v in p.ivars_of(obj)}
            retired = p.deprecated_expressions("plugins", p.plugin_of[obj]).get(LOWER(member))
            if retired is None and LOWER(member) in p.common_expressions_of(plugin):
                retired = p.deprecated_expressions("plugins", "_common").get(LOWER(member))
            if retired and LOWER(member) not in ivars:
                self.deprecated_use(where, self.deprecated_expression(f"{obj}.{member}", p.plugin_of[obj], retired))
                continue
            known = p.expressions_of(plugin) | p.common_expressions_of(plugin) | ivars
            if LOWER(member) not in known:
                # Platform.Speed is reached as Player.Platform.Speed, through the behavior's name on the object.
                owner = next((name for name, b in p.behaviors_of(obj).items()
                              if LOWER(member) in p.expressions_of(p.schema("behaviors", b))), None)
                hint = f"; it is an expression of a behavior: {obj}.{owner}.{member}" if owner \
                    else closest(member, known)
                self.err(f"{where}: {obj}.{member} is neither an expression nor an instance variable of {obj}{hint}")
            elif LOWER(member) not in ivars and sub is None:
                self.check_arguments(where, f"{m.group(1)}.{member}", [(plugin, None), (p.common, p.common_of(plugin))],
                                     member, text, m.end(2))
        for m in IDENT.finditer(text):
            name = m.group(0)
            if NUMBER.fullmatch(name):
                continue
            if text[:m.start()].rstrip().endswith(".") or text[m.end():].lstrip().startswith("."):
                continue
            if LOWER(name) in scope_lower:
                continue
            retired = p.deprecated_expressions("plugins", "system").get(LOWER(name))
            if retired:
                self.deprecated_use(where, self.deprecated_expression(name, "System", retired))
                continue
            if LOWER(name) in p.system_expressions:
                self.check_arguments(where, name, [(p.system, None)], name, text, m.end())
                continue
            if LOWER(name) in p.objects_lower and text[m.end():].lstrip().startswith("("):
                continue
            hint = closest(name, list(scope) + list(p.plugin_of))
            if LOWER(name) in p.objects_lower:
                hint = f"; {p.objects_lower[LOWER(name)]} is an object, write {p.objects_lower[LOWER(name)]}.<expression>"
            elif LOWER(name) in ("true", "false"):
                hint = ("; an expression has no true or false, a comparison gives 1 or 0. Test a boolean "
                        "variable with System compare-boolean-eventvar, inverted for false, and set it with System "
                        "set-boolean-eventvar; a boolean instance variable with is-boolean-instance-variable-set "
                        "and set-boolean-instvar")
            elif LOWER(name) in ("if", "then", "else"):
                hint = "; an expression chooses with condition ? a : b"
            elif text.strip() == name:
                hint += f"; a text value carries inner quotes: \"\\\"{name}\\\"\""
            self.err(f"{where}: identifier {name!r} is not a variable, parameter or system expression{hint}")

    def check_find(self, where: str, expr: str) -> None:
        """find or findcase with a one-character literal first and an expression second:
        a one-character text holds nothing longer, so the literal is the text searched for."""
        literals = [m.span() for m in STRING_LITERAL.finditer(expr)]
        for m in FIND_CALL.finditer(expr):
            if any(a < m.start() < b for a, b in literals) or len(unquote(m.group(2))) != 1:
                continue
            second = argument_at(expr, m.end())
            if not second or STRING_LITERAL.fullmatch(second):
                continue
            name, first = m.group(1), m.group(2)
            self.warn(f"{where}: {name}({first}, {second}) searches the one-character text {first} for {second}, "
                      f"so it is -1 unless {second} is {first} or empty; {name}(text, find) takes the text to search "
                      f"first: write {name}({second}, {first})")

    def is_boolean(self, expr: str, scope: dict) -> bool:
        """A comparison or logical expression, or a boolean variable: local, global or instance."""
        if top_level_operator(expr):
            return True
        m = re.fullmatch(r"\s*(?:(\w+)\s*\.\s*)?(\w+)\s*", expr)
        if not m:
            return False
        if m.group(1) is None:
            return (self.variable_named(m.group(2), scope) or {}).get("type") == "boolean"
        types = {LOWER(k): v for k, v in self.p.ivar_types_of(m.group(1)).items()}
        return types.get(LOWER(m.group(2))) == "boolean"

    def check_chooseindex(self, where: str, expr: str, scope: dict) -> None:
        """chooseindex(condition, a, b) as an if-else: it returns b when the condition is
        true, the reverse of the order it is read in. The examples write condition ? b : a."""
        for m in outside_literals(expr, CHOOSEINDEX_CALL.finditer(expr)):
            args = arguments_from(expr, m.end())
            if len(args) != 3 or not self.is_boolean(args[0], scope):
                continue
            test, if_false, if_true = args
            self.p.findings.style_finding(
                "choice", f"{where}: chooseindex({test}, {if_false}, {if_true}) is a two-way choice on a condition, "
                          f"which returns its last value when the condition is true; Construct's conditional "
                          f"operator reads in that order: write {test} ? {if_true} : {if_false}")

    def check_letter_table(self, where: str, expr: str) -> None:
        """mid("<letters>", find("<letters>", X) ..., 1): a value mapped through two text
        literals, a table or a cycle of letters."""
        for m in outside_literals(expr, MID_OF_LITERAL.finditer(expr)):
            position = argument_at(expr, m.end())
            for f in outside_literals(position, FIND_CALL.finditer(position)):
                looked_up = argument_at(position, f.end())
                letters = unquote(f.group(2))
                self.p.findings.style_finding(
                    "table", f"{where}: mid({m.group(1)}, {position}, ...) looks {looked_up} up through the letters "
                             f"{f.group(2)}, a table written as text; keep {looked_up} as a number 0 to "
                             f"{len(letters) - 1}: the next one in a cycle is ({looked_up} + 1) % {len(letters)}, "
                             f"as alien-battle steps (AnimationState + 1) % 3, and a value that maps to another "
                             f"is a Dictionary key or an Array index loaded from a project file")
                break

    def check_find_dispatch(self, tests: dict[str, list[tuple[int, str, str]]]) -> None:
        """Sibling events that test one text with find for different codes: a mini-language
        dispatched by substring. find matches any part of the text and ignores case, so the
        branch of "B" fires for "BU" too."""
        for subject, hits in tests.items():
            events = sorted({(n, w) for n, w, _ in hits})
            if len(events) < 2:
                continue
            codes = sorted({lit for _, _, lit in hits}, key=lambda s: (len(s), s))
            plain = [unquote(c).lower() for c in codes]
            overlap = next(((a, b) for i, a in enumerate(plain) for b in plain[i + 1:] if a and a in b), None)
            because = (f"\"{overlap[0]}\" also matches \"{overlap[1]}\", so a wrong branch runs" if overlap else
                       "a code that contains another runs that one's branch too")
            others = ", ".join(str(n) for n, _ in events[1:])
            self.p.findings.style_finding(
                "dispatch", f"{events[0][1]}: with events {others}, picks a branch by testing {subject} for the codes "
                            f"{', '.join(codes)} with find, which matches any part of the text and ignores case: "
                            f"{because}. Keep each fact in a field of its own, a text field such as kind compared "
                            f"with = (an instance variable, or a field of a JSON or Array project file) and numbers "
                            f"such as amount and times in number fields")

    def check_arguments(self, where: str, written: str, sources: list[tuple[dict, dict | None]], name: str,
                        text: str, end: int) -> None:
        """The arguments of an expression call against the parameters its schema lists.
        sources: (schema, the part of it that applies) in order; the first that has an
        expression of this name decides. The editor stops with "Incorrect parameters:
        'LocalStorage.ItemValue' does not accept 1 parameters"; LocalStorage.ItemValue
        reads the item the last Get item fetched and takes none."""
        for schema, part in sources:
            names = self.p.expression_names(schema)
            entry = next((e for e in (part or schema or {}).get("expressions", [])
                          if LOWER(names.get(e["id"], "")) == LOWER(name)), None)
            if entry is None:
                continue
            params = list(entry.get("params") or {})
            given = call_arguments(text, end)
            # isVariadicParameters: more may follow the listed ones, Mouse.X("HUD"), Array.At(x, y), max(a, b, c)
            more = entry.get("isVariadicParameters")
            if given < len(params) or given > len(params) and not more:
                usage = f"{written}({', '.join(params)}{', ...' if more else ''})" if params or more else written
                # The message is the one r495.2 gave for one argument too many; too few was not probed.
                self.err(f"{where}: {written} takes {'at least ' if more else ''}{len(params)} "
                         f"parameter{'' if len(params) == 1 else 's'} and is given {given}; the editor stops with "
                         f"\"Incorrect parameters: '{written}' does not accept {given} parameters\". Write {usage}")
            return

    @staticmethod
    def deprecated_expression(written: str, owner: str, retired: tuple[str, dict]) -> str:
        """The warning for an expression the editor has deprecated: it still opens the project."""
        _, entry = retired
        return (f"{written} is a deprecated expression of {owner}: {c3.DEPRECATED}"
                + (f"; the current expression of the same name is {entry['current']}" if entry.get("current") else ""))

    def project_property_wording(self, key: str) -> tuple[str, dict[str, str]]:
        """The Properties bar's name of a project property and of its options in the locale,
        so a finding names them as the user's editor shows them: fullscreenMode is 缩放模式 in zh-CN."""
        pack = self.p.rag / "data" / "c3-lang" / f"{self.p.locale}.json"
        if not pack.exists():
            return "", {}
        bar = c3.load(pack)["text"]["ui"]["bars"]["properties"]["project"]
        entry = bar.get(re.sub(r"(?<!^)(?=[A-Z])", "-", key).lower(), {})
        return entry.get("name", ""), entry.get("options", {})

    def builtin_eases(self) -> set[str]:
        """Ids of the built-in eases, the keys the editor's language pack labels."""
        if not self._eases:
            pack = self.p.rag / "data" / "c3-lang" / "en-US.json"
            if pack.exists():
                self._eases.update(c3.load(pack)["text"]["ui"]["bars"]["timeline"]["eases"])
        return self._eases

    def check_param(self, where: str, key: str, value, ptype: str, items: dict | None, obj: str, scope: dict,
                    writes: bool = False, stand_in: str | None = None) -> None:
        """writes: the parameter belongs to an action, which assigns the variable it names.
        stand_in: the object an "object" parameter of the same ACE names."""
        p = self.p
        if ptype == "cmp":
            if value not in (0, 1, 2, 3, 4, 5) or isinstance(value, bool):
                self.err(f"{where}: comparison {value!r} is not an integer 0-5 (=, ≠, <, ≤, >, ≥)")
        elif ptype == "boolean":
            if not isinstance(value, bool):
                self.err(f"{where}: {key} should be a JSON boolean, not {value!r}")
        elif ptype in ("combo", "combo-grouped"):
            if items and value not in items:
                self.err(f"{where}: {key}={value!r} is not one of {list(items)}{bare(value, items)}")
        elif ptype == "keyb":
            if not isinstance(value, int) or isinstance(value, bool):
                self.err(f"{where}: {key}={value!r} should be a key code, a JSON number such as 32 for Space or "
                         f"37-40 for the arrows; the editor stops with 'expected finite number'")
        elif ptype == "ease":
            eases = self.builtin_eases()
            if isinstance(value, str) and eases and value not in eases and not p.data.get("eases"):
                self.err(f"{where}: {key}={value!r} is not a built-in ease{closest(value, eases)}")
        elif ptype == "audiofile":
            # The editor looks the name up among the sound and music files, without the extension and
            # in any case, and refuses the project on any other value: "missing file '0'". The official
            # examples write the name as a string; a project saved by r495 writes {"path": "Name"}.
            stems = [Path(n["name"] if isinstance(n, dict) else n).stem
                     for kind in ("sound", "music")
                     for n, _ in folder_items(p.data.get("rootFileFolders", {}).get(kind, {}))]
            name = value["path"] if isinstance(value, dict) else value
            name = unquote(name) if is_literal(name) else name
            if not isinstance(name, str) or LOWER(name) not in {LOWER(s) for s in stems}:
                near = closest(Path(name).stem, stems) if isinstance(name, str) else ""
                shown = ", ".join(stems[:8]) + (f" and {len(stems) - 8} more" if len(stems) > 8 else "")
                listed = f"; the project has {shown}" if stems else "; the project has none"
                self.err(f"{where}: {key}={value!r} is not a sound or music file of the project; the editor stops "
                         f"with \"missing file {name!r}\". Write the file's name without its extension"
                         + (near or listed))
        elif ptype in ("tilemapbrush", "function", "model3d", "objecteffect"):
            return
        elif ptype == "template":
            # a name in an expression, "\"\"" for none; written "" the editor does not open the project
            self.check_expr(f"{where} {key}", value, scope, obj, stand_in)
        elif ptype == "object":
            if value not in p.plugin_of or value == "System":
                self.err(f"{where}: {key}={value!r} is not an object type or family"
                         + (bare(value, p.plugin_of) or closest(value, p.plugin_of)))
        elif ptype in ("instancevar", "instancevarbool"):
            # shared ACEs name one of the object's own variables
            ivars = p.ivar_types_of(obj)
            if value not in ivars:
                self.err(f"{where}: {obj} has no instance variable {value!r}{bare(value, ivars) or closest(value, ivars)}")
            elif ptype == "instancevarbool" and ivars[value] != "boolean":
                self.err(f"{where}: instance variable {value!r} is not a boolean")
        elif ptype == "objinstancevar":
            target, ivar = (value.get("objectClass", obj), value.get("name")) if isinstance(value, dict) else (obj, value)
            if ivar not in p.ivars_of(target):
                self.err(f"{where}: {target} has no instance variable {ivar!r}{closest(ivar or '', p.ivars_of(target))}")
        elif ptype in ("eventvar", "eventvarbool", "eventvarany"):
            var = self.variable_named(value, scope)
            if var is None:
                self.err(f"{where}: variable {value!r} is not in scope{bare(value, scope) or closest(value, scope)}")
            elif ptype == "eventvarbool" and var["type"] != "boolean":
                self.err(f"{where}: variable {value!r} is not a boolean")
            elif writes and var.get("isConstant") and var["name"] != value and value in self.variable_names:
                kind = "global" if id(var) in self.global_ids else "local"
                self.err(f"{where}: {value} is read as the {kind} constant {var['name']}: the editor finds a "
                         f"variable by its name without case, so the action writes {var['name']} and the editor "
                         f"stops with 'event variable {value} is constant'. Rename the variable {value}, here and "
                         f"wherever it is declared and used, so that it differs from {var['name']} by more than "
                         f"case, for example {value}{SHADOW_SUFFIX.get(var.get('type'), 'Value')}")
            elif writes and var.get("isConstant"):
                self.err(f"{where}: {value} is a constant and an action cannot change it; "
                         f"the editor stops with 'event variable {value} is constant'")
        elif ptype == "layer":
            if is_literal(value):
                if unquote(value) not in self.layers:
                    self.err(f"{where}: no layer named {unquote(value)!r} in any layout")
            else:
                self.check_expr(f"{where} {key}", value, scope, obj, stand_in)
        elif ptype == "layout":
            if value not in self.layouts:
                self.err(f"{where}: no layout named {value!r}{bare(value, self.layouts) or closest(value, self.layouts)}")
        elif ptype == "groupname":
            if is_literal(value) and unquote(value) not in self.group_titles:
                self.err(f"{where}: no group titled {unquote(value)!r}")
        elif ptype == "animation":
            anims = p.animations_of(obj)
            if is_literal(value):
                if anims is not None and LOWER(unquote(value)) not in anims:
                    self.err(f"{where}: {obj} has no animation {unquote(value)!r}")
            else:
                self.check_expr(f"{where} {key}", value, scope, obj, stand_in)
        elif ptype == "projectfile":
            name = value["path"] if isinstance(value, dict) else value
            if not (p.root / "files" / name).exists() and not list((p.root / "files").rglob(Path(name).name)):
                self.err(f"{where}: project file {name!r} is not in files/")
        elif ptype == "timeline":
            if value not in [n for n, _ in folder_items(p.data.get("timelines", {}))]:
                self.err(f"{where}: no timeline named {value!r}")
        elif ptype == "flowchart":
            if value not in [n for n, _ in folder_items(p.data.get("flowcharts", {}))]:
                self.err(f"{where}: no flowchart named {value!r}")
        else:
            if not isinstance(value, str):
                self.err(f"{where}: {key} should be an expression string, not {value!r}")
            else:
                self.check_expr(f"{where} {key}", value, scope, obj, stand_in)

    # --- event sheets: conditions and actions -------------------------------------------------
    def ace_hint(self, kind: str, ace: dict) -> str:
        """Where an id the schema does not have under this object does exist: on one
        of its behaviors, on the object itself, as the other kind, or under a near
        spelling (the script name and the list name are tried as well as the id)."""
        p = self.p
        obj, ace_id = ace["objectClass"], ace["id"]
        if "behaviorType" not in ace:
            for name, behavior_id in p.behaviors_of(obj).items():
                s = p.schema("behaviors", behavior_id)
                if s and any(it["id"] == ace_id for it in s.get(kind, [])):
                    return f"; it belongs to the behavior {name}: add \"behaviorType\": \"{name}\""
        elif any(it["id"] == ace_id for s in p.ace_sources({"objectClass": obj}) for it in s.get(kind, [])):
            return "; it belongs to the object itself: remove \"behaviorType\""
        sources = p.ace_sources(ace)
        other = "actions" if kind == "conditions" else "conditions"
        found = next((it for s in sources for it in s.get(other, []) if it["id"] == ace_id), None)
        if found:
            # where to move it: told only "not its actions", a small model rewrote the loop away (2026-10-04)
            where = (f": move it into the \"conditions\" of this event" + (
                     ", or of a sub-event whose actions are the ones to repeat; a loop is a condition, and the actions "
                     "of its event run once per pass" if found.get("isLooping") else "")
                     if kind == "actions" else ": move it into the \"actions\" of this event")
            return f"; {ace_id} is one of its {other}, not its {kind}{where}"
        spellings = {}
        for s in sources:
            for it in s.get(kind, []):
                for text in (it["id"], it.get("scriptName", ""), it.get("list-name", "")):
                    spellings.setdefault(squash(text), it["id"])
        if squash(ace_id) in spellings:
            return f"; the id is {spellings[squash(ace_id)]!r}"
        near = difflib.get_close_matches(squash(ace_id), list(spellings), n=4, cutoff=0.6)
        ids = list(dict.fromkeys(spellings[n] for n in near))[:3]
        return "; closest: " + ", ".join(ids) if ids else ""

    def check_ace(self, kind: str, ace: dict, scope: dict, where: str) -> None:
        p = self.p
        obj = ace.get("objectClass")
        ace_id = ace.get("id")
        params = ace.get("parameters", {})
        where = f"{where} {obj}:{ace_id}"
        if obj is None or ace_id is None:
            self.err(f"{where}: a {kind[:-1]} needs \"objectClass\" and \"id\"")
            return
        if obj not in p.plugin_of:
            self.err(f"{where}: unknown object {obj}{closest(obj, p.plugin_of)}")
            return
        if "behaviorType" in ace and ace["behaviorType"] not in p.behaviors_of(obj):
            self.err(f"{where}: {obj} has no behavior {ace['behaviorType']}"
                     f"{closest(ace['behaviorType'], p.behaviors_of(obj))}; "
                     f"\"behaviorType\" is the name the behavior has on the object, not its id")
            return
        if not p.ace_sources(ace):
            return      # no schema for this addon: warned about once, nothing to check against
        entry = p.ace_entry(kind, ace)
        retired = p.deprecated_entry(kind, ace)
        if retired:
            # The editor opens a project that uses it, so this is no error, but a new event should not.
            owner, dep = retired
            owner = "System" if owner == "system" else owner
            self.deprecated_use(where, f"{kind[:-1]} {ace_id} of {owner} is deprecated: {c3.DEPRECATED}"
                                + ("" if entry else ", and its parameters are not checked")
                                + (f"; the current {kind[:-1]} of the same name is {dep['current']}"
                                   if dep.get("current") else ""))
            if entry is None:
                return
        if entry is None:
            owner = p.behaviors_of(obj)[ace["behaviorType"]] if "behaviorType" in ace else p.plugin_of[obj]
            shared = "behaviorType" not in ace and obj != "System" and \
                any(it["id"] == ace_id for it in (p.common or {}).get(kind, []))
            self.err(f"{where}: {owner} has no {kind[:-1]} {ace_id}"
                     + (f": it is in plugins/_common.json, but the editor gives it only to plugins that ask for "
                        f"it, not to {owner}, and does not open the project" if shared
                        else "" if "behaviorType" in ace or obj == "System" else " (not in _common either)")
                     + self.ace_hint(kind, ace))
            return
        schema_params = entry.get("params") or {}
        if not isinstance(params, dict):
            self.err(f"{where}: \"parameters\" should be an object keyed by parameter id: "
                     f"{', '.join(schema_params) or 'none here'}")
            return
        for k in params:
            if k not in schema_params:
                self.err(f"{where}: unknown parameter {k}; the parameters are: {', '.join(schema_params) or 'none'}")
        for k in schema_params:
            if k not in params:
                if not self.review:     # the editor saves an ACE so and fills it on open
                    self.warn(f"{where}: parameter {k} is omitted; the editor fills its default")
        named = [v for k, v in params.items() if schema_params.get(k, {}).get("type") == "object"]
        stand_in = named[0] if len(named) == 1 and named[0] in p.plugin_of else None
        for k, v in params.items():
            if k not in schema_params:
                continue
            self.check_param(where, k, v, schema_params[k]["type"], schema_params[k].get("items"), obj, scope,
                             writes=kind == "actions", stand_in=stand_in)
        if kind == "actions" and ace_id in EFFECT_ACTIONS:
            self.check_effect_name(where, obj, ace_id, params)
        if kind == "actions" and ace_id in SPRITE_FONT_TEXT and isinstance(params.get("text"), str) \
                and p.plugin_of[obj].lower() == "spritefont2":
            members = p.families[obj].get("members", []) if obj in p.families else [obj]
            sets = [self.font_sets[m] for m in members if m in self.font_sets]
            if sets:
                charset, bbcode = set().union(*(s for s, _ in sets)), any(b for _, b in sets)
                for literal in joined_literals(params["text"]):
                    self.check_sprite_font_text(f"{where} text", obj, literal, charset, bbcode)
        if ace_id == "create-object" and obj == "System":
            self.created.add(params.get("object-to-create"))
        if ace_id == "set-eventvar-value" and \
                (self.variable_named(params.get("variable"), scope) or {}).get("type") == "boolean":
            self.err(f"{where}: Set value on boolean {params['variable']}; use Set boolean")

    def check_effect_name(self, where: str, obj: str, ace_id: str, params: dict) -> None:
        """An effect named in a literal that the object, the layer or the layouts do not carry: the action runs
        and changes nothing. An object reaches its families' effects. A family's action accepts its members'
        effects, and a layer's the effects of that layer in any layout: whether the runtime resolves those
        was not probed."""
        p = self.p
        name = params.get("effect")
        if not is_literal(name):
            return
        name = unquote(name)
        if ace_id.startswith("set-layer-"):
            layer = params.get("layer")
            if not is_literal(layer) or unquote(layer) not in self.layer_effects:
                return      # a layer by number or expression, or one check_param already says is missing
            names, add = self.layer_effects[unquote(layer)], "the layer's Effects"
            missing, held = f"the layer {unquote(layer)} has no effect named {name!r}", "it has"
        elif ace_id.startswith("set-layout-"):
            names, add = self.layout_effects, "the layout's Effects"
            missing, held = f"no layout has an effect named {name!r}", "the layouts have"
        else:
            holders = [obj] + p.families_of(obj) + (p.families[obj].get("members", []) if obj in p.families else [])
            names = set().union(*(effect_names(p.types.get(h) or p.families.get(h) or {}) for h in holders))
            missing, held, add = f"{obj} has no effect named {name!r}", "it has", f"{obj}'s Effects"
        if LOWER(name) not in {LOWER(n) for n in names}:
            has = f"{held} {', '.join(sorted(names))}" if names else f"{held} none"
            self.warn(f"{where}: {missing} ({has}), so the action runs and changes nothing; add the effect in "
                      f"{add}, or name one it has")

    def check_structure(self, ev: dict, where: str, above: Holder | None, previous: dict | None) -> Holder | None:
        """Where a condition may stand. These are the editor's own rules, the first
        three applied as it opens the project and the fourth before every preview:
        an event branch, from the top-level event down to a leaf, holds one trigger,
        and a function or a custom action counts as one (only an OR block lists
        several); a trigger, a loop and a condition the schema marks
        isInvertible: false cannot be inverted; a function cannot be an OR block;
        Else is the first condition of an event that directly follows a plain event.

        above is the holder of the branch's trigger so far, previous the sibling
        before this event with comments skipped. Returns the holder for the
        sub-events: above, or this event if it brings the trigger."""
        p = self.p
        conds = [c for c in ev.get("conditions", []) if "id" in c]
        entries = [p.ace_entry("conditions", c) or {} for c in conds]
        is_function = ev.get("eventType") != "block"
        triggers = [c for c, e in zip(conds, entries) if e.get("isTrigger")]
        if is_function and ev.get("isOrBlock"):
            self.err(f"{where}: a function or custom action cannot be an OR block")
        if triggers and (above or is_function):
            holder = above.text if above else "a function or custom action, which counts as a trigger"
            self.err(f"{where}: {describe(triggers[0])} is a trigger inside {holder}; the editor stops with 'cannot "
                     f"add another trigger to event branch'. Move it to an event of its own, outside, and test the "
                     f"rest in sub-events")
        elif len(triggers) > 1 and not ev.get("isOrBlock"):
            self.err(f"{where}: {' and '.join(describe(c) for c in triggers)} are two triggers in one event; the "
                     f"editor stops with 'cannot add another trigger to event branch'. One event per trigger, or an "
                     f"OR block")
        for c, e in zip(conds, entries):
            # Both are mended in the one condition, so they name it, as check_ace does.
            its = f"{where} condition {next(i for i, x in enumerate(ev['conditions'], 1) if x is c)}"
            if c.get("isInverted") and (e.get("isTrigger") or e.get("isLooping") or e.get("isInvertible") is False):
                kind = "a trigger" if e.get("isTrigger") else "a loop" if e.get("isLooping") else "this condition"
                self.err(f"{its}: {describe(c)} is inverted, and {kind} cannot be; "
                         f"the editor stops with 'condition not invertible'")
            # Trigger once, Every X seconds: the editor keeps them out of a triggered branch, where they
            # are tested only in the tick the trigger fires. Else has its own rule below.
            if e.get("isCompatibleWithTriggers") is False and c["id"] != "else" \
                    and (triggers or (above and above.fires)):
                self.warn(f"{its}: {describe(c)} is in a branch run by the trigger "
                          f"{describe(triggers[0]) if triggers else above.name}; the editor does not offer it there, "
                          f"since it is only tested when the trigger fires")
        for i, c in enumerate(conds):
            if c.get("objectClass") != "System" or c["id"] != "else":
                continue
            problem = None
            before = [b for b in (previous or {}).get("conditions", []) if "id" in b]
            flags = [p.ace_entry("conditions", b) or {} for b in before]
            if ev.get("isOrBlock") or is_function:
                problem = "its event is " + ("an OR block" if ev.get("isOrBlock") else "a function")
            elif triggers:
                problem = f"its event has the trigger {describe(triggers[0])}"
            elif i != 0:
                problem = "it is not the first condition of its event"
            elif previous is None or previous.get("eventType") != "block":
                problem = "it is the first event of its list" if previous is None else \
                    f"it follows a {previous.get('eventType')}, and only comments may stand between it and the " \
                    f"event it answers"
            elif len(before) == 1 and describe(before[0]) == "System:else":
                problem = "it follows an event whose only condition is Else"
            elif any(f.get("isTrigger") for f in flags):
                problem = "it follows a triggered event"
            elif any(f.get("isLooping") for f in flags):
                problem = "it follows a loop"
            if problem:
                self.err(f"{where}: Else cannot stand here, {problem}; the editor refuses to preview ('An Else "
                         f"condition cannot be placed here'). Use a second event with the inverted condition")
        if above:
            return above
        if is_function:
            kind = "function" if ev.get("eventType") == "function-block" else "custom action"
            return Holder(f"the {kind} {ev.get('functionName') or ev.get('aceName')}", False)
        return Holder(describe(triggers[0]), True) if triggers else None

    def check_variable(self, var: dict, where: str, what: str) -> None:
        """An event variable or a function parameter: its type is one of three and its
        initialValue is text, as the editor writes it. The editor reads a boolean by
        comparing the text to "true", in the editor and again on export, so a JSON
        true or a "True" reads as false; a function parameter may also carry a
        number, anything else stops the load with 'invalid type of initialValue'."""
        name, vtype, value = var.get("name"), var.get("type"), var.get("initialValue")
        w = f"{where}: {what} {name}"
        if isinstance(name, str) and LOWER(name) in self.p.system_expression_names:
            # A local mid passed as Functions.measure(mid) is read as the text function mid(), and
            # a parameter round in "第 " & round & " 轮" as round() with no argument; the editor
            # refuses the project either way (r504, 2026-10-02). None of the 2697 variables and
            # 1028 function parameters of the official examples shares a system expression's name.
            said = ("\"Invalid expressions ... parameter 0 does not take 'string'\" for a local mid"
                    if what == "variable" else "\"'round' does not accept 0 parameters\" for a parameter round")
            self.err(f"{w}: the name is that of the system expression {LOWER(name)}, which wins inside an "
                     f"expression: {name} there is read as {LOWER(name)}(), not as the {what}, and the editor "
                     f"refuses the project ({said}); rename it, for example {name}Value, where it is declared "
                     f"and where it is used")
        if vtype not in VARIABLE_TYPES:
            self.err(f"{w}: type {vtype!r} is not number, string or boolean")
            return
        if what == "parameter" and isinstance(value, (int, float)) and not isinstance(value, bool):
            value = str(value)
        if not isinstance(value, str):
            if vtype == "boolean":
                self.err(f"{w}: initialValue should be the text \"true\" or \"false\", not {value!r}; "
                         f"the editor compares the text to \"true\", so a JSON boolean reads as false")
            else:
                self.err(f"{w}: initialValue should be text, {json.dumps(str(value if value is not None else ''))}, "
                         f"not {value!r}; the editor stores every initial value as text")
        elif vtype == "boolean" and value not in ("true", "false"):
            self.err(f"{w}: initialValue {value!r} should be \"true\" or \"false\", lowercase; "
                     f"the editor compares the text to \"true\" and reads anything else as false")
        elif vtype == "number":
            try:
                finite = math.isfinite(float(value))
            except ValueError:
                finite = False
            if not finite:
                self.err(f"{w}: initialValue {value!r} is not a number; the editor reads it as 0")

    def check_shadow(self, var: dict, other: dict, where: str, visible: str) -> None:
        """A local or parameter named like a global, compared without case. The editor keeps
        both names, and in the local's scope the global's name refers to the local. A text
        count beside a number COUNT makes COUNT - 1 there "Type mismatch: - does not work with
        'string' and 'number'", which stops the open. With a local of the same type under
        another case the project opens, and the global's spelling there reads the local. No
        official example declares a local named like a variable in scope. visible: where the
        local is visible."""
        name, outer = var["name"], other["name"]
        if other.get("type") != var.get("type"):
            self.err(f"{where}: {var.get('type')} {name} has the name of the {other.get('type')} variable {outer} "
                     f"once case is ignored, and it hides it here and in the sub-events; an expression that means "
                     f"{outer} reads {name}, and the editor refuses the project with \"Type mismatch\" "
                     f"(\"- does not work with 'string' and 'number'\" for a text local beside a number); rename it, "
                     f"for example {name}{SHADOW_SUFFIX.get(var.get('type'), 'Local')}")
        elif name != outer:
            self.warn(f"{where}: {name} has the name of the global {outer} once case is ignored, and hides it in "
                      f"{visible}. There, an expression or action that names {outer} refers to {name}, which the "
                      f"editor accepts. If they are two values, rename {name} and its uses, for example "
                      f"{name}{SHADOW_SUFFIX.get(var.get('type'), 'Value')}")

    @staticmethod
    def variable_named(name, scope: dict) -> dict | None:
        """The variable a name refers to in scope, compared without case; enter keeps the
        scope as the editor binds the names."""
        if not isinstance(name, str):
            return None
        return next((v for k, v in scope.items() if LOWER(k) == LOWER(name)), None)

    def enter(self, scope: dict, var: dict, outer: dict, where: str, holder: str) -> None:
        """Bring a local or a function parameter into scope as the editor binds its name, and
        check the name against the variables in scope, compared without case. holder: the
        event that holds its list, "group Movement", "event 5" or "function launch"; outer:
        the scope as it was before this list.

        A local beside a global keeps its name and hides the global in its scope. As it opens
        the project, the editor renames a local or parameter whose name matches another of its
        list or of a scope that holds it: the one that comes later in the sheet gets a number
        (speed to speed2), and both names then refer to the other one wherever it is in scope.
        Probed in the r495.2 and r504 editors (docs/decisions/checker-editor-load-rules.md)."""
        name = var.get("name")
        if not isinstance(name, str):
            return
        visible = holder if variable_kind(var) == "parameter" or holder.startswith("group ") \
            else f"the sub-events of {holder}"
        self.declared[id(var)] = (where, f"the {variable_kind(var)} {name} of {holder}", visible)
        same = next((v for k, v in scope.items() if LOWER(k) == LOWER(name) and outer.get(k) is not v), None)
        if same is not None:
            self.renamed.add(id(var))
            self.check_declared_once(var, same, where, "declared above it in the same list of events",
                                     free_name(name, scope))
            return
        other = self.variable_named(name, outer)
        if other is not None and id(other) not in self.renamed and id(other) not in self.global_ids \
                and self.load_order.get(id(var), 0) > self.load_order.get(id(other), 0):
            self.renamed.add(id(var))
            self.check_renamed(var, other, where, free_name(name, scope))
            return
        for k in [k for k in scope if scope[k] is other]:
            del scope[k]
        scope[name] = var
        if other is None or id(other) in self.renamed:
            return
        if id(other) in self.global_ids:
            self.check_shadow(var, other, where, visible)
        else:
            self.renamed.add(id(other))
            self.check_outer_renamed(other, var, free_name(other["name"], scope))

    def check_renamed(self, var: dict, other: dict, where: str, new: str) -> None:
        """A local or parameter declared after a local or parameter of its name whose scope
        holds it: the editor renames it, and its uses refer to the other one."""
        name, desc = var["name"], self.declared[id(other)][1]
        kept = other["name"] if other["name"] != name else f"that {variable_kind(other)}"
        lost = ", and the value a call passes for it is lost" if variable_kind(var) == "parameter" else ""
        self.err(f"{where}: {name} has the name of {desc}{case_aside(name, other['name'])}, and {kept} is in "
                 f"scope where {name} is declared, before it. The editor renames {name} to {new} when it opens "
                 f"the project. Every use of {name} then refers to {kept}{lost}. Rename {name} and its uses, for "
                 f"example {name}{SHADOW_SUFFIX.get(var.get('type'), 'Value')}")

    def check_outer_renamed(self, var: dict, inner: dict, new: str) -> None:
        """An outer local declared after an inner local or parameter of its name: the editor
        renames the outer one, so its name refers to the inner one inside the inner one's
        scope and to nothing elsewhere."""
        where = self.declared[id(var)][0]
        name = var["name"]
        _, desc, visible = self.declared[id(inner)]
        kept = inner["name"] if inner["name"] != name else f"that {variable_kind(inner)}"
        self.err(f"{where}: {name} has the name of {desc}{case_aside(name, inner['name'])}, which is declared "
                 f"before it, inside the scope of {name}. The editor renames {name} to {new} when it opens the "
                 f"project. In {visible}, {name} then refers to {kept}, and elsewhere an expression that names "
                 f"{name} stops the open with \"Unknown expression '{name}': This is not a system expression or "
                 f"variable name in this scope\". Rename {name} and its uses, for example "
                 f"{name}{SHADOW_SUFFIX.get(var.get('type'), 'Value')}")

    def check_declared_once(self, var: dict, earlier: dict, where: str, first: str, new: str = "") -> None:
        """Two variables of one list whose names match without case, which the editor's own
        dialogs never allow. A file that has them opens, and every use of either name refers
        to the first. The editor renames the second local as it opens the project, to new:
        STEP to STEP2. A second global keeps its name, and only a script reads it. first:
        where the first one is, as a phrase."""
        name, other = var["name"], earlier["name"]
        if other == name:
            renames = f" The editor renames this one to {new} when it opens the project." if new else ""
            self.err(f"{where}: {name} is declared again; the first {name} is {first}.{renames} Every use of the "
                     f"name refers to the first, so this declaration is never read or written. Delete it"
                     + ("; a global is visible from every sheet" if id(var) in self.global_ids else ""))
            return
        renames = f" The editor renames {name} to {new} when it opens the project." if new else ""
        constant = (f"; an action that writes {name} stops the editor with \"event variable {name} is constant\""
                    if earlier.get("isConstant") else "")
        self.err(f"{where}: {name} has the name of {other}, {first}, once case is ignored.{renames} Every use of "
                 f"either name refers to {other}, so {name} is never read or written{constant}. Rename it and its "
                 f"uses, for example {name}{SHADOW_SUFFIX.get(var.get('type'), 'Value')}")

    def check_parameter_renamed(self, param: dict, last: dict, where: str, new: str) -> None:
        """Two parameters of one function whose names match without case. The editor renames
        every one but the last as it opens the project, amount to amount2 and Amount to
        Amount3 before a third AMOUNT, and every use of the name refers to the last."""
        name, kept = param["name"], last["name"]
        said = (f"{name} is declared again by a later parameter of the same function" if name == kept else
                f"{name} has the name of {kept}, a later parameter of the same function, once case is ignored")
        self.err(f"{where}: {said}. The editor renames {name} to {new} when it opens the project. Every use of "
                 f"the name refers to {'the later one' if name == kept else kept}, so {name} is never read or "
                 f"written, and the value a call passes for it is lost. Rename it and its uses, for example "
                 f"{name}{SHADOW_SUFFIX.get(param.get('type'), 'Value')}")

    def check_callable_name(self, ev: dict, kind: str, name: str, where: str) -> None:
        """Functions share one namespace, and the custom actions of an object another, compared
        without case. As it opens the project, the editor renames the one that comes later, a
        number added (Beep to Beep2), and a call by either name runs the first."""
        owner = "" if kind == "function" else str(ev.get("objectClass"))
        key = (owner, LOWER(name))
        first = self.callables.setdefault(key, (name, where))
        if first[0] == name:
            return
        of = f"{owner}." if owner else ""
        new = free_name(name, [n for (o, _), (n, _) in self.callables.items() if o == owner])
        self.err(f"{where}: {kind} {of}{name} has the name of the {kind} {of}{first[0]} at {first[1]} once case is "
                 f"ignored. The editor renames it to {new} when it opens the project, and a call to {name} runs "
                 f"{first[0]}, so this {kind} never runs. Rename it and its calls so that the two names differ by "
                 f"more than case")

    def note_signal(self, ace: dict, where: str) -> None:
        if ace.get("objectClass") != "System" or ace.get("id") not in ("signal", "wait-for-signal", "on-signal"):
            return
        tag = (ace.get("parameters") or {}).get("tag")
        if ace["id"] != "signal":
            if is_literal(tag):
                self.awaited.append((unquote(tag).lower(), ace["id"], where))
        elif self.signalled is not None:
            self.signalled = self.signalled | {unquote(tag).lower()} if is_literal(tag) else None

    def check_script(self, script, scope: dict, where: str) -> None:
        """A script reads an event's locals and parameters as localVars.name; a bare name
        is a ReferenceError when the event runs. Signals it raises count as Signal actions."""
        text = script_text(script)
        for m in JS_SIGNAL.finditer(text):
            if self.signalled is not None:
                self.signalled = self.signalled | {m.group(2).lower()} if m.group(1) else None
        code = JS_SKIPPED.sub('""', text)
        for name, var in scope.items():
            if id(var) not in self.global_ids and isinstance(name, str) and bare_name_in(code, name):
                self.warn(f"{where}: the script reads {name} as a bare name, which it does not know; an event's "
                          f"local or parameter is localVars.{name} in a script")

    def reads_input(self, ev: dict) -> bool:
        return any(self.p.plugin_of.get(c.get("objectClass"), "").lower() in INPUT_PLUGINS
                   for c in ev.get("conditions", []))

    def check_gesture(self, action: dict, by_input: bool | None, where: str) -> None:
        """by_input: whether the action's event or one above it tests touch, mouse, keyboard or a form
        control; None in a function or custom action, which an input trigger may call."""
        page = GESTURE_ACTIONS.get((self.p.plugin_of.get(action.get("objectClass"), "").lower(), action.get("id")))
        if page and by_input is False:
            self.warn(f"{where}: {describe(action)} runs with no touch, click or key in its event or above it, "
                      f"and the browser refuses it there; move it into an event with a trigger such as Touch On "
                      f"tap, Mouse On click or Keyboard On key pressed (manual: plugin-reference/{page}.md)")

    def pacing(self, ev: dict) -> set[str]:
        """What keeps the event from running every tick: "trigger", "every" for Every X seconds, "once" for
        Trigger once. A condition of an addon without a schema is a trigger when its id starts with on-."""
        kinds = set()
        for c in ev.get("conditions", []):
            entry = self.p.ace_entry("conditions", c)
            if entry.get("isTrigger") if entry else str(c.get("id", "")).startswith("on-"):
                kinds.add("trigger")
            elif (self.p.plugin_of.get(c.get("objectClass"), "").lower(), c.get("id")) in PACING:
                kinds.add("once" if c.get("id") == "trigger-once-while-true" else "every")
        return kinds

    def paces(self, ev: dict) -> bool:
        """Whether a condition of the event keeps it from running every tick."""
        return bool(self.pacing(ev))

    def is_solid(self, obj) -> bool:
        """A type with the Solid behavior, or a family that is one or has one among its members."""
        p = self.p
        names = [obj] + (p.families[obj].get("members", []) if obj in p.families else [])
        return any(b.lower() == "solid" for n in names if n in p.plugin_of for b in p.behaviors_of(n).values())

    def check_pathfinding(self, action: dict, where: str, found: dict[str, str], paced: bool | None) -> None:
        """found: object -> the name of the Pathfinding behavior a Find path earlier in the same actions
        started on it, cleared by Wait for previous actions to complete. paced: as check_block's."""
        p = self.p
        obj, ace_id, params = action.get("objectClass"), action.get("id"), action.get("parameters", {})
        if obj not in p.plugin_of or not isinstance(params, dict):
            return      # a comment, a script, a function call or a custom action
        behavior = p.behaviors_of(obj).get(action.get("behaviorType", ""), "").lower()
        if obj == "System" and ace_id == "wait-for-previous-actions":
            found.clear()
        made = params.get("object-to-create") if (obj, ace_id) == ("System", "create-object") \
            else params.get("object") if ace_id == "spawn-another-object" else None
        if (isinstance(made, str) and self.is_solid(made)) \
                or (ace_id in SOLID_CHANGES and not behavior and self.is_solid(obj)) \
                or (behavior == "solid" and ace_id == "set-enabled"):
            self.solid_changes.append(where)
        if behavior == "pathfinding" and ace_id in REGENERATE:
            self.regenerated = True
        if behavior == "pathfinding" and ace_id == "find-path":
            found[obj] = action["behaviorType"]
            if paced is False:
                # A kind of its own, so that edit_sheet.py refuses it in an event a plan creates.
                every = json.dumps({"id": "every-x-seconds", "objectClass": "System",
                                    "parameters": {"interval-seconds": "0.5"}})
                self.p.findings.style_finding(
                    "pathfinding", f"{where}: Find path runs every tick; move it into the trigger that sets the "
                                   f"target, such as Touch On tap or Mouse On click, or add System Every 0.5 seconds "
                                   f"to its event, {every}. With no trigger, Every X seconds or Trigger once in its "
                                   f"event or above it, the manual warns that pathfinding every tick takes extremely "
                                   f"high CPU and delays every other object's path "
                                   f"(manual: behavior-reference/pathfinding.md)")
            return
        early = obj in found and (behavior == "pathfinding" and ace_id == "move-along-path"
                                  or behavior == "moveto" and ace_id == "move-along-pathfinding-path")
        for m in PATH_NODES.finditer(" ".join(v for v in params.values() if isinstance(v, str))):
            owner = obj if LOWER(m.group(1)) == "self" else p.objects_lower.get(LOWER(m.group(1)))
            early |= owner in found and LOWER(m.group(2)) == LOWER(found[owner])
        if early:
            self.warn(f"{where}: {describe(action)} reads the path a Find path above it in the same actions has only "
                      f"started: the path is there after On path found, and until then this reads the previous "
                      f"one. Put System Wait for previous actions to complete between them, or move this into "
                      f"an On path found event (manual: behavior-reference/pathfinding.md)")

    def behavior_of(self, ace: dict) -> str:
        """The behavior id an ACE belongs to, lower case, or "" for the object's own."""
        obj = ace.get("objectClass")
        return self.p.behaviors_of(obj).get(ace.get("behaviorType", ""), "").lower() if obj in self.p.plugin_of else ""

    def check_held_control(self, action: dict, where: str, held: tuple, paced: bool | None) -> None:
        """Simulate control of a movement held down, under a trigger: the control holds for the one tick the
        trigger fires. held: the conditions of the event and of those above it."""
        controls = HELD_CONTROLS.get(self.behavior_of(action), ())
        control = params_of(action).get("control")
        if action.get("id") != "simulate-control" or paced is None or (controls is not None and control not in controls):
            return
        trigger = next((c for c in held if (self.p.ace_entry("conditions", c) or {}).get("isTrigger")), None)
        if trigger is None:
            return
        plugin = self.p.plugin_of.get(trigger.get("objectClass"), "").lower()
        hold = HOLDING.get((plugin, trigger.get("id")))
        if hold:
            kept = {k: v for k, v in params_of(trigger).items() if k in hold[1]}
            instead = {"id": hold[0], "objectClass": trigger["objectClass"], **({"parameters": kept} if kept else {})}
            fix = f"Put this action in an event whose condition is {trigger['objectClass']} {hold[0]} in place of the " \
                  f"trigger, {json.dumps(instead, ensure_ascii=False)}"
        else:
            example = json.dumps({"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 87}})
            fix = f"Put this action in an event whose condition holds while the input is held, such as {example} " \
                  f"with the key's code"
        self.p.findings.style_finding(
            "control", f"{where}: Simulate control {control} runs only in the tick that {describe(trigger)} fires, "
                       f"so {action.get('objectClass')} moves for one tick and stops. {fix} "
                       f"(manual: behavior-reference.md \"Custom controls\")")

    @staticmethod
    def words_of(aces: list) -> set[str]:
        """Every word in the parameters of these conditions or actions, lower case: the variables, objects and
        expressions they read."""
        words = set()
        for ace in aces:
            for value in params_of(ace).values():
                if isinstance(value, str):
                    words |= {w.lower() for w in IDENT.findall(value)}
        return words

    def check_timer_restart(self, action: dict, where: str, line: tuple, held: tuple, paced: bool | None) -> None:
        """Start timer in an event that runs every tick, whose conditions test values that the actions of its
        branch leave alone: each tick starts the timer over, and On timer never fires. A cooldown tests Is timer
        running, and an overlap, a key held or a position changes as the game plays, so those are left alone.
        line: the event and those above it, held: their conditions."""
        if paced is not False or action.get("id") != "start-timer" or self.behavior_of(action) != "timer":
            return
        for c in held:
            value_test = (c.get("objectClass"), c.get("id")) in VALUE_TESTS or c.get("id") in INSTANCE_VALUE_TESTS
            moving = any(m.group(2).lower() != "count" for value in params_of(c).values() if isinstance(value, str)
                         for m in OBJECT_EXPRESSION.finditer(value))
            if c.get("id") == "is-timer-running" or not value_test or moving:
                return
        actions = [a for ev in line for a in ev.get("actions", []) if isinstance(a, dict)]
        changed = {str(params_of(a).get(SETS[a["id"]], "")).lower() for a in actions if a.get("id") in SETS}
        changed |= {str(a.get("objectClass")).lower() for a in actions if a.get("id") == "destroy"}
        changed |= {str(self.made_by(a)).lower() for a in actions if self.made_by(a)}
        if changed & self.words_of(list(held)) or any("callFunction" in a or "customAction" in a for a in actions) \
                or any(a.get("objectClass") == "System" and a.get("id") in LEAVES for a in actions):
            return
        tag = params_of(action).get("tag", '""')
        once = json.dumps({"id": "trigger-once-while-true", "objectClass": "System"})
        self.p.findings.style_finding(
            "timer", f"{where}: Start timer {tag} runs every tick. No trigger, Every X seconds or Trigger once is in "
                     f"its event or above it, and its actions leave its conditions true. So the timer starts over each "
                     f"tick, and On timer {tag} never fires. Add System Trigger once as the last condition of its "
                     f"event, {once}, or start the timer in the event that begins the countdown")

    @staticmethod
    def flipped(a: dict) -> str | None:
        """The variable an action flips between two values, as TOGGLES and FLIPS name them; None for any other
        action. An instance variable is read as Self.x or through its object's name, an event variable bare."""
        params = params_of(a)
        if a.get("id") in TOGGLES:
            name = params.get(TOGGLES[a["id"]])
            return name if isinstance(name, str) else None
        name, value = params.get(FLIPS.get(a.get("id"), "")), params.get("value")
        if not isinstance(name, str) or not isinstance(value, str):
            return None
        x = re.escape(name) if a["id"] == "set-eventvar-value" else \
            rf"(?:self|{re.escape(str(a.get('objectClass')))})\.{re.escape(name)}"
        v = re.sub(r"\s+", "", value)
        forms = (rf"\(?-?\d+(?:\.\d+)?-{x}\)?", rf"-\(?{x}\)?", rf"\(?{x}\)?\*\(?-1\)?", rf"\(?-1\)?\*\(?{x}\)?")
        if any(re.fullmatch(f, v, re.I) for f in forms):
            return name
        m = re.fullmatch(rf"\(?{x}(=|<>)({LITERAL})\)?\?({LITERAL}):({LITERAL})", v, re.I)
        # x = a ? b : a and x <> a ? a : b go back to a on the next run
        if m and m.group(3) != m.group(4) and m.group(2) == (m.group(4) if m.group(1) == "=" else m.group(3)):
            return name
        return None

    @staticmethod
    def actions_below(ev: dict) -> list[dict]:
        """The actions of an event and of all its sub-events."""
        return [a for a in ev.get("actions") or [] if isinstance(a, dict)] + \
            [a for k in ev.get("children") or [] if isinstance(k, dict) for a in Checker.actions_below(k)]

    def writes(self, actions: list, seen: set[int]) -> set[str] | None:
        """What these actions change that a condition may test, lower case: the variables they set or toggle,
        and the types they create or destroy. The functions and custom actions they call count with their
        events. None when one leaves the group or the layout. seen: the blocks already read."""
        out: set[str] = set()
        for a in actions:
            if a.get("objectClass") == "System" and a.get("id") in LEAVES:
                return None
            if a.get("id") in SETS:
                out.add(str(params_of(a).get(SETS[a["id"]], "")).lower())
            if a.get("id") == "destroy" or self.made_by(a):
                out.add(str(self.made_by(a) or a.get("objectClass")).lower())
            hit = self.called(a)
            if hit and id(hit[1]) not in seen:
                seen.add(id(hit[1]))
                below = self.writes(self.actions_below(hit[1]), seen)
                if below is None:
                    return None
                out |= below
        return out

    @staticmethod
    def tests_a_value(c: dict) -> bool:
        """Whether a condition tests a value that holds until an event changes it, a variable or Count, or is
        Else or Trigger once; an input, an overlap, a position or a function changes as the game plays."""
        if c.get("objectClass") == "System" and c.get("id") in ("else", "trigger-once-while-true"):
            return True
        moving = any(m.group(2).lower() != "count" for value in params_of(c).values() if isinstance(value, str)
                     for m in OBJECT_EXPRESSION.finditer(value))
        return ((c.get("objectClass"), c.get("id")) in VALUE_TESTS or c.get("id") in INSTANCE_VALUE_TESTS) \
            and not moving

    def check_flip(self, action: dict, where: str, line: tuple, paced: bool | None) -> None:
        """A variable flipped in an event that runs every tick: the event runs again on the next tick and flips
        it back. Under Trigger once alone, with conditions that test values, the flip happens once each time
        they turn true, not once per input. That is a warning edit_sheet.py does not refuse, since a flip once a
        round is sound. A branch passes when its actions change what its conditions test: they set a variable,
        create or destroy a type, or act on an object a condition is on or reads (Player.X, Grid.At). It also
        passes when they leave the group or layout. An event that starts with Else also tests the event it
        answers. line: the event and those above it."""
        name = self.flipped(action) if paced is not None else None
        if name is None:
            return
        kinds = set().union(*(self.pacing(ev) for ev in line))
        if kinds - {"once"}:
            return
        tested = []
        for ev in line:
            while ev is not None:
                tested += [c for c in ev.get("conditions", []) if isinstance(c, dict)]
                ev = self.answered.get(id(ev))
        if kinds and not all(self.tests_a_value(c) for c in tested):
            return
        read = self.words_of(tested) | {str(c.get("objectClass")).lower() for c in tested
                                        if c.get("objectClass") != "System"}
        actions = [a for ev in line for a in ev.get("actions", []) if isinstance(a, dict)]
        changed = self.writes(actions, set())
        if changed is None or changed & read \
                or any(a is not action and str(a.get("objectClass")).lower() in read for a in actions):
            return
        owner = "" if action.get("objectClass") == "System" else f"{action.get('objectClass')} "
        what = f"{owner}Toggle {name}" if action["id"] in TOGGLES else f"{owner}Set {name} to {params_of(action)['value']}"
        touch = next((n for n, plugin in self.p.plugin_of.items() if plugin.lower() == "touch"), "Touch")
        trigger = json.dumps({"id": "on-touched-object", "objectClass": touch,
                              "parameters": {"object": "<Object>", "type": "start"}})
        if kinds:
            self.p.findings.style_finding(
                "flip-once", f"{where}: {what} under Trigger once flips {name} once each time the conditions of "
                             f"its event turn true. They test values, not an input, so {name} changes when those "
                             f"values do, not once per tap or move. If it should follow each tap or move, move the "
                             f"flip into the event whose trigger causes the change, or into a sub-event of it, such "
                             f"as {trigger} with the tapped object for <Object>")
            return
        # A timeout has no trigger: the event that tests the time left resets it, and so runs once.
        timer = next((params_of(c).get("variable") for c in tested if c.get("id") == "compare-eventvar"
                      and params_of(c).get("variable") != name), None)
        reset = json.dumps({"id": "set-eventvar-value", "objectClass": "System",
                            "parameters": {"variable": timer or "<the time left>", "value": "<its start value>"}})
        self.p.findings.style_finding(
            "flip", f"{where}: {what} flips {name} on every tick, so an input can read either value: no trigger is "
                    f"in its event or above it. Move the flip into the event whose trigger causes the change, or "
                    f"into a sub-event of it. Trigger once does not fix it: it flips {name} once when the "
                    f"conditions turn true, not once per change. An event of its own for the flip starts with "
                    f"that trigger, such as {trigger}, with the tapped object for <Object>. If a value that runs "
                    f"out causes the change, such as the time left of a turn, keep the flip here and set that value "
                    f"back in the same actions, {reset}: the event then runs once each time it runs out")

    def none_left(self, c: dict) -> tuple[str, str] | None:
        """Return (the object type, "count" or "pickedcount") when a condition tests that none of the type is
        left, X.Count = 0 or X.PickedCount = 0, in Compare two values with the operands in either order or in
        Evaluate expression; None otherwise."""
        params = params_of(c)
        if c.get("objectClass") != "System" or c.get("isInverted"):
            return None
        if c.get("id") == "compare-two-values" and params.get("comparison") in COMPARISONS:
            text = f"{params.get('first-value')}{COMPARISONS[params['comparison']]}{params.get('second-value')}"
        elif c.get("id") == "evaluate-expression":
            text = str(params.get("value"))
        else:
            return None
        m = NONE_LEFT.fullmatch(re.sub(r"\s+", "", text))
        return None if m is None else (m.group(1), m.group(2).lower()) if m.group(1) else (m.group(3), m.group(4).lower())

    @staticmethod
    def picks(c: dict) -> set[str]:
        """The object types and families a condition narrows, lower case: its own, unless it is System's, and
        the one its object parameter names (Pick all, For each, On touched object, Is overlapping)."""
        own = c.get("objectClass") if c.get("objectClass") != "System" else None
        return {n.lower() for n in (own, params_of(c).get("object")) if isinstance(n, str)}

    def check_none_left(self, c: dict, where: str, gone: dict[str, str] | None, earlier: list[dict]) -> None:
        """X.Count = 0 after a Destroy of X earlier in the same top-level event: the destroyed instance counts
        until the top-level event ends (prompts/pitfalls/picking.md), so the test fails for the last one.
        X.PickedCount = 0 below a condition that picks X: a pick of no X stops the event, Pick all included.
        gone: object type -> where an action destroyed it before this condition runs; earlier: the conditions
        that run before this one in its branch, those of OR blocks left out."""
        tested = self.none_left(c)
        if tested is None:
            return
        name, expression = tested
        if expression == "pickedcount":
            pick = next((e for e in earlier if name.lower() in self.picks(e)), None)
            if pick:
                count = json.dumps({"id": "compare-two-values", "objectClass": "System",
                                    "parameters": {"first-value": f"{name}.Count", "comparison": 0, "second-value": "0"}})
                self.p.findings.style_finding(
                    "picked", f"{where}: {name}.PickedCount = 0 never holds here. {describe(pick)} above it picks "
                              f"{name}, and a condition that picks no {name} stops its event, as System Pick all does "
                              f"when no {name} exists. Test none left in an event that does not pick {name}, {count}")
            return
        obj = next((o for o in gone or {} if o.lower() == name.lower()), None)
        if obj is None:
            return
        test = json.dumps([{"id": "compare-two-values", "objectClass": "System",
                            "parameters": {"first-value": f"{obj}.Count", "comparison": 0, "second-value": "0"}},
                           {"id": "trigger-once-while-true", "objectClass": "System"}])
        self.p.findings.style_finding(
            "count", f"{where}: {obj}.Count = 0 is false here even when the last {obj} is gone. {gone[obj]} destroys "
                     f"it earlier in this top-level event, and a destroyed instance counts in Count until that event "
                     f"ends. Test it in a top-level event of its own, with the conditions {test}")

    @staticmethod
    def equals_constant(c: dict) -> tuple[str, str, str] | None:
        """(object, instance variable, value) of X: variable = a number or text literal, not inverted."""
        params = params_of(c)
        value = str(params.get("value", "")).strip()
        if (c.get("id") != "compare-instance-variable" or c.get("isInverted") or params.get("comparison") != 0
                or not (NUMBER.fullmatch(value) or STRING_LITERAL.fullmatch(value))):
            return None
        return c.get("objectClass", ""), str(params.get("instance-variable", "")).lower(), value

    def check_narrowed(self, c: dict, where: str, earlier: list[dict]) -> None:
        """X: v = 0 below X: v = 1 in the same branch: each condition keeps the instances the one above kept, so
        none passes both and the event never runs. A QQ bot wrote a tic-tac-toe row as nine Cell conditions
        (Row = 0, Column = 0, Value = 1, Row = 0, Column = 1, ...), 2026-10-06. A Pick all of X in between
        starts the narrowing again."""
        mine = self.equals_constant(c)
        if mine is None:
            return
        obj, var, value = mine
        for e in reversed(earlier):
            if e.get("id") == "pick-all" and str(params_of(e).get("object", "")).lower() == obj.lower():
                return
            other = self.equals_constant(e)
            if other and other[0] == obj and other[1] == var and other[2] != value:
                self.p.findings.style_finding(
                    "narrowed", f"{where}: {obj}.{params_of(c).get('instance-variable')} = {value} below "
                                f"{obj}.{params_of(e).get('instance-variable')} = {other[2]} in the same event never holds: each condition keeps only the {obj} "
                                f"the conditions above it kept, so no instance passes both. To test that several "
                                f"instances agree, narrow once and count: {obj}: Row = 0, {obj}: Value = 1, then "
                                f"System: {obj}.PickedCount = 3, or keep the values in an Array and compare its cells")
                return

    def check_block(self, ev: dict, scope: dict, where: str, by_input: bool | None = False,
                    paced: bool | None = False, line: tuple = (), gone: dict[str, str] | None = None) -> None:
        """by_input as check_gesture's; paced: whether the event or one above it is triggered, on a timer
        or Trigger once, None in a function or custom action; line: the event and those above it; gone: as
        check_none_left's, filled by the event's Destroy actions, None for the sub-events of an event whose
        actions wait."""
        held = tuple(c for e in line for c in e.get("conditions", []) if isinstance(c, dict))
        earlier = [c for e in line[:-1] if not e.get("isOrBlock") for c in e.get("conditions", []) if isinstance(c, dict)]
        self.event_where[id(ev)] = where
        if isinstance(ev.get("actions"), list):
            self.action_lists.append((ev["actions"], where))
        for i, c in enumerate(ev.get("conditions", []), 1):
            self.check_ace("conditions", c, scope, f"{where} condition {i}")
            self.note_signal(c, f"{where} condition {i}")
            if isinstance(c, dict):
                self.check_none_left(c, f"{where} condition {i}", gone, earlier)
                if not ev.get("isOrBlock"):
                    self.check_narrowed(c, f"{where} condition {i}", earlier)
                    earlier.append(c)
        found: dict[str, str] = {}
        for i, a in enumerate(ev.get("actions", []), 1):
            w = f"{where} action {i}"
            self.note_signal(a, w)
            self.check_gesture(a, by_input, w)
            self.check_pathfinding(a, w, found, paced)
            self.check_held_control(a, w, held, paced)
            self.check_timer_restart(a, w, line, held, paced)
            self.check_flip(a, w, line, paced)
            if gone is not None and a.get("id") == "destroy" and a.get("objectClass") in self.p.plugin_of:
                gone.setdefault(a["objectClass"], w)
            if a.get("type") == "script":
                self.check_script(a.get("script"), scope, w)
            if a.get("type") in ("comment", "script"):
                continue
            if "callFunction" in a or "customAction" in a:
                params = a.get("parameters", [])
                if not isinstance(params, list):
                    self.err(f"{w}: the call writes \"parameters\": {json.dumps(params, ensure_ascii=False)}, and the "
                             f"editor stops with \"TypeError: expected array\" before the project opens. Write the "
                             f"arguments as a list in order, \"parameters\": [\"1\"], or leave the key out when the "
                             f"call passes none")
                    params = []
                if "callFunction" in a:
                    self.pending_calls.append(("function", a["callFunction"], None, len(params), w))
                else:
                    owner = a.get("customActionObjectClass", a["objectClass"])
                    self.pending_calls.append(("custom", a["customAction"], owner, len(params), w))
                for param in params:
                    self.check_expr(w, param, scope)
                continue
            self.check_ace("actions", a, scope, w)

    def check_event_lists(self, ev: dict, et, where: str) -> None:
        """What the editor walks as it reads an event. A block and its two
        relatives loop over conditions and actions without looking first, so a
        block that carries neither stops the open where the sheet is named and
        the event is not."""
        if et in ("block", "function-block", "custom-ace-block"):
            for what in ("conditions", "actions"):
                if not isinstance(ev.get(what), list):
                    self.err(f"{where}: {what} is {ev.get(what)!r}; the editor walks both lists as it reads the "
                             f'event. An event with none writes "{what}": []')
        if et == "script" and not isinstance(ev.get("script"), (str, list)):
            self.err(f"{where}: script is {ev.get('script')!r}; the editor stops with \"invalid script data\". "
                     f"Write the code as text, or as a list with a line per item")
        if "children" in ev and not isinstance(ev["children"], list):
            self.err(f"{where}: children is {ev['children']!r}; sub-events are a list, and an event with none "
                     f"leaves the key out")
        # Text the editor reads without a default; an empty one is written "".
        for kind, key, message in EVENT_TEXT:
            if et == kind and not isinstance(ev.get(key), str):
                self.err(f"{where}: the {kind} has {key} {ev.get(key)!r}; write \"{key}\": \"\" when it has none, "
                         f"the editor reads it as text and stops with \"{message}\"")
        if et == "function-block" and ev.get("functionReturnType") not in FUNCTION_RETURN_TYPES:
            self.err(f"{where}: functionReturnType {ev.get('functionReturnType')!r} is not one of "
                     f"{', '.join(FUNCTION_RETURN_TYPES)}; the editor stops with \"function has wrong return type\"")
        if et == "custom-ace-block" and ev.get("aceType") != "action":
            self.err(f"{where}: aceType {ev.get('aceType')!r} should be \"action\", the one kind of custom ACE; "
                     f"the editor stops with \"invalid ACE type\"")

    def walk(self, events: list, scope: dict, where: str, counter: list[int], above: Holder | None = None,
             depth: int = 0, group: dict | None = None, by_input: bool | None = False,
             paced: bool | None = False, line: tuple = (), gone: dict[str, str] | None = None,
             holder: str = "") -> None:
        """A local declared in a list of sibling events is visible to every event of
        that list, whatever the order, and to their sub-events; not to the parent's
        own actions. So the list's variables enter the scope first, and a block is
        checked before its children are walked. scope maps a name to the variable
        event or function parameter that declares it, in the order enter keeps; a
        sheet's own top-level variables are there before its walk. counter holds the sheet's
        running event number, above what holds the trigger of this branch, depth
        how many sub-event levels down this list is (a group's children are 0),
        group the group whose children the list is, by_input whether an event above
        tests input (check_gesture), paced whether one above is triggered or on a
        timer (check_pathfinding), line the events above in this branch, gone
        what the top-level event destroyed before the list runs (check_none_left),
        shared by the list's events in the order they run, holder the event that
        holds the list, "group Movement", "event 5" or "function launch"."""
        scope = dict(scope)
        bad = [ev for ev in events if not isinstance(ev, dict)]
        if bad:
            self.err(f"{where}: an event is {bad[0]!r}; every event is an object with an eventType")
            events = [ev for ev in events if isinstance(ev, dict)]
        outer = dict(scope)
        for ev in events:
            if ev.get("eventType") == "variable" and id(ev) not in self.global_ids:
                self.enter(scope, ev, outer, f"{where} variable {ev['name']}", holder)
        ladders = self.ladders(events) if self.style else {}
        numbered: dict[int, list[tuple[int, str]]] = {}
        find_tests: dict[str, list[tuple[int, str, str]]] = {}
        previous = None
        for i, ev in enumerate(events):
            et = ev.get("eventType")
            if et in NUMBERED:
                counter[0] += 1
            w = f"{where} event {counter[0] + (et not in NUMBERED)} (sid {ev.get('sid', '?')})"
            self.check_event_lists(ev, et, w)
            if self.style and et in ("block", "function-block", "custom-ace-block"):
                self.check_style(ev, w, events, i, depth, group, counter[0])
            if et == "block":
                self.check_undone(events[:i], ev, w)
            if self.style and et == "block":
                for subject, code in self.find_tests(ev):
                    find_tests.setdefault(subject, []).append((counter[0], w, code))
            if id(ev) in ladders:
                rungs = numbered.setdefault(ladders[id(ev)][0], [])
                rungs.append((counter[0], w))
                if len(rungs) == ladders[id(ev)][1]:
                    self.check_ladder(rungs)
            if et == "variable":
                self.check_variable(ev, w, "variable")
            elif et in ("comment", "include"):
                if et == "include" and ev["includeSheet"] not in self.sheets:
                    self.err(f"{w}: included sheet {ev['includeSheet']} does not exist"
                             f"{closest(ev['includeSheet'], self.sheets)}")
                elif et == "include" and where == f"sheet {ev['includeSheet']}":
                    self.err(f"{w}: a sheet cannot include itself")
            elif et == "group":
                self.walk(ev.get("children") or [], scope, where, counter, above, group=ev, by_input=by_input,
                          paced=paced, holder=f"group {ev.get('title')}")
            elif et in ("function-block", "custom-ace-block"):
                kind = "function" if et == "function-block" else "custom action"
                name = ev.get("functionName") if et == "function-block" else ev.get("aceName")
                label = ev.get("functionName") or f"{ev['objectClass']}.{ev['aceName']}"
                if isinstance(name, str):
                    self.check_callable_name(ev, kind, name, w)
                fscope = dict(scope)
                outer = dict(fscope)
                params = ev["functionParameters"]
                # Of the parameters whose names match without case, the editor keeps the last.
                last = {LOWER(p["name"]): p for p in params if isinstance(p.get("name"), str)}
                taken = set(fscope) | {p.get("name") for p in params}
                for param in params:
                    kept = last[LOWER(param["name"])] if isinstance(param.get("name"), str) else param
                    if kept is param:
                        self.enter(fscope, param, outer, f"{w} parameter {param['name']}", f"{kind} {label}")
                    else:
                        new = free_name(param["name"], taken)
                        taken.add(new)
                        self.check_parameter_renamed(param, kept, f"{w} parameter {param['name']}", new)
                    self.check_variable(param, w, "parameter")
                if et == "custom-ace-block" and ev["objectClass"] not in self.p.plugin_of:
                    self.err(f"{w}: custom action {label} belongs to unknown object {ev['objectClass']}")
                body: dict[str, str] = {}
                self.check_block(ev, fscope, f"{w} {label}", None, None, gone=body)
                self.walk(ev.get("children", []), fscope, where, counter,
                          self.check_structure(ev, f"{w} {label}", above, previous), depth + 1, by_input=None,
                          paced=None, gone=None if any(self.waits(a) for a in ev.get("actions", [])) else body,
                          holder=f"{kind} {label}")
            elif et == "block":
                here = None if by_input is None else by_input or self.reads_input(ev)
                timed = None if paced is None else paced or self.paces(ev)
                first = next(iter(ev.get("conditions") or []), None)
                if isinstance(first, dict) and (first.get("objectClass"), first.get("id")) == ("System", "else") \
                        and previous is not None and previous.get("eventType") == "block":
                    self.answered[id(ev)] = previous
                # A top-level event starts with nothing destroyed; after a Wait its sub-events run later.
                mine = {} if depth == 0 else gone
                self.check_block(ev, scope, w, here, timed, line + (ev,), mine)
                self.walk(ev.get("children", []), scope, where, counter, self.check_structure(ev, w, above, previous),
                          depth + 1, by_input=here, paced=timed, line=line + (ev,),
                          gone=None if any(self.waits(a) for a in ev.get("actions", [])) else mine,
                          holder=f"event {counter[0]}")
            elif et == "script":
                self.check_script(ev.get("script"), scope, w)
            else:
                self.err(f"{w}: unknown eventType {et!r}; the editor knows block, group, variable, comment, include, "
                         f"function-block, custom-ace-block and script")
            if et != "comment":
                previous = ev
        self.check_find_dispatch(find_tests)

    @staticmethod
    def find_tests(ev: dict) -> list[tuple[str, str]]:
        """(text searched, code) for each find or findcase in the event's conditions whose
        second argument is a text literal: find(TMP, "BU")."""
        tests = []
        for c in ev.get("conditions", []):
            params = c.get("parameters")
            for value in (params.values() if isinstance(params, dict) else []):
                if not isinstance(value, str):
                    continue
                for m in outside_literals(value, FIND_LITERAL_SECOND.finditer(value)):
                    args = arguments_from(value, m.end())
                    if len(args) == 2 and STRING_LITERAL.fullmatch(args[1]) and \
                            not STRING_LITERAL.fullmatch(args[0]):
                        tests.append((re.sub(r"\s+", "", args[0]), args[1]))
        return tests

    # --- style, with --style ------------------------------------------------------------
    def check_style(self, ev: dict, where: str, siblings: list, i: int, depth: int, group: dict | None,
                    n: int) -> None:
        """Habits of sheets written by small models, each with the shape the
        official examples give it instead. Warnings, never errors: the editor
        accepts them all. The thresholds sit past the 90th percentile of the
        studio examples, where a run of actions without a comment is 3 at the
        median and 6 at the 90th percentile, branches go two sub-events deep in
        93% of events, 93% of top-level events have a comment above them, and
        of the events with two or more case sub-events 84% have a comment above
        at least one case (docs/decisions/event-sheet-design-guidance.md,
        2026-09-22). edit_sheet.py refuses a plan whose new events raise the
        ones whose fix is one comment or one deleted condition, and prints the others; check_project.py
        reports them all over the whole project when asked, which suits a
        project the agent wrote. Every tick beside another condition adds
        nothing: an event without a trigger is tested every tick. A ladder of sibling events is check_ladder."""
        actions = ev.get("actions", [])
        run = longest = 0
        for a in actions:
            run = 0 if a.get("type") == "comment" else run + 1
            longest = max(longest, run)
        style = self.p.findings.style_finding
        if longest >= STYLE_RUN:
            style("run", f"{where}: {longest} actions in a row without a comment action; the official examples step a "
                         f"long block with a comment action every three to five actions, "
                         '{"type": "comment", "text": "What the next actions do."}')
        conditions = ev.get("conditions", [])
        others = [c for c in conditions if (c.get("objectClass"), c.get("id")) != ("System", "every-tick")]
        if not ev.get("isOrBlock") and others and len(others) < len(conditions):
            style("tick", f"{where}: Every tick beside {len(others)} other condition(s) changes nothing, an event "
                          f"without a trigger is tested every tick already; the official examples write Every tick "
                          f"only as an event's one condition. Remove it")
        self.check_countdown(ev, where, conditions, actions)
        if depth == 0 and (actions or ev.get("children")):
            j = i - 1
            while j >= 0 and siblings[j].get("eventType") == "variable":     # locals declared above the event
                j -= 1
            commented = j >= 0 and siblings[j].get("eventType") == "comment"
            comment = '{"eventType": "comment", "text": "..."}'
            if not commented and group is None:
                style("comment", f"{where}: no comment above it; the official examples put a one-sentence comment "
                                 f"above every top-level event, saying what it does or which case it is, "
                                 f"{comment} as the event before it")
            elif not commented:
                # Small models took "top-level" for the sheet's own list and put the comment
                # above the group, plan after plan (event-sheet-design-guidance.md): name the list it goes into.
                on_disk = f'; edit_sheet.py puts it there with {{"before": {n}, "events": [{comment}]}}'
                style("comment", f"{where}: no comment above it; the official examples put a one-sentence comment "
                                 f"above every top-level event, the events directly in a group included, saying "
                                 f"what it does or which case it is. This one is entry {i + 1} in the \"children\" "
                                 f"of group {json.dumps(group.get('title'), ensure_ascii=False)}: {comment} goes "
                                 f"into that list before it" + (on_disk if self.numbers_on_disk else ""))
        cases = [j for j, k in enumerate(ev.get("children", []))
                 if k.get("eventType") == "block" and (k.get("actions") or k.get("children"))]
        if len(cases) >= 2 and not any(j > 0 and ev["children"][j - 1].get("eventType") == "comment" for j in cases):
            style("cases", f"{where}: none of its {len(cases)} case sub-events has a comment above it; the official "
                           f"examples put a one-sentence comment above each case, saying which case it is, "
                           '{"eventType": "comment", "text": "..."} as the event before each')
        if depth == 0 and self.tree_depth(ev) >= STYLE_TREE:
            leaves = self.leaves(ev)
            called = {a["callFunction"] for leaf in leaves for a in leaf.get("actions", []) if "callFunction" in a}
            if len(leaves) >= 3 and len(called) == 1 and \
                    all(any("callFunction" in a for a in leaf.get("actions", [])) for leaf in leaves):
                style("tree", f"{where}: sub-events {self.tree_depth(ev)} levels deep, every leaf calling "
                              f"{called.pop()}; the official examples write the cases as sibling sub-events with a "
                              f"comment each, or compute the value in one expression")

    @staticmethod
    def seconds_taken(a: dict, interval: float) -> str | None:
        """The variable an action takes `interval` off, in any of the three spellings small
        models write: Subtract N, Add -N, Set v to v - N; None for any other action."""
        params = a.get("parameters")
        if not isinstance(params, dict):
            return None
        aid, value = a.get("id"), params.get("value")
        name = params.get("instance-variable" if aid in COUNTDOWN_ON_INSTANCE else "variable")
        if aid in ("subtract-from-eventvar", "subtract-from-instvar"):
            return name if number_of(value) == interval else None
        if aid in ("add-to-eventvar", "add-to-instvar"):
            return name if number_of(value) == -interval else None
        if aid in ("set-eventvar-value", "set-instvar-value") and isinstance(value, str):
            m = re.fullmatch(r"\s*(?:\w+\s*\.\s*)?(\w+)\s*-\s*([\d.]+)\s*", value)
            if m and m.group(1).lower() == str(name).lower() and number_of(m.group(2)) == interval:
                return name
        return None

    def check_countdown(self, ev: dict, where: str, conditions: list, actions: list) -> None:
        """Every N seconds taking N off a variable: the variable counts seconds, a timer
        kept by hand. Of the 155 eval and small-model projects, 73 wrote it, as Subtract 1
        (60), Add -1 (12) or Set v to v - 1 (1); none of the 524 official examples does,
        and the one that subtracts every N seconds counts coins, not time. A global
        counted this way keeps its value across Restart layout, so the next round starts
        at 0 (event-sheet-design-guidance.md, 2026-09-28). Subtracting dt is left alone:
        the examples count cooldowns that way."""
        every = [c for c in conditions if (c.get("objectClass"), c.get("id")) == ("System", "every-x-seconds")]
        if not every or ev.get("isOrBlock"):
            return
        interval = (every[0].get("parameters") or {}).get("interval-seconds")
        if number_of(interval) is None:
            return
        for a in actions:
            name = self.seconds_taken(a, number_of(interval))
            if name is None:
                continue
            on_instance = a["id"] in COUNTDOWN_ON_INSTANCE
            owner = a.get("objectClass", "<Object>") if on_instance else "<Object>"
            start = json.dumps({"id": "start-timer", "objectClass": owner, "behaviorType": "Timer",
                                "parameters": {"duration": "<seconds>", "type": "once", "tag": '"countdown"'}})
            self.p.findings.style_finding(
                "countdown", f"{where}: {name} counts seconds by hand, {number_of(interval):g} off every {interval} seconds"
                             + ("" if on_instance else "; a global keeps its value across Restart layout, so the next "
                                                       "round starts where this one ended") +
                             f". The Timer behavior counts time: add it to "
                             f"{owner if on_instance else 'the object that shows the time (<Object> below)'}, start it where "
                             f"the count starts, {start}, end the count in Timer On timer \"countdown\", and show "
                             f"ceil({owner}.Timer.Duration(\"countdown\") - {owner}.Timer.CurrentTime(\"countdown\"))")
            return

    @staticmethod
    def shape(ev: dict) -> tuple:
        """An event's conditions and actions by their ACE, without their values."""
        return (ev.get("isOrBlock", False),
                tuple((c.get("objectClass"), c.get("id"), c.get("isInverted", False)) for c in ev.get("conditions", [])),
                tuple((a.get("objectClass"), a.get("id")) for a in ev.get("actions", [])),
                len([k for k in ev.get("children", []) if k.get("eventType") == "block"]))

    def ladders(self, events: list) -> dict[int, tuple[int, int]]:
        """The sibling blocks that share their shape with STYLE_LADDER or more others, by
        id, each mapped to its ladder's number and size. One event per option,
        building or state, only the numbers changed, is a table transcribed into
        events; the studio examples reach five such siblings in 32 places of 20 of their 219
        projects, input ladders (a key per action) and else-if chains among them."""
        of_shape: dict[tuple, list[dict]] = {}
        for ev in events:
            if ev.get("eventType") == "block" and (ev.get("actions") or ev.get("children")):
                of_shape.setdefault(self.shape(ev), []).append(ev)
        return {id(ev): (n, len(evs)) for n, evs in enumerate(of_shape.values()) if len(evs) >= STYLE_LADDER
                for ev in evs}

    def trigger_of(self, ev: dict) -> dict | None:
        """The event's first condition when it is a trigger, else None."""
        conds = [c for c in ev.get("conditions") or [] if isinstance(c, dict)]
        if not conds:
            return None
        entry = self.p.ace_entry("conditions", conds[0])
        return conds[0] if (entry.get("isTrigger") if entry else str(conds[0].get("id", "")).startswith("on-")) \
            else None

    @staticmethod
    def state_set(actions: list) -> set[str]:
        """The variables these actions set, and Obj.animationframe and the like for the state of an object, up to
        the first wait: what a wait leaves for later, the next event of the same input does not see."""
        out = set()
        for a in actions:
            if Checker.waits(a):
                break
            params = params_of(a)
            if a.get("id") in SETS or (a.get("objectClass") == "System" and a.get("id") in ("add-to-eventvar",
                                                                                       "subtract-from-eventvar")):
                out.add(str(params.get(SETS.get(a["id"], "variable"), "")).lower())
            if a.get("id") in STATE_SETS and a.get("objectClass") != "System":
                prop = STATE_SETS[a["id"]] or str(params.get("instance-variable", "")).lower()
                out.add(f"{str(a.get('objectClass')).lower()}.{prop}")
        return out

    def state_read(self, conditions: list) -> set[str]:
        """What these conditions test, in the form state_set() writes: variables, Obj.var, Obj.animationframe."""
        out = set()
        for c in conditions:
            obj = str(c.get("objectClass")).lower()
            if c.get("id") in STATE_TESTS:
                out.add(f"{obj}.{STATE_TESTS[c['id']]}")
            if c.get("id") in INSTANCE_VALUE_TESTS:
                out.add(f"{obj}.{str(params_of(c).get('instance-variable', '')).lower()}")
            for value in params_of(c).values():
                if isinstance(value, str):
                    out |= {m.lower() for m in re.findall(r"\w+\.\w+", value)} | {w.lower() for w in IDENT.findall(value)}
        return out

    def check_undone(self, before: list, ev: dict, where: str) -> None:
        """A block with the same trigger as an earlier block in its list that tests what that block changed.
        Both run on the one input, the later one after the earlier one's actions, so it sees the new value: a
        switch written as "frame 0: set 1" and "frame 1: set 0" sets it back on every tap. Else does not reach
        across two events with their own trigger; one event with the trigger and two case sub-events, the
        second starting with Else, does."""
        trigger = self.trigger_of(ev)
        tests = [c for c in (ev.get("conditions") or [])[1:] if isinstance(c, dict)]
        if trigger is None or not tests:
            return
        same = ("objectClass", "id", "parameters", "isInverted")
        key = json.dumps({k: trigger.get(k) for k in same}, sort_keys=True)
        read = self.state_read(tests)
        for earlier in reversed(before):
            if not isinstance(earlier, dict) or earlier.get("eventType") != "block":
                continue
            first = self.trigger_of(earlier)
            if first is None or json.dumps({k: first.get(k) for k in same}, sort_keys=True) != key:
                continue
            actions = self.actions_below(earlier)
            hit = sorted(self.state_set(actions) & read)
            if not hit:
                continue
            case = json.dumps({"eventType": "block", "conditions": [{"id": "else", "objectClass": "System"}],
                               "actions": ["..."]})
            self.p.findings.style_finding(
                "undone", f"{where}: it has the same trigger as an earlier event in its list and tests {', '.join(hit)}, "
                          f"which that event's actions change. Both run on the same input, this one after the other, "
                          f"so it sees the value just set and can set it back: a switch never stays switched. Write "
                          f"one event with the trigger, and the cases as its sub-events: the first with the test, the "
                          f"second {case}")
            return

    def check_ladder(self, rungs: list[tuple[int, str]]) -> None:
        others = ", ".join(str(n) for n, _ in rungs[1:])
        self.p.findings.style_finding(
            "ladder", f"{rungs[0][1]}: with events {others}, the same conditions and actions {len(rungs)} times over, "
                      f"differing only in their values; the official examples write such cases once, over what "
                      f"differs: an instance variable of the object touched, a family, a Dictionary loaded from a "
                      f"project file, or the value in one expression")

    @staticmethod
    def tree_depth(ev: dict) -> int:
        kids = [k for k in ev.get("children", []) if k.get("eventType") == "block"]
        return 1 + max((Checker.tree_depth(k) for k in kids), default=0) if kids else 0

    @staticmethod
    def leaves(ev: dict) -> list[dict]:
        kids = [k for k in ev.get("children", []) if k.get("eventType") == "block"]
        return [leaf for k in kids for leaf in Checker.leaves(k)] if kids else [ev]

    def declared_functions(self, events: list) -> None:
        """Functions and custom actions are visible from every sheet, so collect them
        first. An event that is not an object is reported by walk(), which numbers it."""
        for ev in events:
            if not isinstance(ev, dict):
                continue
            et = ev.get("eventType")
            if et == "function-block":
                self.functions[ev["functionName"]] = len(ev["functionParameters"])
                self.returns[LOWER(ev["functionName"])] = ev.get("functionReturnType")
                self.function_blocks[ev["functionName"]] = ev
            elif et == "custom-ace-block":
                self.custom_actions[(ev["objectClass"], ev["aceName"])] = len(ev["functionParameters"])
                self.custom_blocks[(ev["objectClass"], ev["aceName"])] = ev
            self.declared_functions(ev.get("children") or [])

    def declared_groups(self, events: list) -> None:
        for ev in events:
            if not isinstance(ev, dict):
                continue
            if ev.get("eventType") == "group":
                self.group_titles.add(ev["title"])
            self.declared_groups(ev.get("children") or [])

    def check_sheets(self) -> None:
        for sname, sheet in self.sheets.items():
            if not (isinstance(sheet.get("name"), str) and sheet["name"]):
                self.err(f"sheet {sname}: the file says \"name\": {sheet.get('name')!r}; the editor reads it "
                         f"as text and stops with \"invalid event sheet name\"")
            if not isinstance(sheet.get("events"), list):
                self.err(f"sheet {sname}: events is {sheet.get('events')!r}; an empty sheet writes "
                         f"\"events\": []")
        self.sheets = {n: s for n, s in self.sheets.items() if isinstance(s.get("events"), list)}
        for sheet in self.sheets.values():
            self.collect_sids(sheet)
        for sheet in self.sheets.values():
            self.declared_functions(sheet["events"])
            self.declared_groups(sheet["events"])
        # A global declared at the top level of any sheet is visible from every sheet.
        tops = [(sname, ev) for sname, s in self.sheets.items() for ev in s["events"]
                if isinstance(ev, dict) and ev.get("eventType") == "variable"]
        self.global_ids = {id(ev) for _, ev in tops}
        sheet_of = {id(ev): sname for sname, ev in tops}
        globals_: dict = {}
        for sname, ev in tops:
            earlier = self.variable_named(ev.get("name"), globals_)
            if earlier is not None:
                self.check_declared_once(ev, earlier, f"sheet {sname} variable {ev['name']}",
                                         f"declared at the top level of sheet {sheet_of[id(earlier)]}")
            elif isinstance(ev.get("name"), str):
                globals_[ev["name"]] = ev
        # The order the editor reads variables and parameters in: sheet by sheet, each event before its sub-events.
        self.load_order = {id(v): i for i, v in enumerate(
            v for s in self.sheets.values() for v in declarations(s["events"]))}
        self.variable_names = {v.get("name") for s in self.sheets.values() for v in declarations(s["events"])}
        for sname, sheet in self.sheets.items():
            # A plan's sheet has numbers the file does not have yet: no operation can address them.
            self.numbers_on_disk = sname not in self.unsaved
            self.walk(sheet["events"], globals_, f"sheet {sname}", [0])

    def check_calls(self) -> None:
        p = self.p
        for kind, name, owner, nparams, where in self.pending_calls:
            if kind == "function":
                if name not in self.functions:
                    self.err(f"{where}: call to undefined function {name}{closest(name, self.functions)}")
                elif self.functions[name] != nparams:
                    self.err(f"{where}: {name} called with {nparams} parameters, defined with {self.functions[name]}")
                elif self.returns.get(LOWER(name), "none") != "none":
                    self.err(f"{where}: {name} returns a {self.returns[LOWER(name)]} and is called as an action; the "
                             f"editor stops with \"function '{name}' has wrong return type\". Read it in an expression, "
                             f"{p.functions_object}.{name}{'(...)' if nparams else ''}, or set its return type to none")
            else:
                owners = [owner] + p.families_of(owner)
                hit = next(((o, name) for o in owners if (o, name) in self.custom_actions), None)
                if hit is None:
                    self.err(f"{where}: {owner} has no custom action {name!r}"
                             + closest(name, [n for o, n in self.custom_actions if o in owners]))
                elif self.custom_actions[hit] != nparams:
                    self.err(f"{where}: {owner}.{name} called with {nparams} parameters, "
                             f"defined with {self.custom_actions[hit]}")
        # Signals are not kept: a Wait for signal or On signal that no Signal raises never ends or runs.
        for tag, ace, where in self.awaited if self.signalled is not None else []:
            if tag not in self.signalled:
                self.warn(f"{where}: no Signal action or runtime.signal() raises \"{tag}\", so this "
                          + ("Wait for signal never ends" if ace == "wait-for-signal" else "On signal never runs")
                          + f"; add Signal \"{tag}\" where it should")
        if self.solid_obstacles and self.solid_changes and not self.regenerated:
            places, more = self.solid_changes[:3], len(self.solid_changes) - 3
            self.warn("; ".join(places) + (f" and {more} more" if more > 0 else "")
                      + f": {'this changes' if len(places) == 1 else 'these change'} a Solid while Pathfinding "
                        "takes its obstacles from Solids, and nothing regenerates the obstacle map, which is built "
                        "once at startup: paths keep going round the old obstacles. After a change add Pathfinding "
                        "Regenerate region around object on the Solid, or for many changes Regenerate obstacle map; "
                        "it takes effect the next tick, so a Find path right after it waits first "
                        "(manual: behavior-reference/pathfinding.md)")
        self.check_pending_instances()
        for t in self.created:
            if t in p.types and t not in self.templates:
                self.warn(f"{t} is created at runtime but has no instance in any layout: "
                          f"it is created, but its behavior properties read 0 (a Bullet does not "
                          f"move); place one in a layout that never runs")

    # --- created instances read by a later function in the same actions ------------------------
    def is_object(self, name) -> bool:
        return isinstance(name, str) and (name in self.p.types or name in self.p.families)

    def related(self, a: str, b: str) -> bool:
        return a == b or a in self.p.families_of(b) or b in self.p.families_of(a)

    @staticmethod
    def waits(a: dict) -> bool:
        """Whether the actions after this one run later: a System wait, or a script that awaits."""
        if a.get("type") == "script":
            return "await" in script_text(a.get("script"))
        return a.get("objectClass") == "System" and a.get("id") in WAITS

    def made_by(self, a: dict) -> str | None:
        """The object type or family an action creates instances of, when a literal parameter names it."""
        obj, ace_id = a.get("objectClass"), a.get("id")
        key = CREATING.get((obj, ace_id)) or ("object" if ace_id == "spawn-another-object" else None)
        made = (a.get("parameters") or {}).get(key) if key else None
        return made if self.is_object(made) else None

    def picked_by(self, c: dict) -> str | None:
        """The object type or family a condition picks among the instances that have joined."""
        obj, cid = c.get("objectClass"), c.get("id")
        if obj == "System":
            made = (c.get("parameters") or {}).get("object") if cid in SYSTEM_PICKS else None
            return made if self.is_object(made) else None
        return obj if self.is_object(obj) and cid not in NOT_PICKING else None

    @staticmethod
    def picked_by_link(c: dict) -> str | None:
        """The type a condition picks through a link to an instance rather than among the type's
        instances: Pick by unique ID, Pick last created, or the child or parent of picked instances.
        A condition on that type after it narrows what the link found."""
        cid, params = c.get("id"), c.get("parameters") or {}
        if cid == "pick-by-unique-id":
            return c.get("objectClass")
        if cid == "pick-last-created" and c.get("objectClass") == "System":
            return params.get("object")
        if cid in ("pick-children", "pick-nth-child"):
            return params.get("child")
        return params.get("parent") if cid == "pick-parent" else None

    def called(self, a: dict) -> tuple[str, dict] | None:
        """(the name to print, the block) of the function or custom action an action calls."""
        if "callFunction" in a:
            name = a["callFunction"]
            return (name, self.function_blocks[name]) if name in self.function_blocks else None
        if "customAction" in a:
            owner = a.get("customActionObjectClass", a.get("objectClass"))
            for o in [owner] + self.p.families_of(owner):
                if (o, a["customAction"]) in self.custom_blocks:
                    return f"{owner}.{a['customAction']}", self.custom_blocks[(o, a["customAction"])]
        return None

    def summary(self, block: dict) -> tuple[dict, dict] | None:
        """What a function or custom action does when called, in its own events and the functions they
        call: ({type it creates: [the functions it calls to create it]},
        {type it picks: (where, condition, [the functions it calls to pick it])}).
        None when it waits anywhere, since what follows a wait runs after the instances have joined. A
        condition after a pick through a link on the same type (picked_by_link), or the picks of a custom
        action or a function that copies the caller's picked instances, are not counted: those start from
        instances the caller picked. A cycle of calls counts what is known when it closes."""
        key = id(block)
        if key in self._summaries:
            return self._summaries[key]
        self._summaries[key] = ({}, {})
        made: dict[str, list[str]] = {}
        picked: dict[str, tuple[str, str, list[str]]] = {}

        def visit(ev: dict, uids: set[str]) -> bool:
            if ev.get("eventType") == "script":
                return "await" not in script_text(ev.get("script"))
            uids = set(uids)
            for c in ev.get("conditions") or []:
                if not isinstance(c, dict):
                    continue
                linked = self.picked_by_link(c)
                if linked:
                    uids.add(linked)
                    continue
                t = self.picked_by(c)
                if t and not any(self.related(t, u) for u in uids if isinstance(u, str)):
                    picked.setdefault(t, (self.event_where.get(id(ev), "an event"), describe(c), []))
            for a in ev.get("actions") or []:
                if not isinstance(a, dict):
                    continue
                if self.waits(a):
                    return False
                t = self.made_by(a)
                if t:
                    made.setdefault(t, [])
                hit = self.called(a)
                sub = self.summary(hit[1]) if hit else None
                if sub:
                    for t, chain in sub[0].items():
                        made.setdefault(t, [hit[0]] + chain)
                    if hit[1].get("eventType") == "function-block" and not hit[1].get("functionCopyPicked"):
                        for t, (w, c, path) in sub[1].items():
                            picked.setdefault(t, (w, c, [hit[0]] + path))
            return all(visit(child, uids) for child in ev.get("children") or [] if isinstance(child, dict))

        self._summaries[key] = (made, picked) if visit(block, set()) else None
        return self._summaries[key]

    def check_pending_instances(self) -> None:
        """In one list of actions, a function that creates instances and then a function that picks them
        by a condition: the second runs before the instances join, and misses them."""
        for actions, where in self.action_lists:
            made: dict[str, tuple[int, list[str]]] = {}
            warned: set[tuple[str, str]] = set()
            for i, a in enumerate(actions, 1):
                if not isinstance(a, dict):
                    continue
                if self.waits(a):
                    break       # the rest runs later, where when the instances join is not read here
                t = self.made_by(a)
                if t:
                    made.setdefault(t, (i, []))
                    continue
                hit = self.called(a)
                sub = self.summary(hit[1]) if hit else None
                if not sub:
                    continue
                name, block = hit
                if block.get("eventType") == "function-block":
                    for p, (pwhere, cond, path) in sub[1].items():
                        for t, (j, chain) in made.items():
                            # a function that copies picked instances gets the one the caller created
                            if not self.related(p, t) or (not chain and block.get("functionCopyPicked")) \
                                    or (name, t) in warned:
                                continue
                            warned.add((name, t))
                            by = f"action {j} creates {t}" if not chain else \
                                f"action {j} calls {chain[0]}, which creates {t}" \
                                + (f" through {', '.join(chain[1:])}" if len(chain) > 1 else "")
                            through = f" through {', '.join(path)}" if path else ""
                            self.warn(f"{where} action {i}: {name} picks {p}{through} ({cond} in {pwhere}), but {by} "
                                      f"earlier in the same actions, and that new {t} is not among the "
                                      f"instances {name} picks from: until the top-level event or trigger that "
                                      f"runs these actions ends, only Pick by unique ID finds it outside the "
                                      f"event that created it. Set the new {t} up in the event that creates "
                                      f"it, pass its UID to {name} and pick it there by unique ID, or call "
                                      f"{name} from a later top-level event or trigger "
                                      f"({(self.p.rag / 'prompts' / 'pitfalls' / 'creating-objects.md').as_posix()})")
                for t, chain in sub[0].items():
                    made.setdefault(t, (i, [name] + chain))

    # --- uniqueness, project files, addons ----------------------------------------------------
    def check_uniqueness(self) -> None:
        sids, ace_sids, uids = self.sids, self.ace_sids, self.uids
        # Only an object class sid stops the editor
        shared = {s: names for s, names in self.class_sids.items() if len(names) > 1}
        for s, names in sorted(shared.items()):
            self.err(f"{' and '.join(names)} share the sid {s}; the editor stops with \"object class sid "
                     f"already in use\": give all but one a new 15-digit sid no other entry of the project has")
        dup_sids = sorted(({s for s in sids if sids.count(s) > 1} | (set(sids) & set(ace_sids))) - set(shared))
        if dup_sids:
            self.warn(f"duplicate sids: {dup_sids[:5]}{' ...' if len(dup_sids) > 5 else ''}; the editor opens the "
                      f"project; to make them unique, search the project's JSON for each sid and give all but one "
                      f"entry a new 15-digit sid")
        dup_ace_sids = sorted({s for s in ace_sids if ace_sids.count(s) > 1})
        if dup_ace_sids:
            self.warn(f"conditions or actions sharing a sid (pasted in the editor?): "
                      f"{dup_ace_sids[:5]}{' ...' if len(dup_ace_sids) > 5 else ''}")
        # The editor renumbers all but one of the instances that share a uid
        dup_uids = sorted({u for u in uids if uids.count(u) > 1})
        if dup_uids:
            self.err(f"duplicate uids: {dup_uids[:5]}{' ...' if len(dup_uids) > 5 else ''}; the editor gives all "
                     f"but one of them another uid, so a hierarchy link or a Pick by UID written for one may reach "
                     f"the other: give the copies a uid no instance or single-global object type has")

    def check_secrets(self) -> None:
        """A string shaped like a key in what a web export ships, which every player can read."""
        for s, what, shown in c3.secrets_in(c3.shipped_strings(self.p.root, self.p.data, self.sheets)):
            self.warn(f"{s.place}: a string shaped like {what} ({shown}), and a web export ships every string to "
                      f"the players, who can read it. Move the key to a server that the game calls. If it is meant "
                      f"to be public, write {c3.ALLOW} in {s.mark}")

    def check_files_and_addons(self) -> None:
        p = self.p
        root_files = p.data.get("rootFileFolders", {})
        # The editor opens every listed file and stops with "missing file path 'icons\icon-16.png'".
        for kind, directory in ROOT_FILE_FOLDERS.items():
            for name, folder in folder_items(root_files.get(kind, {})):
                fname = name["name"] if isinstance(name, dict) else name
                if not (p.root / directory / folder / fname).exists():
                    shown = (Path(directory) / folder / fname).as_posix()
                    self.err(f"{kind} file {fname} is listed in project.c3proj but {shown} is missing; the editor "
                             f"stops with \"missing file path\". Add the file, or take it out of rootFileFolders")
                if kind in ("sound", "music") and not LOWER(fname).endswith(".webm"):
                    stem = Path(fname).stem
                    self.warn(f"{kind} file {fname} is not WebM Opus (.webm), the format a project's sound and music "
                              f"are in; the editor opens it, and whether it plays depends on the browser. Encode it, "
                              f"ffmpeg -i {fname} -c:a libopus {stem}.webm, and list {stem}.webm with \"type\": "
                              f"\"{AUDIO_TYPE}\", or import the file in the editor, which converts it")
        self.check_scripts(root_files.get("script", {}))
        self.check_ts_defs()
        self.check_unlisted(root_files)

        addon_ids = {a["id"] for a in p.data.get("usedAddons", [])}

        def need_addon(addon_id: str, where: str) -> None:
            if addon_id not in addon_ids:
                self.err(f"{where}: {addon_id} is not listed in usedAddons")

        for name, t in p.types.items():
            need_addon(t["plugin-id"], f"object type {name}")
            for b in t.get("behaviorTypes", []):
                need_addon(b["behaviorId"], f"object type {name}")
            for e in t.get("effectTypes", []):
                need_addon(e.get("effectId", e.get("id", "")), f"object type {name}")
        for name, f in p.families.items():
            for b in f.get("behaviorTypes", []):
                need_addon(b["behaviorId"], f"family {name}")
            for e in f.get("effectTypes", []):
                need_addon(e.get("effectId", e.get("id", "")), f"family {name}")

    def check_scripts(self, scripts: dict) -> None:
        """A script listed as both .ts and .js: Construct runs the .js and ignores the .ts."""
        kinds: dict[str, set[str]] = {}
        shown: dict[str, str] = {}
        for name, folder in folder_items(scripts):
            fname = name["name"] if isinstance(name, dict) else name
            if not isinstance(fname, str):
                continue
            path = (folder / fname).with_suffix("").as_posix()
            kinds.setdefault(LOWER(path), set()).add(LOWER(Path(fname).suffix))
            shown.setdefault(LOWER(path), path)
        for key, suffixes in sorted(kinds.items()):
            if {".ts", ".js"} <= suffixes:
                self.warn(f"scripts/{shown[key]}.ts and scripts/{shown[key]}.js are both listed; Construct runs the "
                          f".js and ignores the .ts, so an edit to the .ts changes nothing. List the .ts alone when "
                          f"Construct compiles the TypeScript, the .js alone when an external editor does")

    def check_ts_defs(self) -> None:
        """scripts/ts-defs/instanceTypes.d.ts, which the editor writes when the user sets up or
        updates TypeScript definitions, without an object type or family the project has now:
        TypeScript checked against it does not know InstanceType.<name>."""
        p = self.p
        defs = p.root / "scripts" / "ts-defs" / "instanceTypes.d.ts"
        if not defs.is_file():
            return
        declared = set(re.findall(r"\w+", defs.read_text(encoding="utf-8", errors="replace")))
        missing = sorted(n for n in (*p.types, *p.families) if n not in declared)
        if missing:
            shown = ", ".join(missing[:5]) + (f" and {len(missing) - 5} more" if len(missing) > 5 else "")
            self.warn(f"scripts/ts-defs/instanceTypes.d.ts does not declare {shown}, so TypeScript checked against "
                      f"it does not know InstanceType.{missing[0]}. Have the editor write them again: "
                      f"{script_command(p.root, 'open_in_editor.py', ' --typescript')}")

    def check_unlisted(self, root_files: dict) -> None:
        """A file in a folder of the project that project.c3proj does not list: the editor
        reads only what the project lists and ignores the rest."""
        p = self.p
        for kind in RESOURCE_FOLDERS:
            folder = p.root / kind
            if not folder.is_dir():
                continue
            listed = {LOWER(n) for n, _ in folder_items(p.data.get(kind) or {}) if isinstance(n, str)}
            for f in sorted(folder.rglob("*.json")):
                rel = f.relative_to(folder)
                if f.name.endswith(".uistate.json") or "uistate" in rel.parts[:-1] or LOWER(f.stem) in listed:
                    continue
                self.warn(f"{kind}/{rel.as_posix()} is not listed in project.c3proj, so the editor ignores it: if "
                          f"the project uses it, add \"{f.stem}\" to the \"{kind}\" items")
        for kind in UNLISTED_ROOT_FILES:
            directory = ROOT_FILE_FOLDERS[kind]
            folder = p.root / directory
            if not folder.is_dir():
                continue
            listed = {LOWER((sub / (n["name"] if isinstance(n, dict) else n)).as_posix())
                      for n, sub in folder_items(root_files.get(kind) or {})
                      if isinstance(n, str) or isinstance(n, dict) and isinstance(n.get("name"), str)}
            for f in sorted(folder.rglob("*")):
                rel = f.relative_to(folder)
                if f.is_file() and not f.name.endswith(".uistate.json") and LOWER(rel.as_posix()) not in listed:
                    self.warn(f"{directory}/{rel.as_posix()} is not listed in project.c3proj, so the editor ignores "
                              f"it: if the project uses it, import it in the editor, or add an entry for "
                              f"\"{f.name}\" to the rootFileFolders \"{kind}\" items, written like the entries the "
                              f"editor saved there")

    def report(self) -> int:
        """Warnings, then problems, then the line that says how it went. A report
        longer than --limit prints what fits of each, warnings in at most a third
        of it when there are problems too, the problems in the rest, and says how
        many it left out."""
        p = self.p
        warnings, errors = [f"warning: {w}" for w in p.findings.warnings], p.findings.errors
        # The room kept for the cut notes and the last line.
        closing = 300 + (0 if errors else len(self.ok_line())) + (len(c3.REVIEW) if self.review else 0)
        room = max(self.limit - closing, 3)
        cut = self.limit and c3.fitting(warnings + errors, room) < len(warnings + errors)
        shares = (0, 0)     # 0 is no limit
        if cut:
            of_warnings = room // 3 if errors else room
            used = sum(len(w) + 1 for w in warnings[:max(c3.fitting(warnings, of_warnings), 1)])
            shares = (of_warnings, max(room - used, 1))
        for lines, share, rest in ((warnings, shares[0], "warnings"),
                                   (errors, shares[1], "problems; fix these and run again")):
            fit = max(c3.fitting(lines, share), 1)
            if lines:
                print("\n".join(lines[:fit]))
            if fit < len(lines):
                print(f"... and {len(lines) - fit} more {rest} (--limit 0 prints all)")
        if self.review:
            print(c3.REVIEW)
        if errors:
            print(f"{len(errors)} problem(s)")
            return 1
        print(self.ok_line(then_open=not self.review))
        return 0

    def ok_line(self, then_open: bool = True) -> str:
        """An agent takes the last line of a passing check for the end of the
        work, so the line names the step after it. edit_sheet.py prints it without:
        a plan is one step of the work, not its end."""
        p = self.p
        line = (f"ok: {len(p.types)} object types, {len(p.families)} families, {len(self.layouts)} layouts, "
                f"{len(self.sheets)} sheets, {len(self.sids) + len(self.ace_sids)} sids, {len(self.uids)} uids, "
                f"{len(self.functions)} functions, {len(self.custom_actions)} custom actions")
        scripts = p.scripts_summary()
        if scripts:
            line += f"; scripts, which this check does not run or type-check: {scripts}"
        if not then_open:
            return line
        if scripts:
            line += "".join(f"; {clause}" for clause in copied_sizes(p, self.layouts))
            line += (f"; when you write or change a script, look up each API it calls: "
                     f"{script_command(p.root, 'lookup_script_api.py')} NAME")
        return (f"{line}; next, review the design of the sheets and act on what it prints, "
                f"{script_command(p.root, 'review_design.py')}, then open and preview it in the editor, which also "
                f"reads the expressions and runs the events: {open_command(p.root)}")


def copied_sizes(p: c3.Project, layouts: dict[str, dict]) -> list[str]:
    """A clause for each script whose code writes both the width and the height of a layout as
    numbers, for the first such layout: the numbers, and what to read at run time in their place.
    A size copied into a script is wrong when the layout is resized. An instance's size is named
    only beside its layout's, because scripts also write such numbers as offsets and counts.
    Evidence: docs/decisions/project-tools-skill.md."""
    def size(holder: dict) -> tuple[float, float] | None:
        w, h = holder.get("width"), holder.get("height")
        return (float(w), float(h)) if JSON_TYPES["number"](w) and JSON_TYPES["number"](h) and w > 0 and h > 0 \
            else None

    def written(numbers: dict[float, int], wh: tuple[float, float]) -> bool:
        # A square is written when its side appears twice
        return numbers.get(wh[0], 0) >= 2 if wh[0] == wh[1] else wh[0] in numbers and wh[1] in numbers

    def shown(wh: tuple[float, float]) -> str:
        return f"width {wh[0]:.10g}, height {wh[1]:.10g}"

    out = []
    for path in p.script_files():
        numbers = p.script_numbers(path)
        for name, layout in layouts.items():
            wh = size(layout) if isinstance(layout, dict) else None
            if not wh or not written(numbers, wh):
                continue
            objects: dict[str, tuple[float, float]] = {}
            for layer, _ in c3.layers_of(layout.get("layers", [])):
                for inst in layer.get("instances", []):
                    of = size(inst.get("world") or {}) if isinstance(inst, dict) else None
                    if of and written(numbers, of):
                        objects.setdefault(str(inst.get("type")), of)
            named = list(objects.items())[:3]
            held = f"{path.as_posix()} writes these sizes as numbers: layout {name!r} ({shown(wh)})"
            held += "".join(f", {obj} in it ({shown(of)})" for obj, of in named)
            read = ("Replace the layout's numbers with runtime.layout.width and runtime.layout.height, and each "
                    "object's numbers with the width and height of its instance") if named \
                else "Replace them with runtime.layout.width and runtime.layout.height"
            out.append(f"{held}. {read}. A number copied from the layout is wrong when the layout"
                       f"{' or an instance' if named else ''} is resized")
            break
    return out


def script_command(root: Path, name: str, flags: str = "") -> str:
    """A script of this folder run on root, as it runs from the current directory."""
    def quoted(s: str) -> str:
        return f'"{s}"' if " " in s else s
    script = Path(__file__).resolve().parent / name
    cwd = Path.cwd()
    shown = script.relative_to(cwd).as_posix() if script.is_relative_to(cwd) else script.as_posix()
    where = "" if c3.find_project(None) == root.resolve() else f" --project {quoted(root.resolve().as_posix())}"
    return f"python {quoted(shown)}{where}{flags}"


def open_command(root: Path) -> str:
    """open_in_editor.py --preview for root, as it runs from the current directory."""
    return script_command(root, "open_in_editor.py", " --preview")


def helpers_behind(root: Path, rag: Path) -> str | None:
    """A sentence when the helpers of the project's generator are an older version than the
    skill's, with the command that refreshes them; a generator whose markers are broken is
    named too, since nothing can refresh it. Edits there, with nothing newer to take, and a
    generator from before the markers say nothing. The helpers edited there are named when the
    clone's history holds the template they were copied from, as install.py names them."""
    h = c3.generator_helpers(root)
    command = script_command(root, "install.py", " --helpers-only")
    if h.state == "broken":
        return f"{c3.GENERATOR}: {h.detail}; until then the skill cannot refresh its helpers"
    if h.state == "older":
        have, want = c3.versions(h.have, h.want)
        return (f"{c3.GENERATOR}: its helpers, between the markers, are the skill's of {have}, and the skill's are "
                f"now of {want}; refresh them, which leaves the lines outside the markers as they are: {command}, "
                f"then run python {c3.GENERATOR}")
    if h.state == "edited" and h.have.stamp != h.want.stamp and h.have.version <= h.want.version:
        have, want = c3.versions(h.have, h.want)
        copied = c3.copied_template(rag, h.have.stamp)
        lost = c3.unkept_helpers(root, copied=copied) if copied else None
        changed = f" ({', '.join(n for n, _, _ in lost)})" if isinstance(lost, list) and lost else ""
        return (f"{c3.GENERATOR}: its helpers, between the markers, are the skill's of {have} with edits made "
                f"there, and the skill's are now of {want}. Copy each helper changed there{changed} below "
                f"the end marker, where a def of the same name replaces the one between the markers, then run "
                f"{command} --replace-edited-helpers and python {c3.GENERATOR}")
    return None


def block_behind(root: Path) -> str | None:
    """A sentence when the Construct 3 block of the project's instruction file is an older version
    than the skill's, with the command that refreshes it, as helpers_behind says it of the generator.
    An edited block with a newer version to take gets the command that lists the edits, and a block
    whose markers are broken is named, since nothing can refresh it. Edits with nothing newer to
    take, and an instruction file without a block that install.py wrote, say nothing."""
    b = c3.instruction_block(root)
    command = script_command(root, "install.py", " --block-only")
    if b.state == "broken":
        return f"{b.file}: {b.detail}; until then the skill cannot refresh its Construct 3 block"
    if b.state == "older":
        have, want = c3.versions(b.have, b.want)
        before = "" if b.have.marked else ", written before the block had markers,"
        return (f"{b.file}: its Construct 3 block is the skill's of {have}{before} and the skill's is now of {want}; "
                f"refresh it, which keeps the lines that name a clone's folder and every line outside the block: "
                f"{command}")
    if b.state == "edited" and b.have.stamp != b.want.stamp and b.have.version <= b.want.version:
        have, want = c3.versions(b.have, b.want)
        return (f"{b.file}: its Construct 3 block is the skill's of {have} with edits made between its markers, and "
                f"the skill's is now of {want}. {command} lists the lines that differ; move the project's own below "
                f"the end marker, then run it with --replace-edited-block")
    return None


def main() -> int:
    ap = c3.argument_parser(
        "Check a Construct 3 folder project against the Construct3-RAG schemas and the rules the editor applies "
        "when it opens or previews a project. Every finding names its place, as 'sheet Game event 15 action 2' "
        "with the editor's event number, and says what to write where it can.",
        "examples:\n"
        "  python scripts/check_project.py\n"
        "  python scripts/check_project.py --project ../OtherGame\n\n"
        "  python scripts/check_project.py --style        # a project the agent wrote\n"
        "  python scripts/check_project.py --review       # a project someone asked about\n\n"
        "exit codes: 0 no errors (warnings do not fail the run), 1 findings or project/clone not found,\n"
        "2 a project file lacks a key the editor always writes and the run stopped there")
    ap.add_argument("--style", action="store_true",
                    help="also warn where a sheet departs from the authoring style of the official examples: "
                         f"{STYLE_RUN} or more actions in a row without a comment action, a top-level event with "
                         f"no comment above it, an event none of whose case sub-events has a comment above it, "
                         f"Every tick beside another condition, "
                         f"sub-events {STYLE_TREE} levels deep whose leaves all call one function, "
                         f"{STYLE_LADDER} or more sibling events of the same conditions and actions with other "
                         "values, Every N seconds taking N off a variable, a countdown the Timer "
                         "behavior keeps, chooseindex on a condition, sibling events dispatching on find of one "
                         "text, and mid through two text literals. For a project the agent wrote; edit_sheet.py "
                         "refuses a plan whose new events raise the first four and warns on the other six")
    ap.add_argument("--review", action="store_true",
                    help="for a project someone else wrote and asked about: leave out the parameters the editor "
                         "fills, end without the next steps of writing a project, and say above the last line "
                         "what a review reports")
    args = ap.parse_args()
    c3.utf8_output()
    findings = c3.Findings()
    c3.stop_with_a_sentence("check_project.py", findings)
    project = c3.Project.open(args, findings)
    if c3.offline():
        print(f"note: CONSTRUCT3_RAG_OFFLINE is 1, so the clone at {project.rag} was not compared with its upstream")
    # Stale tools are a problem to fix first: a warning above a passing check's last line goes unread
    behind = c3.clone_behind(project.rag)
    if behind:
        line, agent_updates = behind
        (findings.err if agent_updates else findings.warn)(line)
    drift = None if behind and behind[1] else c3.skill_drift(project.rag)     # the update above refreshes the copy too
    if drift:
        findings.err(drift)
    helpers = helpers_behind(project.root, project.rag)
    if helpers:
        findings.warn(helpers)
    block = block_behind(project.root)
    if block:
        findings.warn(block)
    return Checker(project, args.limit, style=args.style, review=args.review).run()


if __name__ == "__main__":
    sys.exit(main())

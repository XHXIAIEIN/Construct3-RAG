"""Plans that play an eval case's game in the editor's preview, and the verdicts read from it.

    python evals/play_cases.py CASE
    python evals/play_cases.py CASE --project FOLDER [--out FOLDER] [--release rNNN] [--browser EXE]

A case whose request changes what the game does has a plan of
scripts/preview_project.py here. The first form prints the plan as JSON.
The second plays it on one project and writes plan.json, result.json and
the screenshots into --out (default: a new folder under the system's
temporary directory). It prints the verdict and the evidence of each check.
Use it to try a plan on a project that does what the case asks, and on the
case's fixture. grade.py --play plays the plan of every run.

A check is a js step whose note starts with "check: " and whose code returns
{ok, said}. It reads the running game. Input goes in through the plan's tap
and key steps. A tick2 listener, installed by the first js step, records
what changes between two samples (vars.watch, vars.seen). A setup step that
fails stops the plan, and every check after it fails as not reached. A few
checks read the plan's screenshots instead (the POST table). Every plan also
checks that the game logged no runtime error. Where the run chooses the name
of an object or a variable, the plan finds it by what it does: the UI
instance that widens when a coin is collected is the fill.

exit codes: 0 every check passed or the plan was printed, 1 a check failed or
the plan did not play, 2 no plan for CASE
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
PREVIEW = SKILL / "scripts" / "preview_project.py"
CHECK = "check: "
NO_ERROR = "The game logs no runtime error while the plan plays"
# The browser profile of every plan: short, since the editor's files under a deep path stall the preview.
PROFILE = Path(tempfile.gettempdir()) / "c3-eval-profile"
# Seconds the editor gets to load and start the preview, on top of what the plan's steps take.
START = 150

# Installed by the first js step of every plan; idempotent. vars.watch maps a name to a function read after
# every tick's events (tick2), vars.seen keeps each change with its wallTime. vars.h holds the helpers.
HELPERS = r"""if (!vars.h) {
  const h = vars.h = {};
  vars.starts = 0; vars.startAt = []; vars.startGame = [0]; vars.endAt = []; vars.endGame = [];
  vars.watch = {}; vars.seen = {}; vars.tapped = new WeakSet(); vars.taps = [];
  runtime.addEventListener('afteranylayoutstart', () => {
    vars.starts++; vars.startAt.push(runtime.wallTime); vars.startGame.push(runtime.gameTime); });
  runtime.addEventListener('beforeanylayoutend', () => { vars.endAt.push(runtime.wallTime); vars.endGame.push(runtime.gameTime); });
  runtime.addEventListener('tick2', () => {
    for (const [k, f] of Object.entries(vars.watch)) {
      let v;
      try { v = f(); } catch (e) { v = 'error: ' + e.message; }
      const s = vars.seen[k] || (vars.seen[k] = []), j = JSON.stringify(v), last = s[s.length - 1];
      if (!last || last.j !== j) s.push({v, j, at: runtime.wallTime});
    }
  });
  h.now = () => runtime.wallTime;
  h.round = (n, d = 10) => Math.round(n * d) / d;
  h.box = i => { const b = i.getBoundingBox();
    return {l: h.round(b.left), t: h.round(b.top), r: h.round(b.right), b: h.round(b.bottom)}; };
  h.css = i => { const b = i.getBoundingBox(), [l, t] = i.layer.layerToCssPx(b.left, b.top),
    [r, bo] = i.layer.layerToCssPx(b.right, b.bottom);
    return {l: h.round(l), t: h.round(t), r: h.round(r), b: h.round(bo)}; };
  h.all = () => [...new Map(Object.values(runtime.objects).flatMap(t => t.getAllInstances())
    .map(i => [i.uid, i])).values()];
  h.ui = () => h.all().filter(i => i.layer && /^(ui|hud)$/i.test(i.layer.name));
  h.isText = i => typeof i.text === 'string';
  h.first = name => runtime.objects[name] ? runtime.objects[name].getFirstInstance() : null;
  h.text = name => { const i = h.first(name); return i && h.isText(i) ? i.text : null; };
  h.count = name => runtime.objects[name] ? runtime.objects[name].getAllInstances().length : 0;
  h.since = (k, t) => (vars.seen[k] || []).filter(e => e.at > t);
  // What changed after t, from the value at t: the watch's first sample is no change.
  h.changes = (k, t) => { let last = h.at(k, t); return h.since(k, t).filter(e => {
    const moved = JSON.stringify(e.v) !== JSON.stringify(last); last = e.v; return moved; }); };
  h.at = (k, t) => { let v; for (const e of vars.seen[k] || []) { if (e.at <= t) v = e.v; else break; } return v; };
  h.fresh = type => { const c = runtime.objects[type].getAllInstances().find(c => !vars.tapped.has(c));
    if (c) { vars.tapped.add(c); vars.tapAt = runtime.wallTime; vars.taps.push(runtime.wallTime); vars.before = vars.starts; }
    return c; };
  // A point of a fresh coin that no other coin covers, near its middle, so that a touch picks that one alone.
  h.spot = type => { const c = h.fresh(type); if (!c) return c;
    const others = runtime.objects[type].getAllInstances().filter(o => o !== c).map(o => o.getBoundingBox()), b = c.getBoundingBox();
    for (const [fx, fy] of [[.5, .5], [.3, .5], [.7, .5], [.5, .3], [.5, .7], [.35, .35], [.65, .65], [.35, .65], [.65, .35]]) {
      const x = b.left + b.width * fx, y = b.top + b.height * fy;
      if (!others.some(o => x >= o.left && x <= o.right && y >= o.top && y <= o.bottom)) return {x, y, layer: c.layer.name}; }
    return c; };
  h.numbers = () => { const out = {};
    for (const k in runtime.globalVars) if (typeof runtime.globalVars[k] === 'number') out['g:' + k] = runtime.globalVars[k];
    for (const i of h.ui()) for (const k in (i.instVars || {}))
      if (typeof i.instVars[k] === 'number') out['i:' + i.objectType.name + '.' + k] = i.instVars[k];
    return out; };
  h.setNumber = (key, value) => { const [kind, rest] = [key.slice(0, 1), key.slice(2)];
    if (kind === 'g') { runtime.globalVars[rest] = value; return true; }
    const [type, name] = rest.split('.'), i = h.first(type); if (!i) return false; i.instVars[name] = value; return true; };
  h.end = () => vars.endAt.find(t => t > vars.tapAt);
  h.lastNumber = s => { const m = /(-?\d+(?:\.\d+)?)(?!.*\d)/.exec(s || ''); return m ? +m[1] : null; };
  h.player = s => { const m = /(?:player|p)\s*([12])/i.exec(s || ''); return m ? +m[1] : null; };
}
return true;"""


def js(*lines: str) -> dict:
    return {"js": list(lines)}


def check(text: str, *lines: str) -> dict:
    """A step whose code returns {ok, said}; an exception it throws fails the check, not the plan."""
    return {"js": ["const h = vars.h;", "try {", *lines, "} catch (e) { return {ok: false, said: 'the check threw ' + e}; }"],
            "note": CHECK + text}


def tap(kind: str = "Coin") -> dict:
    return {"tap": {"js": f"vars.h.spot('{kind}')"}}


def collect(most: int = 10) -> list[dict]:
    """Tap every coin of the round, however many it dealt, then wait for the next round: a tap with no coin
    left presses an empty corner."""
    return [*[{"tap": {"js": "vars.h.spot('Coin') || {x: 4, y: 4}"}} for _ in range(most)], *next_round()]


def ready(expression: str) -> list[dict]:
    return [{"until": expression, "timeout": 20}, js(HELPERS)]


# A second to settle before the first tap: a layout that restarts itself on its first ticks has done so by then.
COINS = [*ready("runtime.objects.Coin && runtime.objects.Coin.getAllInstances().length > 0"), {"wait": 1.0}]


def next_round() -> list[dict]:
    """Wait for the layout to start again after the last tap, and for the new round's coins to settle."""
    return [{"until": "vars.starts > vars.before", "timeout": 10}, {"wait": 0.8}]


# --- coins game ------------------------------------------------------------------------------------------

TIME = r"(s => { const m = /time\D{0,6}?(-?\d+)/i.exec(s || ''); return m ? +m[1] : null; })"


def add_countdown() -> dict:
    sizes = js("(vars.sizes = vars.sizes || []).push(...runtime.objects.Coin.getAllInstances()"
               ".map(c => ({value: c.instVars.value, w: vars.h.round(c.width)}))); return vars.sizes.length")
    return {"touch": True, "steps": [
        *COINS,
        js("vars.watch.text = () => vars.h.text('ScoreText'); return true"),
        check("The score text shows the score and the time",
              "let s = '';",
              "for (let n = 0; n < 20; n++) { s = h.text('ScoreText') || ''; if (/time\\D{0,6}?\\d/i.test(s)) break; await wait(0.1); }",
              "return {ok: /time\\D{0,6}?\\d/i.test(s) && (s.match(/\\d+/g) || []).length >= 2, said: `ScoreText says ${JSON.stringify(s)}`};"),
        check("The time shown loses one a second",
              f"const t = () => ({TIME})(h.text('ScoreText'));",
              "const a = t(); await wait(3); const b = t();",
              "return {ok: a >= 26 && a <= 30 && a - b >= 2 && a - b <= 4, said: `time ${a}, 3 s later ${b}`};"),
        check("The layout restarts when the time reaches 0, and not before",
              "const before = vars.starts, began = vars.startGame[vars.startGame.length - 1];",
              "runtime.timeScale = 6;",
              "try { for (let n = 0; n < 120 && vars.starts === before; n++) await wait(0.1); } finally { runtime.timeScale = 1; }",
              "if (vars.starts === before) return {ok: false, said: 'no restart in 72 s of game time'};",
              "const lasted = vars.endGame[vars.endGame.length - 1] - began, end = vars.endAt[vars.endAt.length - 1];",
              # The tick that ends the layout starts the next one, so its sample shows the new layout's text.
              f"const shown = ({TIME})(h.at('text', end - 1e-6));",
              "return {ok: lasted >= 28 && lasted <= 32.5 && shown !== null && shown <= 1, "
              "said: `the layout lasted ${lasted.toFixed(1)} s of game time; the time shown last was ${shown}`};"),
        check("After the restart the countdown starts over from 30",
              "await wait(0.5); const s = h.text('ScoreText');",
              f"const t = ({TIME})(s);",
              "return {ok: t !== null && t >= 28 && t <= 30, said: `0.5 s after the restart ScoreText says ${JSON.stringify(s)}`};"),
        {"wait": 0.3}, sizes, *collect(), sizes, *collect(), sizes,
        check("A coin worth 5 is 1.5 times the width of a coin worth 1",
              "const s = vars.sizes, ones = s.filter(c => c.value == 1).map(c => c.w), fives = s.filter(c => c.value == 5).map(c => c.w);",
              "if (!ones.length || !fives.length) return {ok: false, said: `coins read: ${JSON.stringify(s)}`};",
              "const base = [...ones].sort((a, b) => a - b)[Math.floor(ones.length / 2)];",
              "const bad = s.filter(c => Math.abs(c.w - base * (c.value == 5 ? 1.5 : 1)) > 3);",
              "return {ok: !bad.length, said: `widths of coins worth 1: ${ones}; worth 5: ${fives}`};"),
    ]}


def fix_load_errors() -> dict:
    return {"touch": True, "steps": [
        *COINS,
        js("vars.coin = runtime.objects.Coin.getFirstInstance(); vars.uid = vars.coin.uid;",
           "vars.value = vars.coin.instVars.value; vars.score0 = vars.h.lastNumber(vars.h.text('ScoreText')); vars.w0 = vars.h.round(vars.coin.width);",
           "vars.watch.coin = () => { const c = runtime.getInstanceByUid(vars.uid); return c ? vars.h.round(c.width) : null; };",
           "return {value: vars.value, score: vars.score0}"),
        {"tap": {"js": "vars.tapped.add(vars.coin), vars.tapAt = vars.h.now(), vars.coin"}},
        check("A tapped coin adds its value to the score text",
              "await wait(0.6); const s = h.text('ScoreText');",
              "return {ok: h.lastNumber(s) === vars.score0 + vars.value, said: `score ${vars.score0}, a coin worth ${vars.value}, then ScoreText says ${JSON.stringify(s)}`};"),
        check("The tapped coin shrinks and is gone within 1.5 s",
              "await wait(0.9); const seen = h.since('coin', vars.tapAt).map(e => e.v), w = seen.filter(v => v !== null);",
              "const start = vars.w0, gone = seen.includes(null);",
              "return {ok: gone && w.some(v => v < start * 0.5), said: `width ${start}, then ${w.slice(0, 10).join(', ')}${w.length > 10 ? ' ...' : ''}; gone: ${gone}`};"),
        check("The next round starts after the last coin",
              "for (let n = 0; n < 40 && vars.starts < 1; n++) await wait(0.1); await wait(0.6);",
              "return {ok: vars.starts >= 1 && h.count('Coin') === 3, said: `${vars.starts} restart(s); ${h.count('Coin')} coin(s) dealt after it`};"),
    ]}


def countdown_between_rounds() -> dict:
    return {"touch": True, "steps": [
        *COINS,
        js("vars.watch.text = () => vars.h.text('ScoreText'); return true"),
        tap(), *next_round(),
        js("const end = vars.h.end(), seen = vars.h.since('text', vars.tapAt).filter(e => e.at < end);",
           "vars.counts = seen.filter(e => /next\\s*round/i.test(e.v || '')).map(e => ({n: vars.h.lastNumber(e.v), at: e.at}))",
           "  .filter((e, i, all) => i === 0 || e.n !== all[i - 1].n);",
           "return {texts: seen.map(e => e.v), counts: vars.counts.map(e => e.n)}"),
        check("After the last coin the score text counts Next round 3, 2, 1",
              "const n = vars.counts.map(e => e.n), i = n.findIndex((v, k) => v === 3 && n[k + 1] === 2 && n[k + 2] === 1);",
              "vars.three = i; return {ok: i >= 0, said: `Next round texts counted ${n.join(', ') || 'nothing'}`};"),
        check("The numbers change about a second apart",
              "if (vars.three < 0) return {ok: false, said: 'no 3, 2, 1 to time'};",
              "const c = vars.counts, a = c[vars.three + 1].at - c[vars.three].at, b = c[vars.three + 2].at - c[vars.three + 1].at;",
              "return {ok: a >= 0.75 && a <= 1.3 && b >= 0.75 && b <= 1.3, said: `3 to 2 in ${a.toFixed(2)} s, 2 to 1 in ${b.toFixed(2)} s`};"),
        check("The next round starts about a second after 1 shows",
              "if (vars.three < 0) return {ok: false, said: 'no 1 shown'};",
              "const d = vars.h.end() - vars.counts[vars.three + 2].at;",
              "return {ok: d >= 0.7 && d <= 1.5, said: `the layout ended ${d.toFixed(2)} s after 1 showed`};"),
        check("The next round deals 3 coins",
              "return {ok: h.count('Coin') === 3, said: `${h.count('Coin')} coin(s) after the restart`};"),
    ]}


def fix_next_round() -> dict:
    return {"touch": True, "steps": [
        *COINS, tap(), *next_round(),
        check("The next round starts 2.5 to 5 s after the last coin is tapped",
              "const d = vars.h.end() - vars.tapAt;",
              "return {ok: d >= 2.5 && d <= 5, said: `the layout ended ${d.toFixed(2)} s after the tap`};"),
        check("The next round deals 3 coins",
              "return {ok: h.count('Coin') === 3, said: `${h.count('Coin')} coin(s) after the restart`};"),
    ]}


def turns(limit: bool = False) -> dict:
    """In round 2: a collect passes the turn once, the turn then holds still, and the next collect passes it back.
    With a limit, first in round 1: without a tap the turn passes once about every 5 seconds, and the seconds
    shown count down."""
    steps = [*COINS, js("vars.watch.turn = () => vars.h.player(vars.h.text('ScoreText'));",
                        "vars.watch.text = () => vars.h.text('ScoreText'); return vars.h.text('ScoreText')"), {"wait": 0.3}]
    if limit:
        steps += [
            check("Without a tap the turn passes to the other player about every 5 s",
                  "const t0 = h.now(), first = h.player(h.text('ScoreText'));",
                  "for (let n = 0; n < 140 && h.changes('turn', t0).length < 2; n++) await wait(0.1);",
                  "await wait(0.6); const ch = h.changes('turn', t0);",
                  "if (ch.length < 2) return {ok: false, said: `turn ${first}, then ${ch.map(e => e.v).join(', ') || 'no change'} in 14 s`};",
                  "const gap = ch[1].at - ch[0].at, flips = ch[0].v === 3 - first && ch[1].v === first;",
                  "const quick = ch.slice(2).filter(e => e.at - ch[1].at < 0.5).length;",
                  "vars.turnAt = ch[1].at;",
                  "return {ok: flips && gap >= 4.5 && gap <= 6 && !quick, said: `turn ${first}, then ${ch.slice(0, 4).map(e => `${e.v} at +${(e.at - t0).toFixed(1)} s`).join(', ')}`};"),
            check("The seconds shown count down",
                  "const sec = s => { const m = /(\\d+(?:\\.\\d+)?)\\s*(?:s\\b|sec)/i.exec(s || '') || /(\\d+)(?!.*\\d)/.exec(s || ''); return m ? +m[1] : null; };",
                  "const a = sec(h.text('ScoreText')); await wait(2); const b = sec(h.text('ScoreText'));",
                  "return {ok: a !== null && b !== null && a - b >= 1 && a - b <= 3, said: `${a}, 2 s later ${b}: ${JSON.stringify(h.text('ScoreText'))}`};"),
        ]
    steps += [
        tap(), *next_round(),
        js("vars.turn0 = vars.h.at('turn', vars.h.now()); return vars.turn0"), tap(), {"wait": 0.8},
        check("A collected coin passes the turn to the other player once",
              "const ch = h.changes('turn', vars.tapAt).map(e => e.v), now = h.at('turn', h.now());",
              "return {ok: ch.length === 1 && now === 3 - vars.turn0, said: `turn ${vars.turn0}; after the collect ${ch.slice(0, 8).join(', ') || 'no change'}${ch.length > 8 ? ` ... (${ch.length} changes)` : ''}`};"),
        check("Without input the turn shown holds still",
              "const t = h.now(); await wait(1); const ch = h.changes('turn', t), now = h.at('turn', h.now());",
              "return {ok: (now === 1 || now === 2) && !ch.length, said: `turn ${now}; ${ch.length} change(s) in 1 s; ScoreText says ${JSON.stringify(h.text('ScoreText'))}`};"),
        js("vars.turn1 = vars.h.at('turn', vars.h.now()); return vars.turn1"), tap(), {"wait": 0.8},
        check("The next collected coin passes it back",
              "const ch = h.changes('turn', vars.tapAt).map(e => e.v), now = h.at('turn', h.now());",
              "return {ok: ch.length === 1 && now === 3 - vars.turn1, said: `turn ${vars.turn1}; after the collect ${ch.slice(0, 8).join(', ') || 'no change'}`};"),
    ]
    return {"touch": True, "steps": steps}


LEFT = "(() => { const t = vars.h.all().find(i => vars.h.isText(i) && /left/i.test(i.text)); return t ? t.text : null; })()"


def readable_on_a_dark_background() -> dict:
    def shows(n: int, text: str) -> dict:
        return check(text, f"const s = {LEFT}, n = h.lastNumber(s);",
                     f"return {{ok: n === {n}, said: `the label says ${{JSON.stringify(s)}}; ${{h.count('Coin')}} coin(s) left`}};")
    return {"touch": True, "steps": [
        *COINS, tap(), *next_round(),
        shows(3, "In round 2 the Left label shows the 3 coins dealt"), tap(), {"wait": 1.0},
        shows(2, "After a collect it shows one less"), tap(), {"wait": 1.0},
        shows(1, "And one less again after the next"),
    ]}


HUD_VIEW = (2340, 1080)     # wider than the project's 16:9, so a corner of the screen is not a corner of the layout


def lay_out_the_hud() -> dict:
    w, h = HUD_VIEW
    return {"viewport": [w, h], "touch": True, "steps": [
        *ready("runtime.objects.ScoreText && runtime.objects.ScoreText.getFirstInstance()"), {"wait": 0.5},
        js("vars.hud = vars.h.ui().map(i => ({type: i.objectType.name, text: vars.h.isText(i) ? i.text : null, box: vars.h.css(i)}));",
           "return vars.hud"),
        check("Every box on the UI layer lies inside the window",
              f"const out = vars.hud.filter(i => i.box.l < -1 || i.box.t < -1 || i.box.r > {w} + 1 || i.box.b > {h} + 1);",
              f"return {{ok: vars.hud.length > 0 && !out.length, said: out.length ? `outside {w}x{h}: ${{JSON.stringify(out)}}` : `${{vars.hud.length}} boxes inside {w}x{h}`}};"),
        check("No two boxes on the UI layer overlap",
              "const inside = (a, b) => a.l >= b.l - 1 && a.t >= b.t - 1 && a.r <= b.r + 1 && a.b <= b.b + 1;",
              "const hits = [];",
              "vars.hud.forEach((a, n) => vars.hud.slice(n + 1).forEach(b => {",
              "  const x = Math.min(a.box.r, b.box.r) - Math.max(a.box.l, b.box.l), y = Math.min(a.box.b, b.box.b) - Math.max(a.box.t, b.box.t);",
              "  const label = (a.text !== null && b.text === null && inside(a.box, b.box)) || (b.text !== null && a.text === null && inside(b.box, a.box));",
              "  if (x > 1 && y > 1 && !label) hits.push(`${a.type} and ${b.type}`); }));",
              "return {ok: !hits.length, said: hits.length ? `overlapping: ${hits.join('; ')}` : 'no overlap'};"),
        check("The timer sits in the top-right corner of the window",
              "const t = vars.hud.find(i => i.text !== null && /time/i.test(i.text));",
              f"return {{ok: !!t && t.box.r >= {w - 96} && t.box.t <= 96, said: t ? `${{t.type}} ${{JSON.stringify(t.box)}} in a {w}x{h} window` : 'no text on the UI layer says Time'}};"),
        check("The pause button sits in the bottom-right corner of the window",
              "const b = vars.hud.find(i => i.text === null && /pause|button|btn/i.test(i.type));",
              f"return {{ok: !!b && b.box.r >= {w - 96} && b.box.b >= {h - 96}, said: b ? `${{b.type}} ${{JSON.stringify(b.box)}} in a {w}x{h} window` : 'no button on the UI layer'}};"),
        check("The lives sit at the top of the window, centred",
              "const l = vars.hud.filter(i => i.text === null && !/pause|button|btn/i.test(i.type));",
              "if (!l.length) return {ok: false, said: 'no sprite on the UI layer besides the button'};",
              "const left = Math.min(...l.map(i => i.box.l)), right = Math.max(...l.map(i => i.box.r)), top = Math.min(...l.map(i => i.box.t));",
              f"const off = (left + right) / 2 - {w / 2};",
              f"return {{ok: Math.abs(off) <= {w * 0.02} && top <= 96, said: `${{[...new Set(l.map(i => i.type))]}} from x ${{left}} to ${{right}}, ${{off.toFixed(0)}} px off centre, top ${{top}}`}};"),
        check("The score text stays at the top left of the window",
              "const s = vars.hud.find(i => i.type === 'ScoreText');",
              "return {ok: !!s && s.box.l <= 96 && s.box.t <= 160, said: s ? `ScoreText ${JSON.stringify(s.box)}` : 'no ScoreText'};"),
    ]}


# The UI instances' boxes, by uid with their type; the fill is the one that widens when hp goes up.
UI_BOXES = "() => Object.fromEntries(vars.h.ui().map(i => [i.uid, {type: i.objectType.name, ...vars.h.box(i)}]))"

FIND_FILL = r"""const start = vars.h.at('ui', vars.tapAt), end = vars.h.at('ui', vars.h.end() - 0.02) || {};
vars.fill = null; vars.hp = null;
for (const [uid, a] of Object.entries(start || {})) {
  const b = end[uid];
  if (b && b.r - b.l > a.r - a.l + 1 && (!vars.fill || b.r - b.l - (a.r - a.l) > vars.fill.w1 - vars.fill.w0))
    vars.fill = {uid: +uid, type: a.type, w0: a.r - a.l, w1: b.r - b.l};
}
const n0 = vars.h.at('numbers', vars.tapAt) || {}, n1 = vars.h.at('numbers', vars.h.end() - 0.02) || {};
vars.hp = Object.keys(n0).find(k => n0[k] === 40 && n1[k] === 50) || null;
if (vars.fill) {
  const samples = vars.h.since('ui', vars.tapAt - 0.01).filter(e => e.at < vars.h.end()).map(e => e.v);
  const boxes = samples.map(s => s[vars.fill.uid]).filter(Boolean);
  vars.fill.widths = [...new Set(boxes.map(b => vars.h.round(b.r - b.l)))];
  const changes = vars.h.since('ui', vars.tapAt).filter(e => e.at < vars.h.end() && e.v[vars.fill.uid])
    .filter((e, i, all) => i === 0 || e.v[vars.fill.uid].r - e.v[vars.fill.uid].l !== all[i - 1].v[vars.fill.uid].r - all[i - 1].v[vars.fill.uid].l);
  vars.fill.span = changes.length > 1 ? changes[changes.length - 1].at - changes[0].at : 0;
  const last = end[vars.fill.uid];
  const frame = Object.entries(end).find(([uid, f]) => +uid !== vars.fill.uid
    && f.l <= last.l + 1 && f.t <= last.t + 1 && f.r >= last.r - 1 && f.b >= last.b - 1);
  vars.frame = frame ? frame[1].type : null;
  vars.outside = frame ? boxes.filter(b => b.l < frame[1].l - 1 || b.t < frame[1].t - 1 || b.r > frame[1].r + 1 || b.b > frame[1].b + 1).length : null;
}
return {fill: vars.fill, hp: vars.hp, frame: vars.frame, outside: vars.outside};"""


def show_hp_as_a_bar() -> dict:
    return {"touch": True, "steps": [
        *COINS,
        js(f"vars.watch.ui = {UI_BOXES}; vars.watch.numbers = () => vars.h.numbers(); return true"),
        {"wait": 0.2}, tap(), *next_round(), js(FIND_FILL),
        check("Collecting a coin widens one object on the UI layer",
              "return {ok: !!vars.fill, said: vars.fill ? `${vars.fill.type} from ${vars.fill.w0} to ${vars.fill.w1} px` : 'no UI object widened'};"),
        check("The bar grows by a quarter when hp goes from 40 to 50",
              "if (!vars.fill) return {ok: false, said: 'no fill'};",
              "const r = vars.fill.w0 / vars.fill.w1;",
              "return {ok: Math.abs(r - 0.8) <= 0.04, said: `${vars.fill.w0} / ${vars.fill.w1} = ${r.toFixed(3)}; hp ${vars.hp || 'not found'}`};"),
        check("The bar slides to the new value",
              "if (!vars.fill) return {ok: false, said: 'no fill'};",
              "const mid = vars.fill.widths.filter(w => w > vars.fill.w0 + 0.5 && w < vars.fill.w1 - 0.5);",
              "return {ok: mid.length >= 3 && vars.fill.span >= 0.1, said: `${mid.length} widths between, over ${vars.fill.span.toFixed(2)} s`};"),
        check("The fill stays inside its frame",
              "return {ok: !!vars.frame && vars.outside === 0, said: vars.frame ? `frame ${vars.frame}; ${vars.outside} sample(s) outside it` : 'no other UI object holds the fill'};"),
        js("if (!vars.hp) return 'no hp';",
           "vars.forced = vars.h.setNumber(vars.hp, 95); return vars.forced"),
        tap(), {"wait": 1.5},
        check("hp stops at 100 and the bar at its full length",
              "if (!vars.fill || !vars.hp) return {ok: false, said: `fill ${!!vars.fill}, hp ${vars.hp}`};",
              "const hp = h.numbers()[vars.hp], f = h.first(vars.fill.type), full = vars.fill.w0 * 2.5, w = f ? f.width : null;",
              "const box = f && h.box(f), fr = vars.frame && h.first(vars.frame), fb = fr && h.box(fr);",
              "const inside = box && fb && box.l >= fb.l - 1 && box.r <= fb.r + 1;",
              "return {ok: hp === 100 && w !== null && Math.abs(f.getBoundingBox().width - full) <= 2 && !!inside, "
              "said: `hp set to 95, then a collect: hp ${hp}, fill ${w !== null ? h.round(f.getBoundingBox().width) : 'gone'} px of ${h.round(full)}, inside the frame ${!!inside}`};"),
    ]}


def boxes_step(name: str) -> dict:
    return {"js": f"vars.h.ui().map(i => ({{type: i.objectType.name, text: vars.h.isText(i), box: vars.h.css(i)}}))",
            "note": f"boxes {name}"}


def reveal_the_gradient() -> dict:
    return {"viewport": [1920, 1080], "touch": True, "steps": [
        *COINS, tap(), *next_round(), {"wait": 0.7},
        boxes_step("before"), {"shot": "before"}, tap(), {"wait": 1.6}, {"shot": "after"}, boxes_step("after"),
    ]}


# The lives are the number that drops by one twice over round 3 and does not change otherwise. They may be
# counted across rounds or per round. Between the two drops the score changes once per coin collected, so it
# changes three times when a life goes every third coin. The count comes from the score, not from the taps,
# because one touch can take two coins that overlap. A drop belongs to the last tap of the plan before it, and
# the screenshots before and after that tap show the heart it took.
LIVES = r"""const r3 = vars.r3, end = Math.min(r3[r3.length - 1] + 0.9, ...vars.endAt.filter(t => t > r3[0])), at = s => vars.h.at('numbers', s) || {}, start = at(r3[0] - 0.05);
const moves = k => vars.h.changes('numbers', r3[0] - 0.05).filter(e => e.at <= end).map(e => ({at: e.at, v: e.v[k]}))
  .filter((e, i, all) => e.v !== (i ? all[i - 1].v : start[k]));
vars.lives = Object.keys(start).find(k => k !== 'g:score' && (m => m.length === 2 && m[0].v === start[k] - 1
  && m[1].v === start[k] - 2)(moves(k))) || null;
const drops = vars.lives ? moves(vars.lives) : [];
vars.drops = drops.map(d => r3.filter(t => t <= d.at).length);
vars.between = drops.length === 2 ? moves('g:score').filter(e => e.at > drops[0].at && e.at <= drops[1].at).length : null;
vars.livesSeen = Object.keys(start).map(k => `${k.slice(2)}: ${start[k]}${moves(k).map(e => ' ' + e.v).join('')}`);
return {lives: vars.lives, drops: vars.drops, between: vars.between, after: drops.length ? drops[0].v : null, values: vars.livesSeen};"""


def lives_as_hearts() -> dict:
    after = [step for k in range(1, 7) for step in (js("vars.r3.push(vars.h.now()); return vars.r3.length"),
                                                    {"tap": {"js": "vars.h.spot('Coin') || {x: 4, y: 4}"}},
                                                    {"wait": 1.0}, {"shot": f"tap{k}"})]
    return {"viewport": [1920, 1080], "touch": True, "steps": [
        *COINS, js("vars.watch.numbers = () => vars.h.numbers(); vars.r3 = []; return vars.h.numbers()"), {"wait": 0.3},
        *collect(), *collect(), boxes_step("hearts"), {"shot": "tap0"}, *after,
        {"js": LIVES, "note": "lives drops"},
        check("Every third coin of a round costs one life",
              "return {ok: !!vars.lives && vars.between === 3, "
              "said: vars.lives ? `${vars.lives.slice(2)} drops twice over round 3, ${vars.between} coin(s) apart` "
              ": `no number drops by one twice over round 3: ${vars.livesSeen.join('; ')}`};"),
    ]}


# --- the official examples -------------------------------------------------------------------------------

PLAYER = "runtime.objects.Player && runtime.objects.Player.getFirstInstance()"


def keys_move(keys: dict[str, tuple[int, int]], seconds: float = 0.5) -> list[dict]:
    steps = []
    for key in keys:
        steps += [js("const p = vars.h.first('Player'); vars.p0 = [p.x, p.y]; return vars.p0"),
                  {"key": key, "seconds": seconds},
                  js("const p = vars.h.first('Player');",
                     f"(vars.moves = vars.moves || []).push({{key: '{key}', dx: vars.h.round(p.x - vars.p0[0]), "
                     "dy: vars.h.round(p.y - vars.p0[1])}); return vars.moves[vars.moves.length - 1]")]
    return steps


def moved(text: str, keys: dict[str, tuple[int, int]]) -> dict:
    return check(text, f"const want = {json.dumps(keys)};",
                 "const got = (vars.moves || []).filter(m => m.key in want);",
                 "const bad = got.filter(m => m.dx * want[m.key][0] + m.dy * want[m.key][1] < 30);",
                 "return {ok: got.length === Object.keys(want).length && !bad.length, "
                 "said: got.map(m => `${m.key} ${m.dx >= 0 ? '+' : ''}${m.dx}, ${m.dy >= 0 ? '+' : ''}${m.dy}`).join('; ')};")


WASD = {"KeyW": (0, -1), "KeyA": (-1, 0), "KeyS": (0, 1), "KeyD": (1, 0)}
ARROWS = {"ArrowUp": (0, -1), "ArrowLeft": (-1, 0), "ArrowDown": (0, 1), "ArrowRight": (1, 0)}


def walk_with_wasd() -> dict:
    return {"steps": [*ready(PLAYER), *keys_move(WASD), *keys_move(ARROWS),
                      moved("W, A, S and D each move Player at least 30 px its way while held", WASD),
                      moved("The arrow keys still move Player", ARROWS)]}


def edges(watch: str, holds: list[tuple[str, float]], area: str, stays: str, reaches: str, margin: int) -> list[dict]:
    """Hold keys toward the edges while the box is read every tick. Then check that the box stayed in the area
    and that it reached each side of it. watch returns {l, t, r, b} and the area as {L, T, R, B}."""
    return [js(f"vars.watch.edge = {watch}; return vars.watch.edge()"),
            *[{"key": k, "seconds": s} for k, s in holds],
            js("vars.edge = (vars.seen.edge || []).map(e => e.v).filter(v => v && typeof v === 'object'); return vars.edge.length"),
            check(stays,
                  "const out = vars.edge.filter(v => v.l < v.L - 1 || v.t < v.T - 1 || v.r > v.R + 1 || v.b > v.B + 1);",
                  "const far = s => Math.max(...out.map(v => Math.max(v.L - v.l, v.T - v.t, v.r - v.R, v.b - v.B)));",
                  f"return {{ok: vars.edge.length > 0 && !out.length, said: out.length ? `${{out.length}} of ${{vars.edge.length}} samples past the {area}, up to ${{far().toFixed(0)}} px` : `${{vars.edge.length}} samples inside the {area}`}};"),
            check(reaches,
                  "const gap = {left: Math.min(...vars.edge.map(v => v.l - v.L)), top: Math.min(...vars.edge.map(v => v.t - v.T)),",
                  "  right: Math.min(...vars.edge.map(v => v.R - v.r)), bottom: Math.min(...vars.edge.map(v => v.B - v.b))};",
                  f"const far = Object.entries(gap).filter(([k, g]) => g > {margin});",
                  "return {ok: vars.edge.length > 0 && !far.length, said: Object.entries(gap).map(([k, g]) => `${k} ${g.toFixed(0)} px`).join(', ')};")]


def speed(keys: list[str]) -> list[dict]:
    """Hold the keys for 1 s from the middle of the layout, where no edge stops the player. Store the player's speed
    in px/s in vars.speeds, under the key names joined with +. The speed is the move of the watched box's centre from
    its first to its last change."""
    name = "+".join(keys)
    return [js("const p = vars.h.first('Player'); p.x = runtime.layout.width / 2; p.y = runtime.layout.height / 2;",
               "vars.watch.mid = () => { const b = vars.h.box(vars.h.first('Player')); return (b.l + b.r) / 2; };",
               "return [p.x, p.y]"),
            {"wait": 0.3}, js("vars.mark = vars.h.now(); return vars.mark"), {"key": keys, "seconds": 1.0}, {"wait": 0.2},
            js("const s = vars.h.since('mid', vars.mark), a = s[0], b = s[s.length - 1];",
               f"(vars.speeds = vars.speeds || {{}})['{name}'] = s.length > 2 ? vars.h.round((b.v - a.v) / (b.at - a.at)) : 0;",
               f"return {{ticks: s.length, speed: vars.speeds['{name}']}}")]


def script_shift_and_edges() -> dict:
    watch = ("() => { const p = vars.h.first('Player'); if (!p) return null; "
             "return {...vars.h.box(p), L: 0, T: 0, R: runtime.layout.width, B: runtime.layout.height}; }")
    return {"steps": [*ready(PLAYER), *keys_move({"ArrowRight": (1, 0)}),
                      moved("The arrow keys move the player", {"ArrowRight": (1, 0)}),
                      *edges(watch, [("ArrowLeft", 2.5), ("ArrowUp", 2.0), ("ArrowRight", 7.5), ("ArrowDown", 6.5)],
                             "layout", "The player never leaves the layout", "The player reaches every edge of the layout", 8),
                      *speed(["ArrowRight"]), *speed(["ShiftLeft", "ArrowRight"]),
                      check("Holding Shift doubles the player's speed",
                            "const s = vars.speeds, a = s.ArrowRight, b = s['ShiftLeft+ArrowRight'], r = a > 0 ? b / a : 0;",
                            "return {ok: r >= 1.8 && r <= 2.2, said: `ArrowRight ${a} px/s, with ShiftLeft ${b} px/s: ${r.toFixed(2)} times`};")]}


def stay_on_screen() -> dict:
    watch = ("() => { const p = vars.h.first('Player'); if (!p) return null; const v = p.layer.getViewport(); "
             "return {...vars.h.box(p), L: vars.h.round(v.left), T: vars.h.round(v.top), R: vars.h.round(v.right), B: vars.h.round(v.bottom)}; }")
    # A laser outside the layout is destroyed as it spawns, so the lasers are counted as they are created.
    return {"steps": [*ready(PLAYER),
                      js("vars.fired = 0; runtime.objects.Laser.addEventListener('instancecreate', () => vars.fired++); return true"),
                      {"key": "Space", "seconds": 0.5},
                      check("Space still fires",
                            "return {ok: vars.fired >= 2, said: `${vars.fired} Laser(s) created while Space was held 0.5 s`};"),
                      *edges(watch, [("ArrowDown", 1.0), ("ArrowUp", 3.0), ("ArrowLeft", 2.5), ("ArrowRight", 4.0)],
                             "screen", "The ship never leaves the screen", "The ship reaches every edge of the screen", 8)]}


# A behavior is reached by its name on the object: the runtime does not list an instance's behaviors.
FLOOR = "(() => { const p = runtime.objects.Player.getFirstInstance(); return !!(p && p.behaviors.Platform && p.behaviors.Platform.isOnFloor); })()"


def jump(name: str, gaps: list[float]) -> list[dict]:
    steps = [js("vars.mark = vars.h.now(); vars.y0 = vars.h.first('Player').getBoundingBox().top; return vars.y0")]
    for n, gap in enumerate(gaps):
        if n:
            steps.append({"wait": gap})
        steps.append({"key": "ArrowUp", "seconds": 0.1})
    return steps + [{"wait": 0.3}, {"until": FLOOR, "timeout": 6}, {"wait": 0.2},
                    js("const tops = vars.h.since('top', vars.mark).map(e => e.v);",
                       f"vars.rises['{name}'] = vars.h.round(vars.y0 - Math.min(vars.y0, ...tops)); return vars.rises['{name}']")]


def double_jump() -> dict:
    return {"steps": [
        {"until": f"{PLAYER} && {FLOOR}", "timeout": 20}, js(HELPERS),
        js("vars.watch.top = () => vars.h.round(vars.h.first('Player').getBoundingBox().top); vars.rises = {}; return true"),
        *jump("single", [0]), *jump("double", [0, 0.2]), *jump("triple", [0, 0.2, 0.2]), *jump("again", [0, 0.2]),
        check("A single jump rises as before, 120 to 160 px",
              "const r = vars.rises.single; return {ok: r >= 120 && r <= 160, said: `rose ${r} px`};"),
        check("A second press in mid-air jumps again, at least 40 px higher than a single jump",
              "const r = vars.rises; return {ok: r.double >= r.single + 40, said: `single ${r.single} px, with a second press ${r.double} px`};"),
        check("A third press in mid-air does not jump again",
              "const r = vars.rises; return {ok: r.triple <= r.double + 15, said: `two presses ${r.double} px, three presses ${r.triple} px`};"),
        check("After landing the double jump works again",
              "const r = vars.rises; return {ok: r.again >= r.single + 40, said: `single ${r.single} px, the next double jump ${r.again} px`};"),
    ]}


def walls_stop_the_player() -> dict:
    return {"steps": [
        *ready(PLAYER),
        js("vars.over = 0; vars.layout0 = runtime.layout.name;",
           "runtime.addEventListener('tick2', () => { const p = vars.h.first('Player'), w = runtime.objects.SolidBarrier;",
           "  if (p && w && w.getAllInstances().some(i => p.testOverlap(i))) vars.over++; });",
           "vars.watch.box = () => vars.h.box(vars.h.first('Player'));",
           "vars.walls = runtime.objects.SolidBarrier.getAllInstances().map(i => vars.h.box(i)); return {layout: vars.layout0, walls: vars.walls}"),
        {"key": "ArrowUp", "seconds": 1.5}, {"key": "ArrowDown", "seconds": 2.0},
        check("The player never overlaps a wall",
              "return {ok: vars.over === 0, said: `overlapping a SolidBarrier in ${vars.over} tick(s)`};"),
        check("The player walks up to the top and bottom walls",
              "const boxes = (vars.seen.box || []).map(e => e.v), top = Math.min(...boxes.map(b => b.t)), bottom = Math.max(...boxes.map(b => b.b));",
              "const above = Math.max(...vars.walls.filter(w => w.b < 240).map(w => w.b)), below = Math.min(...vars.walls.filter(w => w.t > 240).map(w => w.t));",
              "return {ok: top <= above + 4 && bottom >= below - 4, said: `player from y ${top} to ${bottom}; walls end at ${above} and start at ${below}`};"),
        {"key": "ArrowRight", "seconds": 2.0}, {"wait": 0.5},
        check("Walking off the right side still leads to the next room",
              "return {ok: runtime.layout.name !== vars.layout0, said: `layout ${vars.layout0}, then ${runtime.layout.name}`};"),
    ]}


RING = r"""const b = vars.h.box(vars.h.first('Board')), c = runtime.objects.Coin.getAllInstances().map(i => vars.h.box(i));
(vars.rings = vars.rings || []).push({board: b, coins: c}); return {board: b, coins: c.length}"""


def ring_check(n: int, text: str, index: int) -> dict:
    return check(text,
                 f"const g = vars.rings[{index}];",
                 f"if (!g || g.coins.length !== {n}) return {{ok: false, said: `${{g ? g.coins.length : 0}} coins, not {n}`}};",
                 "const cx = (g.board.l + g.board.r) / 2, cy = (g.board.t + g.board.b) / 2;",
                 "const pts = g.coins.map(k => [(k.l + k.r) / 2 - cx, (k.t + k.b) / 2 - cy]);",
                 "const r = pts.map(([x, y]) => Math.hypot(x, y)), a = pts.map(([x, y]) => Math.atan2(y, x) * 180 / Math.PI).sort((p, q) => p - q);",
                 "const gaps = a.map((v, i) => (i + 1 < a.length ? a[i + 1] : a[0] + 360) - v);",
                 "const mx = pts.reduce((s, p) => s + p[0], 0) / pts.length, my = pts.reduce((s, p) => s + p[1], 0) / pts.length;",
                 "const spread = Math.max(...r) - Math.min(...r), uneven = Math.max(...gaps) - Math.min(...gaps), off = Math.hypot(mx, my);",
                 "return {ok: spread <= 2 && uneven <= 3 && off <= 4, said: `radius ${Math.min(...r).toFixed(1)} to ${Math.max(...r).toFixed(1)}, "
                 "steps ${gaps.map(v => v.toFixed(1)).join(', ')} deg, ring ${off.toFixed(1)} px off the board's centre`};")


def coins_in_a_ring() -> dict:
    return {"touch": True, "steps": [
        *COINS, tap(), *next_round(), {"wait": 0.4}, js(RING), tap(), tap(), tap(), *next_round(), {"wait": 0.4}, js(RING),
        ring_check(3, "Round 2's three coins sit evenly on a ring around the board's middle", 0),
        ring_check(6, "Round 3's six coins sit evenly on a ring around the board's middle", 1),
        check("Every coin lies on the board",
              "const out = vars.rings.flatMap(g => g.coins.filter(k => k.l < g.board.l - 1 || k.t < g.board.t - 1 || k.r > g.board.r + 1 || k.b > g.board.b + 1));",
              "return {ok: !out.length, said: out.length ? `off the board: ${JSON.stringify(out)}` : 'every coin on the board'};"),
    ]}


PLANS: dict[str, Callable[[], dict]] = {
    "add-countdown": add_countdown, "fix-load-errors": fix_load_errors, "lay-out-the-hud": lay_out_the_hud,
    "show-hp-as-a-bar": show_hp_as_a_bar, "reveal-the-gradient": reveal_the_gradient,
    "lives-as-hearts": lives_as_hearts, "readable-on-a-dark-background": readable_on_a_dark_background,
    "walk-with-wasd": walk_with_wasd, "fix-wasd-twitch": walk_with_wasd,
    "countdown-between-rounds": countdown_between_rounds, "fix-next-round": fix_next_round,
    "fix-turn-flip": turns, "two-player-turns": turns, "two-player-turn-limit": lambda: turns(limit=True),
    "script-shift-and-edges": script_shift_and_edges, "double-jump": double_jump, "stay-on-screen": stay_on_screen,
    "walls-stop-the-player": walls_stop_the_player, "coins-in-a-ring": coins_in_a_ring,
}


# --- checks on the screenshots ---------------------------------------------------------------------------

def shot_of(result: dict, name: str) -> Path | None:
    for done in (result.get("preview") or {}).get("steps", []):
        if done.get("ok") and done["line"].split(" ", 2)[1:2] == ["shot"] and done["line"].endswith(f" {name}"):
            return Path(done["said"])
    return None


def value_of(result: dict, note: str) -> object:
    """The value of the js step with this note."""
    for done in (result.get("preview") or {}).get("steps", []):
        if done.get("ok") and done["line"].endswith(f" ({note})"):
            return done.get("value")
    return None


def images(result: dict, before: str = "before", after: str = "after", boxes: tuple[str, ...] = ("boxes before", "boxes after")
           ) -> tuple | str:
    """Two screenshots of the plan and the UI boxes beside them, or why they are missing."""
    try:
        from PIL import Image
    except ImportError:
        return "Pillow is not installed: pip install pillow"
    a, b = shot_of(result, before), shot_of(result, after)
    found = [value_of(result, note) for note in boxes]
    if not (a and b and a.exists() and b.exists()) or not all(isinstance(f, list) for f in found):
        return "the plan did not reach its screenshots"
    with Image.open(a) as one, Image.open(b) as two:
        return one.convert("RGB"), two.convert("RGB"), [box for f in found for box in f]


def changed(a, b, region: tuple[int, int, int, int], masks: list[tuple[int, int, int, int]], tolerance: int = 16
            ) -> list[tuple[int, int]]:
    """The pixels of region that differ between a and b by more than tolerance in a channel, masks left out."""
    left, top, right, bottom = region
    out = []
    pa, pb = a.load(), b.load()
    for y in range(max(0, top), min(a.height, bottom)):
        for x in range(max(0, left), min(a.width, right)):
            if any(m[0] <= x < m[2] and m[1] <= y < m[3] for m in masks):
                continue
            if max(abs(p - q) for p, q in zip(pa[x, y], pb[x, y])) > tolerance:
                out.append((x, y))
    return out


def ints(box: dict, pad: int = 0) -> tuple[int, int, int, int]:
    return int(box["l"]) - pad, int(box["t"]) - pad, int(box["r"] + 0.999) + pad, int(box["b"] + 0.999) + pad


def union(boxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)


def gradient_checks(result: dict) -> list[tuple[bool, str]]:
    """A collect lights more of the bar, and the colours it already showed stay where they were: on the bar's
    middle row, nothing changes over the first 10 to 35% of its box."""
    got = images(result)
    if isinstance(got, str):
        return [(False, got)] * 2
    a, b, boxes = got
    texts = [ints(i["box"], 4) for i in boxes if i["text"]]
    shapes = list({ints(i["box"]) for i in boxes if not i["text"]})
    if not shapes:
        return [(False, "no object but text on the UI layer")] * 2
    diff = [p for s in shapes for p in changed(a, b, s, texts)]
    if not diff:
        return [(False, "the UI layer looks the same before and after the collect")] * 2
    held = [s for s in shapes if any(s[0] <= x < s[2] and s[1] <= y < s[3] for x, y in diff[::max(1, len(diff) // 200)])]
    bar = union(held)
    row = sorted(y for _, y in diff)[len(diff) // 2]
    cols = sorted({x for x, y in changed(a, b, (bar[0], row - 1, bar[2], row + 2), texts)})
    width = bar[2] - bar[0]
    lit = (bool(cols) and cols[-1] - cols[0] >= 4, f"on row {row}, x {cols[0]} to {cols[-1]} changed; "
                                                    f"the bar's box x {bar[0]} to {bar[2]}" if cols else f"nothing changed on row {row}")
    early = [x for x in cols if bar[0] + 0.1 * width <= x <= bar[0] + 0.35 * width]
    kept = (bool(cols) and not early, f"{len(early)} column(s) changed in the first 10-35% of the bar's box (x {bar[0]} "
                                      f"to {bar[2]}), from x {early[0]}: the colours moved" if early
            else f"the first 35% of the bar's box (x {bar[0]} to {bar[2]}) kept its colours; x {cols[0]} to {cols[-1]} changed"
            if cols else lit[1])
    return [lit, kept]


def hearts_checks(result: dict) -> list[tuple[bool, str]]:
    """When the first life of round 3 is lost, only the slot of that life changes. A slot is a fifth of the
    hearts' box, counted from the left by the lives left. After the loss the slot does not show the backdrop:
    an empty heart is drawn there."""
    lost = value_of(result, "lives drops") or {}
    drops, left = lost.get("drops") or [], lost.get("after")
    if not drops:
        return [(False, "no life was lost over the six coins of round 3")] * 2
    got = images(result, f"tap{drops[0] - 1}", f"tap{drops[0]}", ("boxes hearts",))
    if isinstance(got, str):
        return [(False, got)] * 2
    a, b, boxes = got
    texts = [ints(i["box"], 4) for i in boxes if i["text"]]
    hearts = [ints(i["box"]) for i in boxes if not i["text"]]
    if not hearts:
        return [(False, "no object but text on the UI layer")] * 2
    box = union(hearts)
    diff = changed(a, b, box, texts)
    if not diff:
        return [(False, f"nothing changed in the hearts' box {box} when coin {drops[0]} of round 3 cost a life")] * 2
    fifth = (box[2] - box[0]) / 5
    slot = (box[0] + fifth * left - 2, box[0] + fifth * (left + 1) + 2) if isinstance(left, (int, float)) else (0, 0)
    stray = [p for p in diff if not slot[0] <= p[0] <= slot[1]]
    xs0 = [x for x, _ in diff]
    where = (not stray, f"{len(diff)} pixels changed in the hearts' box x {box[0]} to {box[2]}, from x {min(xs0)} to "
                        f"{max(xs0)}; the slot of heart {left + 1 if isinstance(left, (int, float)) else '?'} is x "
                        f"{slot[0]:.0f} to {slot[1]:.0f}" + (f"; {len(stray)} outside it" if stray else ""))
    # The backdrop beside the hearts, left of their box or right of it, outside every UI box.
    ys = range(box[1], box[3])
    band = [(x, y) for x in range(max(0, box[0] - 40), max(0, box[0] - 8)) for y in ys] or \
           [(x, y) for x in range(box[2] + 8, min(b.width, box[2] + 40)) for y in ys]
    others = [ints(i["box"]) for i in boxes]
    band = [(x, y) for x, y in band if not any(o[0] <= x < o[2] and o[1] <= y < o[3] for o in others)]
    if not band:
        return [where, (False, "no backdrop beside the hearts to compare with")]
    pb = b.load()
    back = {pb[p] for p in band}
    xs, ys2 = [x for x, _ in diff], [y for _, y in diff]
    spot = [(x, y) for x in range(min(xs), max(xs) + 1) for y in range(min(ys2), max(ys2) + 1)]
    drawn = [p for p in spot if min(max(abs(c - d) for c, d in zip(pb[p], k)) for k in back) > 24]
    share = len(drawn) / len(spot)
    return [where, (share >= 0.05, f"{share:.0%} of the changed spot differs from the backdrop after the life is lost")]


# case -> (the texts of its screenshot checks, the function that judges them)
POST: dict[str, tuple[list[str], Callable[[dict], list[tuple[bool, str]]]]] = {
    "reveal-the-gradient": (["Collecting a coin lights more of the bar",
                             "The colours the bar already showed stay where they are"], gradient_checks),
    "lives-as-hearts": (["Only the heart of the life lost changes",
                         "The emptied heart stays drawn"], hearts_checks),
}


# --- playing and judging ---------------------------------------------------------------------------------

def plan_for(case: str) -> dict | None:
    return PLANS[case]() if case in PLANS else None


def check_texts(case: str) -> list[str]:
    """The runtime assertions of a case, in the order verdicts() gives them; [] without a plan."""
    plan = plan_for(case)
    if plan is None:
        return []
    return ([s["note"][len(CHECK):] for s in plan["steps"] if s.get("note", "").startswith(CHECK)]
            + POST.get(case, ([], None))[0] + [NO_ERROR])


def budget(plan: dict) -> float:
    """Seconds the plan may take once the preview runs: its waits, holds and timeouts, and a margin per step."""
    total = 0.0
    for s in plan["steps"]:
        total += s.get("wait", 0) if isinstance(s.get("wait"), (int, float)) else 0
        total += s.get("seconds", 0) + (s.get("timeout", 10) if "until" in s else 0) + 1.5
        if "js" in s:
            total += 15
    return total


def play(plan: dict, project: Path, out: Path, release: str | None = None, browser: str | None = None) -> tuple[dict | None, str]:
    """Play the plan on the project with preview_project.py: its result, and what it printed."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "result.json").unlink(missing_ok=True)
    cmd = [sys.executable, str(PREVIEW), str(out / "plan.json"), "--project", str(project), "--out", str(out / "result.json"),
           "--shots", str(out), "--profile", str(PROFILE), "--limit", "0"]
    cmd += ["--release", release] if release else []
    cmd += ["--browser", browser] if browser else []
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=START + budget(plan), env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        said = (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired as e:
        said = f"preview_project.py did not finish in {e.timeout:.0f} s"
    (out / "printed.txt").write_text(said + "\n", encoding="utf-8")
    try:
        result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        result = None
    return result, said


def verdicts(case: str, result: dict | None, said: str = "") -> list[tuple[bool, str]]:
    """One (passed, evidence) per entry of check_texts(case), read from preview_project.py's result."""
    plan = plan_for(case)
    texts = check_texts(case)
    if result is None:
        last = said.strip().splitlines()[-1] if said.strip() else "no result"
        return [(False, f"the plan did not play: {last}")] * len(texts)
    if result.get("status") != "opened":
        why = result.get("exception") or "; ".join(result.get("dialogs") or []) or result.get("status")
        return [(False, f"the project did not open: {why}")] * len(texts)
    ran = result.get("preview") or {}
    if not ran.get("started"):
        return [(False, f"the preview did not run: {'; '.join(ran.get('errors') or ['no reason given'])}")] * len(texts)
    done = {d["step"]: d for d in ran.get("steps", [])}
    failed = next((d for d in ran.get("steps", []) if not d["ok"]), None)
    out = []
    for n, step in enumerate(plan["steps"], 1):
        if not step.get("note", "").startswith(CHECK):
            continue
        d = done.get(n)
        if d is None:
            out.append((False, f"not reached: step {failed['step']} failed: {failed['said']}" if failed else "not reached"))
        elif not d["ok"]:
            out.append((False, f"the check did not run: {d['said']}"))
        else:
            v = d.get("value")
            out.append((bool(v.get("ok")), str(v.get("said", ""))) if isinstance(v, dict) and "ok" in v
                       else (False, f"the check returned {json.dumps(v)[:200]}"))
    if case in POST:
        out += POST[case][1](result)
    errors = list(ran.get("errors", [])) + [e for d in ran.get("steps", []) for e in d.get("errors", [])]
    out.append((not errors, f"{len(errors)} runtime error(s): {errors[0].splitlines()[0]}" if errors else "no runtime error"))
    return out


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("case", metavar="CASE", help=f"a case of evals.json with a plan: {', '.join(PLANS)}")
    ap.add_argument("--project", type=Path, metavar="FOLDER", help="play the plan on this project and print the verdicts")
    ap.add_argument("--out", type=Path, metavar="FOLDER", help="where plan.json, result.json and the screenshots go")
    ap.add_argument("--release", metavar="rNNN", help="the editor release to open in (default: the current one)")
    ap.add_argument("--browser", metavar="EXE", help="the Chromium-based browser preview_project.py starts")
    args = ap.parse_args()
    plan = plan_for(args.case)
    if plan is None:
        print(f"no plan for {args.case}; plans exist for: {', '.join(PLANS)}", file=sys.stderr)
        return 2
    if not args.project:
        print(json.dumps(plan, indent=1, ensure_ascii=False))
        return 0
    out = (args.out or Path(tempfile.mkdtemp(prefix=f"play-{args.case}-"))).resolve()
    result, said = play(plan, args.project.resolve(), out, args.release, args.browser)
    graded = list(zip(check_texts(args.case), verdicts(args.case, result, said), strict=True))
    for text, (ok, evidence) in graded:
        print(f"{'pass' if ok else 'FAIL'}  {text}\n      {evidence}")
    passed = sum(ok for _, (ok, _) in graded)
    print(f"{passed}/{len(graded)} runtime checks passed; plan, result and screenshots in {out}")
    return 0 if passed == len(graded) else 1


if __name__ == "__main__":
    sys.exit(main())

# Construct 3 Event Sheet — Writing Rules

System prompt for writing events down for a user who builds them in the
editor. Load with [event-sheet-thinking.md](event-sheet-thinking.md)
(structure first) and [event-sheet-pitfalls.md](event-sheet-pitfalls.md)
(runtime facts). Events that go into a project's `eventSheets/*.json` are
written with the `construct3-project` skill instead
([SKILL.md](../skills/construct3-project/SKILL.md)); the rules below on
names hold for both.

## Locale

Schemas live in `data/c3-schemas/{lang}/`; `_index.json` → `languages` lists
the directories (`en-US`, `zh-CN`). Use the user's language. `{lang}/_index.json`
maps localized addon names to ids. Ids and structure are identical across
languages; only text differs.

## Output format

One event = a bold heading, a conditions table, an actions table. Sub-events
are quoted with `>` and numbered `3.1`, `3.2`. Object is what to right-click,
Name is the `list-name` shown in the add dialog (append `(Category)` when
ambiguous), Parameters lists each field with expressions in backticks and `—`
for none.

**Event 3** — Track speed every tick

> Conditions

| Object | Name | Parameters |
|--------|------|------------|
| System | Every tick | — |

> Actions

| Object | Name | Parameters |
|--------|------|------------|
| System | Set value | speed = `Player.Platform.Speed` |

> **Event 3.1** — Fast run animation

> Conditions

| Object | Name | Parameters |
|--------|------|------------|
| Player | Compare speed (Platform) | Comparison: ≥, Speed: `200` |

> Actions

| Object | Name | Parameters |
|--------|------|------------|
| Player | Set animation | Animation: `"FastRun"`, From: `beginning` |

## Rules

- Design first: the guide's rules and smell table, then write.
- Every Name exists in the schema: `list-name` in
  `data/c3-schemas/{lang}/plugins/{id}.json` or `behaviors/{id}.json`. Ask
  for the part instead of reading the file: `python
  <Construct3-RAG>/skills/construct3-project/scripts/lookup_ace.py System
  wait` prints the matching conditions, actions and expressions of `System`,
  or of a plugin or behavior by id or display name, with their parameters.
  ACEs shared by all world objects (overlap, collisions, instance variables,
  hierarchy, UID, nearest, Z order) are in `plugins/_common.json`, not in the
  plugin's file: the lookup includes them for an object of a game project,
  run in its folder; anywhere else search that file for the words.
  `plugins/system.json` and `plugins/_common.json` are longer than a file
  reader returns at once, and an ACE below the cut looks missing. Nothing
  found: say so, offer the closest match, mark it unverified. Never invent a
  plausible name.
- Expressions use the English `translated-name`: `Sprite.AnimationFrame`, not
  `Sprite.动画帧`. A user's localized names are valid in their locale; do not
  correct them.
- Variable names in one language, never mixed: `playerHealth` or `玩家生命值`.
- No pseudocode. No `if/else`, no calls, no assignments outside the tables;
  `speed = expression` inside a Parameters cell is fine.

## Where data lives

All under `data/`; `{lang}` is a locale from `_index.json` → `languages`.

| Need | File |
|------|------|
| Plugin, behavior, effect list | `c3-schemas/_index.json` |
| Localized addon names | `c3-schemas/{lang}/_index.json` |
| ACE definitions | `c3-schemas/{lang}/plugins/{id}.json`, `behaviors/{id}.json` |
| ACEs shared by all world objects | `c3-schemas/{lang}/plugins/_common.json` |
| Effect parameters | `c3-schemas/{lang}/effects/{id}.json` |
| Example projects | `c3-examples/{lang}/{id}.json`; event sheets in `../Construct-Example-Projects/example-projects/{id}/eventSheets/` when cloned alongside |
| TypeScript API | `c3-ts-defs/autocomplete-data.json`, then the matching `.d.ts` |

# Construct 3 Event Sheet — Writing Rules

Use this system prompt to write events down for a user who builds them in
the editor. Load it with [event-sheet-thinking.md](event-sheet-thinking.md)
(structure first) and [event-sheet-pitfalls.md](event-sheet-pitfalls.md)
(runtime facts, and the topic file to open for each group that the events
touch). If events go into a project's `eventSheets/*.json`, write them with
the `construct3-agent-plugin` skill instead
([SKILL.md](../skills/construct3-agent-plugin/SKILL.md)). The rules below
on names apply to both. Before events go into a project, read
[event-sheet-style.md](event-sheet-style.md), which says how the official
examples group, name and comment a sheet.

## Locale

Schemas are in `data/c3-schemas/{lang}/`; `_index.json` → `languages`
lists the directories (`en-US`, `zh-CN`). Use the user's language.
`{lang}/_index.json` maps localized addon names to ids. Ids and structure
are identical across languages; only the text differs.

## Output format

Write each event as a bold heading, a conditions table and an actions
table. Quote sub-events with `>` and number them `3.1`, `3.2`. Object is
what to right-click. Name is the `list-name` that the add dialog shows;
append `(Category)` if it is ambiguous. Parameters lists each field, with
expressions in backticks, and `—` if there are none.

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

- Design first with the rules and smell table of `event-sheet-thinking.md`,
  then write.
- Use only Names that exist in the schema, as `list-name` in
  `data/c3-schemas/{lang}/plugins/{id}.json` or `behaviors/{id}.json`. Look
  up the part instead of reading the file, because `plugins/system.json`
  and `plugins/_common.json` are longer than a file reader returns at once.
  An ACE below the cut then looks missing. `python
  <Construct3-RAG>/skills/construct3-agent-plugin/scripts/lookup_ace.py System
  wait` prints the matching conditions, actions and expressions of `System`
  with their parameters. It also takes a plugin or behavior by id or
  display name.
- ACEs that all world objects share (overlap, collisions, instance
  variables, hierarchy, UID, nearest, Z order) are in `plugins/_common.json`,
  not in the plugin's file. If you run the lookup in a game project's
  folder, it includes them for an object of that project. Anywhere else,
  search that file for the words.
- If you find nothing, say so, offer the closest match and mark it
  unverified. Never invent a plausible name.
- Write expressions with the English `translated-name`:
  `Sprite.AnimationFrame`, not `Sprite.动画帧`. A user's localized names are
  valid in their locale, so keep them unchanged.
- Write variable names in one language, never mixed: `playerHealth` or
  `玩家生命值`.
- Write no pseudocode: no `if/else`, calls or assignments outside the
  tables. `speed = expression` inside a Parameters cell is fine.

## Where data lives

All paths are under `data/`; `{lang}` is a locale from `_index.json` →
`languages`.

| Need | File |
|------|------|
| Plugin, behavior, effect list | `c3-schemas/_index.json` |
| Localized addon names | `c3-schemas/{lang}/_index.json` |
| ACE definitions | `c3-schemas/{lang}/plugins/{id}.json`, `behaviors/{id}.json` |
| ACEs shared by all world objects | `c3-schemas/{lang}/plugins/_common.json` |
| Effect parameters | `c3-schemas/{lang}/effects/{id}.json` |
| Example projects | `c3-examples/{lang}/{id}.json`; event sheets in `../Construct-Example-Projects/example-projects/{id}/eventSheets/` if cloned alongside |
| TypeScript API | `c3-ts-defs/autocomplete-data.json`, then the matching `.d.ts` |

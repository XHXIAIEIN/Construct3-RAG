# The Gold Set Runs in pytest, and Effects Are Looked Up

Date: 2026-09-27
Schema: Construct 3 r495.2

## Problem

The gold set for Direct Lookup was written for a service that answered in two
stages, a lookup and then semantic retrieval for what the lookup declined.
The second stage was removed on 2026-09-22 (`remove-qdrant-full-mode.md`),
but the set kept its shape:

- every case had `expected_semantic`, and twelve rationales said a miss
  "falls back to semantic retrieval", which no longer exists;
- the Bulge case expected a miss because "the first stage only promises
  ACEs", although `data/c3-schemas/{locale}/effects/` answers it exactly and
  `AGENTS.md` lists effect parameters as a question the data answers. With
  no second stage, the case protected a question going unanswered;
- all cases were labelled `r495` while the data is `r495.2`, and the runner
  flagged each one;
- `tests/eval_query_quality.py`, 1 650 lines, compared a `current` and a
  `literal` alias strategy over a dev and a held-out split with Hit@k, MRR,
  nDCG and latency. That is the apparatus for tuning retrieval; nobody tunes
  it now, and it ran only by hand, which is how the set went stale;
- the runner rebuilt the `_common` source of a match that the service
  already reports;
- `tests/eval_lookup.py` repeated part of the set as a second script.

`lookup_ace.py`, which agents use, did not know effects either.

## Decision

- `tests/test_query_gold.py` runs every case of
  `tests/fixtures/query_gold.jsonl` in the ordinary `pytest` run: whether
  the service answers or declines, the intent, the entity, the ACE types,
  the required and forbidden results by stable key within a rank, and the
  result count. A case has only those fields and its source and rationale;
  `expected_semantic`, `split`, `schema_version`, `style_tags`, `critical`
  and the alternatives that fed only nDCG are gone.
- Both eval scripts are deleted. The cases of `eval_lookup.py` that the set
  lacked (bare addon names, `Sprite 重叠`, `Sprite字体`, an unqualified
  `simulateControl`, `custom action`) are gold cases.
- `LookupEngine` loses `directed_aliases_provider`, which only the `literal`
  strategy used.
- A declined query is the `declined` intent and task family, and the
  `semantic-fallback-*` and `fallback-edge-*` cases are `declined-*` and
  `declined-edge-*`. The name reaches `debug.lookup.intent` only.
- Effects: an effect name together with an effect word (`effect`, `shader`,
  `特效`, `滤镜`, `效果`, `着色器`) is the `effect_detail` intent, one match per
  effect with its parameters in `params`. Without the word the query is
  declined and keeps the entity: Screen, Color and 亮度 are ordinary words
  too. The zh-CN pack names both Brightness and Lighten 亮度, so a name maps
  to every effect that has it. `lookup_ace.py` takes an effect by id or name
  and prints its parameters.
- A list case sets `complete_list`, and the test counts the list from the
  entity's schema file. The cases used to pin each release's list sizes as
  `min_results` and as the rank a required entry had to reach (16, 56, 83),
  and some rationales stated them.
- Properties are grouped under `properties`, the schema's section name; the
  presenter used to add an `s` and wrote `propertys`.
- `mode=list` names ACEs only. A hit without ACE names, an effect, a
  property list, a term, an example or a script member, now returns its
  matches as `lookup` mode does, where it returned an empty `lookup` object.

## Re-evaluate when

- A change to the lookup is to be tuned by rank rather than pinned case by
  case: measure it in a script outside `tests/`, from the same gold set.
- Agents ask for effects by a word the cue list lacks: add it to
  `query.effect_keywords` in `src/locale/catalog.json`, from a failing gold
  case.

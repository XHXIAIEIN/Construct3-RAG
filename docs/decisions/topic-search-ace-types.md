# A Topic Search Keeps Every ACE Type a Noun Could Mean

Date: 2026-09-28
Schema: Construct 3 r495.2

## Problem

An entity-plus-topic query such as `精灵碰撞` or `Audio 音量` searched only
the ACE type its topic word was mapped to, and several gold cases pinned the
wrong answer that followed:

- `scoped_ace_type_rules` in `src/locale/catalog.json` mapped topics to one
  type: collision and jump to conditions; animation, volume, parse, request,
  item and others to actions; Array find to expressions; Local storage get to
  actions. Each rule cited the gold case it made pass. `平台跳跃` lost *Set
  jump strength*, `Audio 音量` lost the *Volume* expression, `JSON parse`
  lost *On parse error*, and `怎么在数组中查找特定数字` lost *Contains
  value*, whose description is exactly that search.
- `query.ace_types.*.intent_keywords` did the same with nouns: `碰撞`,
  `可见` and `跳跃` meant conditions, and `位置`, `角度`, `速度`, `宽度` and
  `获取` meant expressions. The schema names a noun in every type: `启用碰撞`
  is an action and `已启用碰撞` a condition; `获取词条` is Local storage's
  asynchronous action and `词条数据` the expression that reads its result.
  `Sprite 角度` returned the *Angle* expression without *Set angle*, and
  `文件系统读取文件` returned folder expressions without *Read text file*.
- Shared ACEs were searched for any plugin with an `initially-visible`
  property. Text and Button have one but no collisions, so `Text 碰撞`
  answered with *On collision with another object*. Array has none, so
  `Array UID` found nothing, although Array's `commonAces` lists
  *Pick by unique ID* and *UID*.
- A test forbade `_common` *Pick by unique ID* for the Array find query. The
  lookup never searched `_common` for Array, so the assertion could not fail,
  and Array does have that ACE. Two more tests forbade ACEs, *Is playing* and
  *Set blend mode*, that shared no word with their queries.
- Ties were broken by where the word first appeared in the Chinese and
  English names joined together, so a short Chinese name ranked its English
  match first, and noun-named expressions led every mixed list.

## Decision

- `scoped_ace_type_rules` and its loader are removed.
- `intent_keywords` keep predicates for conditions (`正在`, `比较`, `是否`),
  acts for actions (`设置`, `播放`, `暂停`) and value computation for
  expressions (`返回`, `转换`, `查找`). Nouns are removed, and so are `获取`,
  `获得` and `读取`, which name asynchronous actions as well as expressions.
  A topic without one of these words searches conditions, actions and
  expressions.
- The directed alias `arr.condition.find-to-contains` lets `查找` on Array
  reach *Contains value*, whose name says contain, not find.
- `_common` is searched for exactly the ACEs the plugin's `commonAces`
  lists, as `AGENTS.md` describes the data.
- Candidates of equal score are ordered conditions, actions, expressions,
  then by where the word sits in the name that holds it.
- The gold cases state the complete answer: *Set jump strength* with *Is
  jumping*, *Volume* with *Set volume*, *On parse error* with *Parse*.
  `script-api-neutral-04` requires all four classes that declare
  `simulateControl`, Tile Movement included. `文本碰撞` and `数组销毁` cover
  the shared ACEs.

## Re-evaluate when

- A verb that stays in `intent_keywords` hides a correct answer of another
  type: remove it, starting from a failing gold case.
- Equal-score ordering puts a trigger before the action a query asks for, as
  in `JSON parse`, often enough to matter: measure an order by rank outside
  `tests/`, from the gold set, as `query-gold-in-pytest.md` says.
- `Array destroy` resolves to the Destroy outside behavior rather than to
  Array; entity resolution between two addon names in one query is not
  decided here.

export const meta = {
  name: 'polish',
  description: 'Polish Construct3-RAG: reorganize and rewrite its instruction files, docs, records and prompts against the repository rules and official guidance, simplify its code with /simplify, verify every change, check, commit and merge',
  whenToUse: 'When no other session is editing this repository, about once a week or after a burst of commits. Run it from a session in the main clone or one of its worktrees. The preflight leaves out every file another worktree, branch, stash or uncommitted change holds. args are optional (header comment of .claude/workflows/polish.js).',
  phases: [
    { title: 'Preflight', detail: 'busy files, the base, the polish worktree, the units, failing tests, guards, official guidance' },
    { title: 'Restructure', detail: 'moves between files: plan, two judges per move, apply with tests, check each move' },
    { title: 'Sweep', detail: 'cross-file sweeps: references, inventories, duplication, names, stale text, growth, duplicated code' },
    { title: 'Polish', detail: 'text units in parallel; code units one at a time through /simplify' },
    { title: 'Verify', detail: 'two reviewers per text unit, a behavior reviewer per code unit; one repair, then keep or revert' },
    { title: 'Check', detail: 'restore what was not kept, follow-ups, tests, output sweep, commits' },
    { title: 'Review', detail: 'the whole branch: routes, project rules, meaning across files' },
    { title: 'Merge', detail: 'fast-forward main when every gate passed, record the run, write the report' },
  ],
}

// args (all optional):
// {
//   scope: 'changed' | 'all'    'changed' (default) polishes what the commits since the last run touched, and what
//                                that run carried over; the first run, with no recorded base, polishes everything.
//   base: '<commit>'            start the changed scope at this commit instead of the recorded base.
//   paths: ['prompts/']         polish only files under these prefixes.
//   busy: 'skip' | 'stop'       'skip' (default) leaves out the files that other sessions hold; 'stop' ends the run
//                                when there are any.
//   stale_days: 14              a holder with no change for this many days and no uncommitted file is stale.
//   mode: 'apply' | 'report'    'report' changes nothing and returns what a run would change.
//   restructure: false          skip the moves between files.
//   max_moves: 6                at most this many moves between files per run.
//   merge: false                leave the branch for a person to merge.
//   refresh_standards: true     re-read the official guidance although the last read is under 30 days old.
//   examples: '<folder>'        the official examples for sweep_outputs.py; default the example-projects folder
//                                of the Construct-Example-Projects clone beside this one.
//   projects: ['<folder>']      game projects for sweep_outputs.py besides the examples.
//   forbidden: ['<name>']       names that must not appear in tracked files. Pass them from your notes, or keep
//                                them one per line in .local/polish/forbidden.txt; never write them here, because this
//                                file is tracked in a public repository.
//   root: '<main clone>'        default: the first worktree `git worktree list` prints.
//   dry_run: true               preflight and guard search only: the units, the busy files, the guards; no worktree.
// }
// A first run: { dry_run: true }, then { mode: 'report' }, then a normal run after reading the report.
//
// Why it is shaped this way:
// - Other sessions work in this repository most of the time. A file that another worktree, branch, stash or
//   uncommitted change holds is left out and carried to the next run, so the merge meets no conflict and no
//   session merges into rewritten text.
// - The skill's text and output are measured: skills/AGENTS.md makes a change to SKILL.md, a reference or
//   what a script prints a new eval iteration, and the evals showed small-model behavior moving with wording
//   a polish would call cosmetic. Those files get proposals in the report, not edits. The guarded files are
//   listed in WHOLE_GUARDS below, so that no agent can drop one.
// - This file is never polished: no check runs it, and a broken template literal would stop the next run.
//   A person updates it from the report's guidance differences.
// - Text units edit one worktree in parallel; code units run one at a time, because their tests import each
//   other's modules. Code goes through the simplify skill and is reviewed with the code-review skill;
//   behavior stays identical, which the tests and sweep_outputs.py check.
// - The gates of checks, review and commits are computed here, not left to an agent: a dead reviewer or a
//   failed check keeps the branch out of main. The merge agent can only add a stop.

const A = args || {}
const MODE = A.mode === 'report' ? 'report' : 'apply'
const APPLY = MODE === 'apply'
const SCOPE = A.scope === 'all' ? 'all' : 'changed'
const BUSY = A.busy === 'stop' ? 'stop' : 'skip'
const STALE_DAYS = Number.isInteger(A.stale_days) && A.stale_days > 0 ? A.stale_days : 14
const RESTRUCTURE = A.restructure !== false
const MAX_MOVES = Number.isInteger(A.max_moves) ? Math.max(0, Math.min(12, A.max_moves)) : 6
const MERGE = A.merge !== false
const PATHS = Array.isArray(A.paths) ? A.paths.map(p => String(p).replace(/\\/g, '/').replace(/^\.\//, '')) : []
const PROJECTS = Array.isArray(A.projects) ? A.projects.map(p => String(p).replace(/\\/g, '/')) : []
const FORBIDDEN = Array.isArray(A.forbidden) ? A.forbidden.map(String) : []

// ---------------------------------------------------------------- what may change

// Never polished: generated, data, assets, or this workflow.
const NEVER = [
  [/^data\/(?!AGENTS\.md$)/, 'scripts/init.py and the CDN pipeline generate data/, and data/c3-guides/ is Scirra\'s text'],
  [/^src\/ingest\/common_aces\.json$/, 'scripts/extract_common_aces.py generates it'],
  [/^tests\/fixtures\//, 'gold cases and fixtures'],
  [/^skills\/[^/]+\/evals\/[^/]+\.json$/, 'eval cases and trigger queries'],
  [/^\.claude\/workflows\//, 'the workflow itself: no check runs it, so a person changes it from the report'],
  [/^\.github\//, 'the update pipeline'],
  [/^(LICENSE|\.gitignore|\.gitattributes)$/, 'licence and git configuration'],
  [/\.(png|jpe?g|webp|gif|ico|svg|html|json|js|css|ts)$/i, 'data, pages and assets that are not prose or Python'],
]
// Whole files whose change needs an eval, a measurement or a decision: proposals only.
const WHOLE_GUARDS = [
  [/^skills\/[^/]+\/SKILL\.md$/, 'skills/AGENTS.md, "Evals": a change to SKILL.md is a new eval iteration, and its description changes only through the trigger eval'],
  [/^skills\/[^/]+\/references\//, 'skills/AGENTS.md, "Evals": a change to a reference is a new eval iteration'],
  [/^skills\/[^/]+\/assets\//, 'a game project copies the assets and its agent reads and edits them; the evals measured the template and the block (docs/decisions/generator-helpers-inline.md, docs/decisions/project-tools-skill.md)'],
  [/^prompts\/event-sheet-thinking\.md$/, 'docs/decisions/event-sheet-design-guidance.md: an edit moved small-model structure on tasks it does not mention, so each edit is rerun beside the old file'],
  [/^\.claude-plugin\//, 'docs/decisions/directory-listing.md: the plugin directory publishes it'],
]
// Passages every run keeps, besides those the guard agents find.
const FIXED_PASSAGES = [
  { path: 'prompts/event-sheet-pitfalls.md', what: 'the Topics structure (one ### group per topic file, with one link to it), every when-to-read line, and the wording of every conclusion line; a conclusion line may move to follow its topic file\'s order', rule: 'docs/decisions/pitfalls-index-and-topics.md, tests/test_prompts.py' },
  { path: 'AGENTS.md', what: 'the section numbers, section 2\'s route to lookup_ace.py, and section 4\'s install commands', rule: 'the game-project block and decision records cite them' },
  { path: 'README.md', what: 'the agent notice at the top, and the Set up section, which stays the first section', rule: 'docs/decisions/bootstrap-from-the-url.md' },
  { path: 'README_CN.md', what: 'the agent notice at the top, and the Set up section, which stays the first section', rule: 'docs/decisions/bootstrap-from-the-url.md' },
  { path: '.claude/CLAUDE.md', what: 'the single line @AGENTS.md', rule: 'Claude Code loads it as the project instructions of this repository, and install.py writes the same line into game projects' },
]

const never = p => NEVER.find(([r]) => r.test(p))
const wholeGuard = p => WHOLE_GUARDS.find(([r]) => r.test(p))
const inPaths = p => !PATHS.length || PATHS.some(x => p.startsWith(x))
const uniq = xs => [...new Set(xs)]

// ---------------------------------------------------------------- shared text

const UNIT_RULES = `A unit is a set of files that must stay consistent with each other and that one agent can read in full: up to about 1500 lines of text, or one large code file, or a few small ones. Every polishable file belongs to exactly one unit. Unit ids are short and kebab-case. Areas and kinds:
- instructions (text): the root AGENTS.md with .claude/CLAUDE.md; every other AGENTS.md on its own.
- readme (text): README.md with README_CN.md, because README_CN.md carries the content of README.md.
- docs (text): docs/guide/; docs/dev/.
- records (text): docs/decisions/, in batches of up to six records that share a group of the table in docs/AGENTS.md.
- prompts (text): prompts/event-sheet-pitfalls.md on its own (the index); the topic files of prompts/pitfalls/ in batches; every other file of prompts/ and prompts/references/ on its own or in small batches by topic.
- skill (text): skills/<skill>/SKILL.md; skills/<skill>/references/ in batches; skills/<skill>/assets/*.md.
- agents (text): .claude/agents/.
- code: scripts/ in batches by topic; scripts/reference_games/; src/ by package; skills/<skill>/scripts/, one large script per unit and small ones in batches; skills/<skill>/evals/*.py; skills/<skill>/assets/*.py; tests/ in batches by the module they test, test_skill_<script>.py with nothing else.
Leave out data/ (except data/AGENTS.md), tests/fixtures/, .github/, .claude/workflows/, generated files, and files that are not Markdown or Python, with the reason for each group under excluded.`

const GUARD_RULES = `Guarded text needs more than a polish to change: an eval iteration, a measurement or a decision. A run proposes edits to it and changes nothing. Kinds of guarded passage:
- Whatever a decision record, an AGENTS.md or an eval says must not change without an eval, a measurement or a decision.
- Any sentence, path or heading a test asserts: grep tests/ for the file's name and its distinctive sentences.
- A heading, a section number or a file name that another file cites, above all text that ships into game projects (skills/<skill>/assets/game-project-block.md, SKILL.md, references) or that scripts print.
- In prompts/pitfalls/: the number and order of top-level entries and each entry's bracketed source, because the index holds one conclusion line per entry in the same order.
- In prompts/event-sheet-style.md, prompts/event-sheet-assistant.md and prompts/game-project-AGENTS.md: what a record or an eval pins (the habits mapped to the checks, the output-format example, the account of the block's step 1).
- In decision records: the Date and Schema lines; measured eval results that settle a decision (pass rates, run counts), never rounded or dropped; decisions the user took, reworded at most, never reversed or softened; quoted editor and script messages; what a record names as removed, renamed or replaced, and its account of the state before the change (remove-*.md and any other record), which name files that are gone on purpose; licence attributions.
- In Markdown code examples: the calls, which must name helpers that exist; a broken one gets a proposal, not a silent change of the example.
- In code: names that a test patches or imports, names that JSON files such as src/locale/catalog.json cite, wrappers an AGENTS.md orders kept, and every string a test asserts.
- What a script prints (stdout, stderr, exit codes, --help, and a module docstring that argparse prints): the code around it may change, the output may not.`

const REPO_RULES = `This repository overrules general guidance where its rules or measurements say so:
- Scripts print everything on stdout, a miss and a note included, and use stderr only for what stops a run (skills/AGENTS.md: PowerShell wraps stderr); the printers emit readable event text, not JSON.
- Small models read SKILL.md and tool output, rarely prose (docs/decisions/event-sheet-design-guidance.md): do not cut text that the evals showed a small model needs, even when a capable model would not need it.
- The skill's name stays, because installed copies and the plugin id depend on it.
- AGENTS.md is read by other clients too (install.py serves .agents/skills and .trae/skills besides Claude Code): content they need stays plain Markdown, not behind Claude Code's @imports or HTML comments.
- Decision records carry Date and Schema lines by design and keep the reasons behind a decision; they still state what holds now (docs/AGENTS.md).
- A pitfall entry is a sourced record (docs/decisions/pitfalls-index-and-topics.md): entries merge only when they state the same fact, never into a few examples.
`

const TEXT_RULES = `How this repository writes (the root AGENTS.md, the AGENTS.md of the area and docs/AGENTS.md give the details):
- State what holds now. No "now", "no longer", "new", "recently", dated updates or the story of a change; Git keeps the history.
- Every sentence earns its place: the reader would know less, or err, without it.
- A rule lives in one file, its owner, and other files point to it with a when-clause ("before X, read Y"), not a description of the file and not a copy of the rule. A file that is read alone (a sub-agent file, the prompts the README loads together as a system prompt, SKILL.md, the game-project block, script output) keeps its copy; a decision record keeps the rule it decided.
- One concept, one name, the name its owner file uses.
- Prompts, the skill, AGENTS.md files and agent files are English. README_CN.md carries the content of README.md; README.md names no Chinese text or locale besides its link to README_CN.md, and the Chinese examples stay in README_CN.md. Chinese Construct terms are the zh-CN editor's (data/c3-lang/zh-CN.json); in Chinese text the Claude Code plugin stays "plugin", because the Chinese word for plugin names a Construct plugin.
- Versions and counts come from data/c3-schemas/_index.json and are never written into text, except a record's Schema line, the release in a pitfall source and the release a measurement was made on; test totals stay out of docs; a tally over the official examples or a minified editor name is not stated as the rule.
- The repository is public: a finding from a game project is stated as the mechanism, without the names of the project, its objects, variables or functions, the maintainer's own projects included; studied games, their authors and sources are not named; commit hashes stay out. Licence attributions and Scirra's own sources stay.
- An instruction gives its condition first and its reason after it. A table or list holds parallel items; reasoning is prose.
- ACE ids stay in their quotes or backticks: scripts/schema_diff.py finds them there when a release changes an ACE.

${REPO_RULES}`

// The baseline of official guidance. The Standards agent re-reads the sources when the last
// read is 30 days old and returns the current list; a difference goes into the report, so that a person updates
// this baseline.
const STANDARDS_BASELINE = `instruction-file:
- cut-line-test: keep a line only if removing it would make the agent err [bp]
- under-200-lines: keep each AGENTS.md or CLAUDE.md under about 200 lines; move what only one area needs into that area's AGENTS.md [mem][lc]
- no-derivable: leave out what the agent learns by reading the code (file-by-file inventories, directory trees); keep pitfalls, reasons and conventions that differ from defaults [mem]
- no-volatile: leave out facts that change often; point to the file that holds them [bp]
- concrete: name the command, path or value instead of a vague goal [mem]
- no-conflicts: remove contradictions between the root file and nested files [mem]
- no-dead-references: every path, script and command named exists [mem]
- emphasis-rare: emphasis (IMPORTANT, MUST) only on the one rule agents keep skipping [bp]
- checks-as-commands: the checks an agent runs before finishing are exact commands [agentsmd]
- root-vs-area: repository-wide rules in the root file, an area's conventions in the area's file [lc]
docs:
- one-term-per-concept [skbp]
- descriptive-names: a file's name says what it holds [skbp]
- toc-over-100-lines: a reference file over 100 lines opens with a table of contents [skbp]
- default-with-escape-hatch: one default and the case it does not cover, not a menu of equal options [skbp][skc]
- forward-slash-paths [skbp]
- length-matches-need: no filler sections, repeated summaries or boilerplate [pbp]
- literal: the literal statement instead of a metaphor [pbp]
records:
- evidence-not-log: the finding that settles the choice, not the log of the runs behind it [docs/AGENTS.md]
- length-matches-need [pbp]
prompt:
- only-unknown-context: keep what the agent does not know and what changes what it does [skbp][ctx]
- right-altitude: heuristics specific enough to guide, neither if-else chains nor vague advice [ctx]
- colleague-test: a reader with no context can follow it, output format included [pbp]
- give-the-reason: a rule carries its reason [pbp]
- say-what-to-do: a prohibition sits next to the wanted alternative [pbp]
- calm-emphasis: plain conditional wording ("use X when ...") instead of shouting [pbp]
- explicit-scope: when a rule covers several items, say so [pbp]
- examples-marked: examples are set off from instructions, relevant and varied, because agents copy them as structure [pbp]
- canonical-not-laundry: a few canonical examples, not a list of edge cases [ctx]
- just-in-time: always-loaded text holds paths and commands; the agent loads content when it needs it [ctx]
skill:
- name-format: lowercase, digits, single hyphens, equal to the folder [spec]
- description: third person, what it does and when to use it, the key terms a matching request contains, at most 1024 characters, the main use first [skbp][spec][ccsk]
- skill-md-size: SKILL.md under 500 lines and about 5000 tokens [spec]
- references-one-level: every reference is linked from SKILL.md directly, with the condition for reading it [skbp][skc]
- list-scripts: every script the agent runs is listed with its purpose and command line, and says whether to run or read it [scripts][skbp]
- freedom-matches-fragility: exact commands for fragile steps, heuristics where many ways work [skbp]
- validation-loop: a step that changes files ends in a validator run, fix and rerun [skbp]
- eval-before-polish: a rewrite of a skill or prompt is kept only if its test holds or improves [pbp][skbp]
subagent:
- frontmatter: name and description on line 1, fields spelled as documented [sub]
- description-when: a specific statement of when to delegate [sub]
- least-privilege: tools limited to what the agent needs [sub]
- self-contained: the prompt works without the parent conversation [sub]
- intent-upfront: the larger task, who reads the output, the constraints, first [pbp]
- concrete-thresholds: a reporting bar with concrete criteria, not "important" [pbp]
- condensed-return: return a condensed result, not the exploration [ctx]
plugin:
- layout: only plugin.json and marketplace.json in .claude-plugin/ [plug]
- names-match: the marketplace entry name equals plugin.json's name [plug]
- version-one-place: version in one place or nowhere [plug]
script-cli:
- help: --help with a one-line purpose, the flags, examples and exit codes [scripts]
- no-prompts: input from flags, never an interactive prompt [scripts]
- actionable-errors: what went wrong, what was expected, what to run next, and the valid values on a miss [scripts][tools]
- bounded-output: a default limit, and a last line that says how to get the rest [scripts][tools]
- high-signal: only what the next step needs, natural-language names over internal ids [tools]
- dry-run: a state-changing script has --dry-run [scripts]
- justify-constants: a constant says why it has its value [skbp]`

const STANDARDS_SOURCES = `[mem] https://code.claude.com/docs/en/memory
[bp] https://code.claude.com/docs/en/best-practices
[lc] https://code.claude.com/docs/en/large-codebases
[sub] https://code.claude.com/docs/en/sub-agents
[plug] https://code.claude.com/docs/en/plugins-reference and https://code.claude.com/docs/en/plugin-marketplaces
[ccsk] https://code.claude.com/docs/en/skills
[agentsmd] https://agents.md
[skbp] https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
[spec] https://agentskills.io/specification
[skc] https://agentskills.io/skill-creation/best-practices
[scripts] https://agentskills.io/skill-creation/using-scripts
[pbp] https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
[ctx] https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
[tools] https://www.anthropic.com/engineering/writing-tools-for-agents`

const AREA_KINDS = {
  instructions: ['instruction-file', 'docs'], readme: ['docs'], docs: ['docs'], records: ['records', 'docs'],
  prompts: ['prompt'], skill: ['skill', 'prompt'], agents: ['subagent'], code: ['script-cli'],
}

const HOLDERS_HOWTO = (main) => `- For "${main}" and every other worktree (\`git -C "${main}" worktree list --porcelain\`): its uncommitted and untracked files, \`git --no-optional-locks -C "<worktree>" status --porcelain\`. The --no-optional-locks keeps your read from taking the other session's index lock.
- For every local branch and every detached worktree HEAD: the commits that main lacks even as cherry-picks, \`git -C "${main}" log --cherry-pick --right-only --no-merges --format=%H main...<ref>\`, and their files, \`git -C "${main}" diff-tree -r --no-commit-id --name-only --no-renames <sha>\`.
- Every stash: \`git -C "${main}" stash list --format=%H\`, and its files, \`git -C "${main}" stash show --include-untracked --name-only <sha>\`.
- If \`claude agents --json --all\` works, every session in state working or blocked whose cwd is "${main}" or under it, with its summary.
A holder with no change for ${STALE_DAYS} days and no uncommitted file is stale: list it with stale=true and leave its files out of busy_files. A polish/* branch or worktree of an earlier run is a leftover, listed under leftovers for a person to clean up: its uncommitted files are that run's unverified edits, not a holding, and only its commits that main lacks count, going stale like any branch's.`

// Everything an agent that touches the worktree must know. Workflow agents start in the session's checkout,
// return there after every shell call, and read the user's instructions about finishing work on a branch.
const LOCK_RULE = 'Run one git command per call; if git says index.lock exists, another git command holds it: wait a few seconds and retry, and never delete the lock.'
const NO_MERGE = 'This run commits and merges only in the steps that say so, because other sessions share the repository and the merge waits for every check and review. Commit only when this prompt tells you to, and never merge, fast-forward main, push, rebase, stash, reset or switch branches, whatever other instructions say about finishing work on a branch.'
const env = pre => `Environment: Windows with Git Bash and PowerShell; Python is \`python\`. The polish worktree is "${pre.worktree}". Your shell starts in another checkout and returns there after every call, so start each shell command that runs Python or a script with \`cd "${pre.worktree}" && \`, run git as \`git -C "${pre.worktree}" ...\`, and give every file to Read, Edit and Write as an absolute path under the worktree. Quote paths in commands. ${LOCK_RULE} Write into "${pre.report_dir}" with Bash or a Python one-off, because a hook may refuse Edit and Write under .local/.
${NO_MERGE}`
// A test that fails because of a file outside the unit is no fault of the unit: units share one worktree.
const OTHERS_FAILURE = 'A failure in a file outside the unit is another agent\'s unfinished edit: run the test again a minute later, and if it still fails, list it under unverified, not as the unit\'s failure.'

const abs = (pre, paths) => paths.map(p => `${pre.worktree}/${p}`)

// ---------------------------------------------------------------- schemas

const STR = { type: 'string' }
const STRS = { type: 'array', items: STR }
const REL = { type: 'string', description: 'repository-relative path with forward slashes, as git ls-files prints it, no line suffix' }
const RELS = { type: 'array', items: REL }
const GUARD = { type: 'object', properties: { path: REL, what: { ...STR, description: 'empty for the whole file, else the passage' }, rule: STR }, required: ['path', 'what', 'rule'] }

const UNIT = {
  type: 'object',
  properties: {
    id: STR,
    area: { type: 'string', enum: ['instructions', 'readme', 'docs', 'records', 'prompts', 'skill', 'agents', 'code'] },
    kind: { type: 'string', enum: ['text', 'code'] },
    paths: RELS,
    tests: { ...STRS, description: 'test files or node ids that exercise the unit or read its files' },
  },
  required: ['id', 'area', 'kind', 'paths', 'tests'],
}

const PREFLIGHT = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    stop_reason: STR,
    main: { ...STR, description: 'absolute path of the main clone, forward slashes' },
    worktree: { ...STR, description: 'absolute path of the polish worktree, forward slashes; on a dry run the path a run would use' },
    branch: STR,
    stamp: STR,
    report_dir: STR,
    head: { ...STR, description: 'HEAD_SHA: the full sha of main that the worktree starts from' },
    base: { ...STR, description: 'the commit the changed scope starts from, empty for all' },
    scope: { type: 'string', enum: ['changed', 'all'] },
    changed_files: RELS,
    holders: { type: 'array', items: { type: 'object', properties: {
      worktree: STR, branch: STR, files: { type: 'integer' }, last_change: STR, stale: { type: 'boolean' }, summary: STR },
      required: ['worktree', 'branch', 'files', 'last_change', 'stale'] } },
    leftovers: STRS,
    busy_files: RELS,
    units: { type: 'array', items: UNIT },
    excluded: { type: 'array', items: { type: 'object', properties: { paths: STR, reason: STR }, required: ['paths', 'reason'] } },
    failing_before: { ...STRS, description: 'pytest node ids that fail in the worktree before any change' },
    examples: { ...STR, description: 'the examples folder for sweep_outputs.py, empty when missing' },
    standing_proposals: { ...RELS, description: 'guarded files whose content is unchanged since proposals.json recorded proposals for them' },
    standards_due: { type: 'boolean' },
    forbidden_files: { ...STRS, description: 'files that list names that must not appear in tracked files' },
    notes: STR,
  },
  required: ['ok', 'stop_reason', 'main', 'worktree', 'branch', 'stamp', 'report_dir', 'head', 'base', 'scope', 'changed_files', 'holders', 'leftovers', 'busy_files', 'units', 'excluded', 'failing_before', 'examples', 'standing_proposals', 'standards_due', 'forbidden_files', 'notes'],
}

const GUARDS = {
  type: 'object',
  properties: { guards: { type: 'array', items: { ...GUARD, properties: { ...GUARD.properties, evidence: STR }, required: ['path', 'what', 'rule', 'evidence'] } } },
  required: ['guards'],
}

const STANDARDS = {
  type: 'object',
  properties: {
    by_kind: { type: 'array', items: { type: 'object', properties: {
      kind: { type: 'string', enum: ['instruction-file', 'docs', 'records', 'prompt', 'skill', 'subagent', 'plugin', 'script-cli'] },
      items: { type: 'array', items: { type: 'object', properties: { id: STR, rule: STR, source: STR }, required: ['id', 'rule', 'source'] } },
    }, required: ['kind', 'items'] } },
    deltas: { type: 'array', items: { type: 'object', properties: { id: STR, change: { type: 'string', enum: ['new', 'changed', 'gone'] }, detail: STR, source: STR }, required: ['id', 'change', 'detail', 'source'] } },
    unreachable: STRS,
  },
  required: ['by_kind', 'deltas', 'unreachable'],
}

const MOVES = {
  type: 'object',
  properties: {
    moves: { type: 'array', items: { type: 'object', properties: {
      id: STR,
      what: { ...STR, description: 'the content that moves, merges or splits, by file and section' },
      from: RELS, to: RELS,
      kind: { type: 'string', enum: ['move', 'merge-files', 'split-file', 'delete-record', 'dedupe'] },
      why: STR,
      evidence: { ...STR, description: 'what in the repository shows the current place is wrong: routing tables, duplicated rules, growth' },
      pointers: { ...RELS, description: 'every file that refers to the moved content and must point to its new place' },
    }, required: ['id', 'what', 'from', 'to', 'kind', 'why', 'evidence', 'pointers'] } },
    considered_and_left: STRS,
  },
  required: ['moves', 'considered_and_left'],
}

const VERDICT = {
  type: 'object',
  properties: {
    accept: { type: 'boolean', description: 'false whenever blocking is not empty' },
    blocking: { type: 'array', items: { type: 'object', properties: { path: REL, line: { type: 'integer' }, problem: STR, fix: STR }, required: ['path', 'problem', 'fix'] } },
    minor: STRS,
  },
  required: ['accept', 'blocking', 'minor'],
}
const accepted = v => !!v && v.accept && !v.blocking.length

const APPLIED = {
  type: 'object',
  properties: {
    applied: { type: 'array', items: { type: 'object', properties: {
      id: STR, commit: STR, created: RELS, deleted: RELS, changed: RELS,
      unit_of_created: { type: 'array', items: { type: 'object', properties: { path: REL, unit: STR }, required: ['path', 'unit'] } } },
      required: ['id', 'commit', 'created', 'deleted', 'changed', 'unit_of_created'] } },
    skipped: STRS,
    head: { ...STR, description: 'git rev-parse HEAD of the worktree after the last commit' },
    clean: { type: 'boolean', description: 'git status --porcelain of the worktree prints nothing' },
  },
  required: ['applied', 'skipped', 'head', 'clean'],
}

const SETTLED = {
  type: 'object',
  properties: { reverted: { ...STRS, description: 'the shas of the move commits reverted, not of the revert commits' }, head: STR, clean: { type: 'boolean' }, reset: { type: 'boolean', description: 'true when the worktree went back to the run\'s start' } },
  required: ['reverted', 'head', 'clean', 'reset'],
}

const FINDINGS = {
  type: 'object',
  properties: {
    findings: { type: 'array', items: { type: 'object', properties: {
      path: REL, line: { type: 'integer' },
      kind: { type: 'string', enum: ['broken-ref', 'wrong-claim', 'inventory', 'duplication', 'contradiction', 'naming', 'stale', 'public', 'growth', 'reevaluate', 'code-cluster', 'other'] },
      problem: STR, fix: STR,
      owner: { ...REL, description: 'for duplication: the file that keeps the rule' },
      files: { ...RELS, description: 'for code-cluster: every file of the cluster, the shared module included' },
      target: { ...REL, description: 'for code-cluster: the shared module that receives the duplicated code' },
    }, required: ['path', 'kind', 'problem', 'fix'] } },
    notes: STR,
  },
  required: ['findings', 'notes'],
}

const POLISHED = {
  type: 'object',
  properties: {
    changes: { type: 'array', items: { type: 'object', properties: { path: REL, what: STR, why: { ...STR, description: 'the rule id, standard or finding the change answers' } }, required: ['path', 'what', 'why'] } },
    created: { ...RELS, description: 'files this unit created (code clusters only)' },
    follow_ups: { type: 'array', items: { type: 'object', properties: { path: REL, what: STR, why: STR }, required: ['path', 'what', 'why'] } },
    proposals: { type: 'array', items: { type: 'object', properties: {
      path: REL, old: STR, new: STR, why: STR,
      needs: { ...STR, description: 'what must happen before it lands: an eval iteration, a measurement, a decision, the owner unit' } },
      required: ['path', 'why', 'needs'] } },
    tests: { type: 'array', items: { type: 'object', properties: { command: STR, passed: { type: 'boolean' } }, required: ['command', 'passed'] } },
    unverified: STRS,
    skill_used: { ...STR, description: 'code units: the skill invoked and its outcome, or why it could not run' },
  },
  required: ['changes', 'created', 'follow_ups', 'proposals', 'tests', 'unverified'],
}

const REPAIRED = {
  type: 'object',
  properties: {
    fixed: STRS,
    rejected: { type: 'array', items: { type: 'object', properties: { finding: STR, why: STR }, required: ['finding', 'why'] }, description: 'findings judged wrong, with the reason' },
    unresolved: { ...STRS, description: 'findings that stand and could not be fixed' },
  },
  required: ['fixed', 'rejected', 'unresolved'],
}

const CLEAN = { type: 'object', properties: { clean: { type: 'boolean' } }, required: ['clean'] }

const CHECKED = {
  type: 'object',
  properties: {
    ok: { type: 'boolean', description: 'true when no check fails beyond failing_before' },
    checks: { type: 'array', items: { type: 'object', properties: { command: STR, passed: { type: 'boolean' }, note: STR }, required: ['command', 'passed'] } },
    reverted: { type: 'array', items: { type: 'object', properties: { path: REL, why: STR }, required: ['path', 'why'] } },
    reverted_moves: STRS,
    head: { ...STR, description: 'git rev-parse HEAD of the worktree at the end' },
    follow_ups_applied: { type: 'array', items: { type: 'object', properties: { unit: STR, paths: RELS }, required: ['unit', 'paths'] } },
    notes: STR,
  },
  required: ['ok', 'checks', 'reverted', 'reverted_moves', 'head', 'follow_ups_applied', 'notes'],
}

const COMMITTED = {
  type: 'object',
  properties: {
    ok: { type: 'boolean', description: 'true when the committed tree is clean and every check passes beyond failing_before' },
    commits: { type: 'array', items: { type: 'object', properties: { sha: STR, subject: STR, files: RELS }, required: ['sha', 'subject', 'files'] } },
    checks: { type: 'array', items: { type: 'object', properties: { command: STR, passed: { type: 'boolean' }, note: STR }, required: ['command', 'passed'] } },
    notes: STR,
  },
  required: ['ok', 'commits', 'checks', 'notes'],
}

const MERGED = {
  type: 'object',
  properties: {
    merged: { type: 'boolean' },
    main_commit: STR,
    branch_deleted: { type: 'boolean' },
    worktree_removed: { type: 'boolean' },
    waits_because: STR,
    report: STR,
  },
  required: ['merged', 'main_commit', 'branch_deleted', 'worktree_removed', 'waits_because', 'report'],
}

// ---------------------------------------------------------------- preflight, guards, standards

const preflightPrompt = `You prepare a polishing run over the Construct3-RAG repository. A later stage rewrites its text and code in a worktree of its own; you find what is safe to touch. Other Claude Code sessions may be working in the repository now: write nothing into their worktrees and do not change the main clone's working tree.

Environment: Windows with Git Bash; Python is \`python\`. Quote paths in commands. Run git as \`git -C "<folder>" ...\`, one command per call. Write under .local/ with Bash or a Python one-off, because a hook may refuse Edit and Write there. Commit nothing.

1. MAIN, the main clone: ${A.root ? `"${A.root}"` : 'the first worktree that `git worktree list --porcelain` prints from your current directory'}. Report it with forward slashes.
2. STAMP: the local date and time, \`date +%Y%m%d-%H%M\`. HEAD_SHA: \`git -C MAIN rev-parse main\`, read once; every later step uses this sha, never the name main or HEAD.
3. Holders, the files other sessions hold:
${HOLDERS_HOWTO('MAIN')}
busy_files is the union of the files of the holders that are not stale, as repository-relative paths.
4. Base and changed files. ${A.base ? `The base is ${A.base}.` : 'Read MAIN/.local/polish/state.json if it exists: {"base", "polished": [sha], "carry": [path], "standards_stamp"}. If MAIN/.local/polish/pending.json exists, it records a run whose branch waited: when `git -C MAIN cherry main <its "tip">` prints no line starting with "+" and either there is no state.json or `git -C MAIN merge-base --is-ancestor <state base> <pending base>` succeeds, the branch was merged later: write pending.json\'s content as state.json and delete pending.json. The base is state.json\'s "base".'} ${SCOPE === 'all' ? 'The scope is all.' : 'changed_files are the files touched by the commits of base..HEAD_SHA, leaving out the commits listed in "polished", plus the paths in "carry". With no base the scope is all.'}
5. ${BUSY === 'stop' ? 'If busy_files is not empty, return ok=false with stop_reason naming the holders, and stop.' : 'Busy files stay in their units; the run leaves them alone.'}
6. ${A.dry_run ? 'This is a dry run: create no worktree; worktree is the folder a run would use, branch is empty, report_dir is the folder a run would use, and failing_before is empty.' : 'Create the polish worktree: `git -C MAIN worktree add -b polish/STAMP "MAIN/.claude/worktrees/polish-STAMP" HEAD_SHA`, where HEAD_SHA is the sha of step 2; that folder is WT. Confirm that `git -C MAIN check-ignore -q .local/polish/x` exits 0, then create MAIN/.local/polish/STAMP/ as report_dir. Run the tests once before anything changes: `cd "WT" && python -m pytest -q -p no:cacheprovider -rf` (allow 10 minutes), and list every failing node id in failing_before.'}
7. Units: partition the tracked files of ${A.dry_run ? 'MAIN at HEAD_SHA (git -C MAIN ls-tree -r --name-only HEAD_SHA)' : 'WT'} by the rules below. List each unit's tests: grep tests/ for the unit's module and file names, and include tests that read its text.
${UNIT_RULES}
8. Examples for the output sweep: ${A.examples ? `"${A.examples}"` : 'the example-projects folder of the Construct-Example-Projects clone beside MAIN'}; empty when it does not exist.
9. standing_proposals: read MAIN/.local/polish/proposals.json if it exists ({path: {"blob": sha, "stamp"}}); list each path whose \`git -C MAIN rev-parse HEAD_SHA:<path>\` still equals its blob.
10. standards_due: ${A.refresh_standards ? 'true.' : 'true when state.json has no "standards_stamp" or it is 30 or more days before STAMP; else false.'}
11. forbidden_files: those of MAIN/.local/polish/forbidden.txt and MAIN/.local/docs/evidence/c3-reference-games/catalog.json that exist. Do not copy names out of them.

Return every field of the schema; paths are repository-relative with forward slashes unless a field says absolute. ok is false only when the run cannot go on (no clone, the worktree failed, the busy policy stopped it), with stop_reason; otherwise stop_reason is empty.`

const GUARD_AREAS = [
  { key: 'instructions-docs', areas: ['instructions', 'readme', 'docs'] },
  { key: 'records', areas: ['records'] },
  { key: 'prompts', areas: ['prompts'] },
  { key: 'skill-agents', areas: ['skill', 'agents'] },
  { key: 'code', areas: ['code'] },
]

const guardPrompt = (root, units) => `You find the guarded passages of part of the Construct3-RAG repository, in "${root}", before a run polishes it. The polishing agents keep every passage you list byte-identical and only propose changes to it, so a passage you miss can be lost. Read only; change no file.

Run git as \`git -C "${root}" ...\`. Use Grep and Read with absolute paths under "${root}".

${GUARD_RULES}

For each file below: grep tests/ for its name and for its distinctive sentences, headings and strings (\`git -C "${root}" grep -n -F "<text>"\`); grep docs/decisions/, every AGENTS.md, skills/, prompts/ and the scripts for citations of its headings, section numbers and name; read the decision records the file's area cites. Report each guarded passage with the file; in what, the passage itself, so that a later agent can find it and compare it byte for byte: the heading text, a sentence's first words and its line, a function or constant name, or a block's first line and line range. what is never empty: a whole file that must stay, beyond those below, is reported with what set to "the whole file". Add the rule it rests on and the evidence (the test, the record or the citing file and line). Whole files that need an eval are known already: ${JSON.stringify(WHOLE_GUARDS.map(([r]) => String(r)))}; do not list them.

Files:
${JSON.stringify(units.map(u => ({ unit: u.id, paths: u.paths })))}`

const standardsPrompt = `You bring the official guidance for agent-facing text and tools up to date, for a run that polishes a repository. Read only; change no file.

Use WebFetch and WebSearch (load them with ToolSearch first if they are listed as deferred). Fetch each source below; when one moved, find it with WebSearch. Compare what the sources state now with the baseline: keep each baseline item that a source still states, correct one that changed, add one that a source states and the baseline lacks, and mark one that no source states any more as gone. Take nothing from outside the sources, and quote nothing longer than 15 words.

Sources:
${STANDARDS_SOURCES}

Baseline:
${STANDARDS_BASELINE}

Return the current items grouped by the kind of file they apply to, every difference from the baseline under deltas with its source, and the sources you could not reach. If you reach none, return the baseline unchanged and list them all as unreachable.`

// The baseline's groups, keyed by the kind of file: a group starts with a line "<kind>:".
const BASELINE_GROUPS = STANDARDS_BASELINE.split('\n').reduce((groups, line) => {
  const head = /^([a-z-]+):$/.exec(line)
  if (head) groups.push({ kind: head[1], lines: [] })
  else if (groups.length) groups[groups.length - 1].lines.push(line)
  return groups
}, [])
const standardsFor = (std, unit) => {
  const kinds = AREA_KINDS[unit.area] || []
  const items = std ? std.by_kind.filter(k => kinds.includes(k.kind)) : []
  if (items.length) return JSON.stringify(items)
  return `${BASELINE_GROUPS.filter(g => kinds.includes(g.kind)).map(g => `${g.kind}:\n${g.lines.join('\n')}`).join('\n')}\nSources: ${STANDARDS_SOURCES.split('\n').join('; ')}`
}

// ---------------------------------------------------------------- restructure

const guardsOf = (units, paths) => units.filter(u => u.paths.some(p => paths.includes(p))).flatMap(u => u.guarded)
const busyOf = (units, paths) => units.filter(u => u.paths.some(p => paths.includes(p))).flatMap(u => u.busy)
const lockedFiles = units => uniq(units.flatMap(u => [...u.paths.filter(p => wholeGuard(p)), ...u.busy]))
const passages = units => units.flatMap(u => u.guarded.filter(g => g.what))

const planPrompt = (pre, units) => `You plan the moves between files that would make the Construct3-RAG repository easier to use, in the worktree "${pre.worktree}". Later stages polish the wording inside each file; you decide only where content lives. Read only; change no file.

Run git as \`git -C "${pre.worktree}" ...\`; read files by absolute path under the worktree.

A move changes where content lives: a section that belongs to another file's job, two files that do one job, one file doing two jobs, a rule repeated in several files that should live in one, a decision record whose decision applies to nothing that exists (docs/AGENTS.md: such a record is deleted). A record that gives the reason for a removal (remove-*.md, or any record whose decision removed a feature) is never deleted, because root AGENTS.md section 5 keeps that reason in docs/decisions/.

Read the routing of the repository first: the tables of the root AGENTS.md (sections 2 and 7), docs/AGENTS.md, skills/AGENTS.md, and "How the prompts are kept" in docs/decisions/event-sheet-design-guidance.md. A move agrees with them, or changes them in the same move.
Growth since the base: \`git -C "${pre.worktree}" log --stat ${pre.base ? pre.base + '..HEAD' : '-n 200'}\`. Growth is where content piles up in the wrong place.

Moves touch Markdown files only; code in the wrong place is the code-duplication sweep's job. Leave out: files that no unit lists (never polished), whole guarded files, busy files, any move that would change or relocate a guarded passage, any move whose benefit you cannot show from the repository itself${PATHS.length ? `, and any move that touches a file outside ${JSON.stringify(PATHS)}` : ''}. Plan at most ${MAX_MOVES} moves, the most useful first; put the next candidates under considered_and_left with one line each.

${TEXT_RULES}

Units with their guarded files and passages and their busy files:
${JSON.stringify(units.map(u => ({ id: u.id, paths: u.paths, guarded: u.guarded, busy: u.busy })))}`

const judgePrompt = (pre, units, mv, lens) => `You judge one planned move between files in the Construct3-RAG worktree "${pre.worktree}", before it is applied. Read only. When unsure, reject.

Move: ${JSON.stringify(mv)}
Guarded passages and busy files of the files involved: ${JSON.stringify({ guarded: guardsOf(units, [...mv.from, ...mv.to, ...mv.pointers]), busy: busyOf(units, [...mv.from, ...mv.to, ...mv.pointers]) })}

${lens === 'reader'
    ? 'Lens: the reader. Follow the routes of the root AGENTS.md (sections 2 and 7) and of the game-project block (skills/construct3-agent-plugin/assets/game-project-block.md) as an agent arriving cold. After the move, does each route still land on the content, with no extra hop? Is the new place the one the routing tables would name? Would a small model that reads only SKILL.md and tool output lose anything?'
    : 'Lens: the evidence. Is the problem the move claims real (read the files)? Does the move lose content, change a rule, change or relocate a guarded passage, touch a busy file, turn the decision a record states or a pitfall entry into a pointer, delete a record that gives the reason for a removal, or contradict docs/AGENTS.md, skills/AGENTS.md or a decision record? Is every pointer listed?'}

Accept only a move that is right on your lens. Put what must change in the move into blocking; accept is false when blocking is not empty.`

const applyMovesPrompt = (pre, units, moves) => `You apply accepted moves between files in the polish worktree, one commit per move. Later stages polish the wording; keep the text as it is apart from the joins.

${env(pre)}

For each move, in order:
1. Read every file in from, to and pointers.
2. Move the content as planned, meeting the judges' conditions. Keep every fact, rule, condition, number, command, path, example and reason. Update every pointer and every routing table that names the old place (the root AGENTS.md sections 2 and 7, docs/AGENTS.md's table of records, the index of prompts/event-sheet-pitfalls.md, skills/AGENTS.md).
3. Leave these alone; skip a move that needs one of them changed. Whole files and busy files: ${JSON.stringify(lockedFiles(units))}. Passages, which stay byte-identical and in their file: ${JSON.stringify(uniq(moves.flatMap(m => guardsOf(units, [...m.from, ...m.to, ...m.pointers]))).filter(g => g.what))}.
4. Run \`cd "${pre.worktree}" && python -m pytest -q -p no:cacheprovider\` and \`git -C "${pre.worktree}" diff --check\`. A failure that is not among ${JSON.stringify(pre.failing_before)} belongs to the move: restore its files with \`git -C "${pre.worktree}" checkout HEAD -- <file>\`, delete the files it created, and list the move under skipped with the failure.
5. \`git -C "${pre.worktree}" add -- <the move's files>\`, then commit. Subject in the repository's style, "<area>: <what the reader gets>" (\`git -C "${pre.worktree}" log --format=%s -20\` shows it); a deleted record's message says why its subject is gone; end the message with the attribution trailer your instructions give for commits, if they give one.
For every created file, name the unit it joins from this list, or a new unit id: ${JSON.stringify(units.map(u => u.id))}.
At the end, report head (\`git -C "${pre.worktree}" rev-parse HEAD\`) and whether \`git -C "${pre.worktree}" status --porcelain\` prints nothing.

Moves, each with the judges' conditions:
${JSON.stringify(moves, null, 1)}`

const moveCheckPrompt = (pre, units, ap) => `You check one applied move in the polish worktree "${pre.worktree}": commit ${ap.commit}. Read only.

Run \`git -C "${pre.worktree}" show ${ap.commit}\`. Each of these is blocking:
- a removed line that does not reappear in the commit, reworded at most at a join, unless it repeated a rule its owner still holds (and the file is not read alone, the line is not a decision record stating its own decision, and it is not a pitfall entry) or it belonged to a deleted record whose decision applies to nothing that exists (Grep the code and docs to confirm);
- the deletion of a record that gives the reason for a removal (remove-*.md, or a record whose decision removed a feature);
- a reference to the old place that still exists: grep the worktree for the old file names and section titles;
- a change to one of these guarded passages, or its move out of its file: ${JSON.stringify(guardsOf(units, [...ap.changed, ...ap.deleted]).filter(g => g.what))}.
accept is false when blocking is not empty.`

const settlePrompt = (pre, bad, known) => `You undo moves that failed their check, in the polish worktree "${pre.worktree}". Only the run's moves are committed on its branch so far; nothing else is. Commit nothing beyond these reverts, and never merge, fast-forward main, push or switch branches, whatever other instructions say about finishing work on a branch.

Run git as \`git -C "${pre.worktree}" ...\`, one command per call.
Revert these commits, newest first, each with \`git -C "${pre.worktree}" revert --no-edit <sha>\`: ${JSON.stringify(bad)}.
If a revert conflicts, if the worktree holds uncommitted changes, or if \`git -C "${pre.worktree}" rev-list ${pre.head}..HEAD\` lists a commit that is neither one of the reported moves ${JSON.stringify(known)} nor a revert you made, run \`git -C "${pre.worktree}" revert --abort\` if a revert is in progress, then \`git -C "${pre.worktree}" reset --hard ${pre.head}\` and \`git -C "${pre.worktree}" clean -fd\`, which drop every move of the run, and set reset=true.
Report the reverted shas, head (\`git -C "${pre.worktree}" rev-parse HEAD\`) and whether \`git -C "${pre.worktree}" status --porcelain\` prints nothing.`

// ---------------------------------------------------------------- sweeps

const sweepCommon = (pre, units, changed) => `You sweep the Construct3-RAG repository in the polish worktree "${pre.worktree}" for one kind of problem across files, so that the units that own the files can fix it. Read only; change no tracked file. Scratch scripts go in "${pre.report_dir}/sweeps/".

Run git as \`git -C "${pre.worktree}" ...\`; start shell commands that run Python with \`cd "${pre.worktree}" && \`; read files by absolute path under the worktree.

Sweep only these polishable files: ${JSON.stringify(units.flatMap(u => u.paths))}. Report each problem at the file and line that must change, with the exact fix, and verify it before you report it; drop what you cannot verify. Report a problem in guarded text too: the unit that owns it turns it into a proposal.
${changed ? `Report broken references, wrong claims and inventories anywhere; report other problems only when one of their files is among these changed files: ${JSON.stringify(changed)}.` : ''}
${TEXT_RULES}`

const SWEEPS = [
  { key: 'references', prompt: pre => `Problem: references that do not resolve, and claims about a script that are not true. Write a Python script that collects, from every polishable .md file and from the docstrings and help texts of the .py files: relative Markdown links; backticked repository paths (they contain a slash or end in .md, .py or .json); every --flag that stands next to a script name, whatever the sentence; citations of a section by its title. Resolve each: the file exists in the worktree, the flag is in the script's --help, the title is a heading of the cited file. Paths written for a game project (eventSheets/, layouts/, .agents/skills/..., tools/build_project.py, Construct3-RAG/<path>) resolve against the game project's layout or this repository: read the context. A decision record names what its decision removed, renamed or replaced, and the state before the change, on purpose: such a name is no broken reference. Collect also the helper and function names that a fenced code example calls, and grep for each in the module the example uses (skills/construct3-agent-plugin/assets/build_project.py, c3project.py, the script it names). Then, for each claim the text makes about what a read-only command prints or how long it takes (lookup_ace.py, print_sheet.py, print_layout.py, check_project.py, any --help), run the command in the worktree and compare; for a statement about every script or a named group of scripts (the flags they take, what they import, which files they write), check each script's --help and imports. The fix names the right target or the actual output, or says to drop the reference when its target is gone and nothing replaced it.` },
  { key: 'inventories', prompt: pre => `Problem: lists, tables and trees that do not cover what exists. Find every list or table that enumerates files, scripts, flags, records, finding kinds or folders: the table of records in docs/AGENTS.md, the script lists of README.md, README_CN.md, the root AGENTS.md and skills/AGENTS.md, the data tree of docs/guide/data-format.md, the source tables of docs/dev/, the file tables of the decision records (apart from a record's account of what its decision removed, renamed or replaced, and of the state before the change), the dev/ row of docs/AGENTS.md. Compare each with \`git -C "${pre.worktree}" ls-files\`, the scripts' --help and the enums in the code. Report each missing and each extra item at the line of the list, with the fix: complete the list, or, when the list only repeats what the code or a directory shows (official guidance "no-derivable"), replace it with a pointer to its owner.` },
  { key: 'duplication', prompt: pre => `Problem: one rule stated in several files, and statements that contradict each other. The owner of a rule is the file the repository's routing names for it: the tables of the root AGENTS.md (sections 2 and 7), docs/AGENTS.md, skills/AGENTS.md, the AGENTS.md of each directory, and "How the prompts are kept" in docs/decisions/event-sheet-design-guidance.md. A passage that another file cites by section, heading or path, or that shipped text routes to, is the copy that stays.
- For a duplicate, report each copy outside the owner with the fix "replace with a when-clause pointer to <owner>", and set owner. Do not report a copy in a file that is read alone (a sub-agent file, the prompts the README loads together as a system prompt, SKILL.md, the game-project block, script output), a decision record's own decision, or a pitfall entry and its conclusion line in the index; report those only when they disagree with the owner.
- For a contradiction, decide first whether the statement is a norm (a rule in an AGENTS.md or a record) or a description (what a module does, who imports whom). When code breaks a norm and a change that keeps behavior fixes it, report the code file and line with that change. When no such change exists, report it at the norm's line with the fix "needs a decision: <the code change or the rule change>". When a description is wrong, find what the code, the data or the tests support (run or read them) and report the wrong text.` },
  { key: 'names', prompt: pre => `Problem: one concept with several names, and names that do not match the code. Collect the names the repository gives to its tools, files, concepts and Construct terms (the script table in skills/construct3-agent-plugin/SKILL.md and the root AGENTS.md list the tool names). Report every place that uses another name for the same thing, with the owner's name as the fix. In Chinese text, a Construct term must be the zh-CN editor's: find its English key in data/c3-lang/en-US.json and take the zh-CN value of the same key from data/c3-lang/zh-CN.json; the Claude Code plugin stays "plugin".` },
  { key: 'stale', prompt: pre => `Problem: text that goes stale or must not be public. Report: versions and counts written into text (the release, numbers of addons or ACEs), apart from a record's Schema line, the release in a pitfall source and the release a measurement was made on; test totals in docs; tallies over the official examples stated as a rule, and minified editor names; relative or dated wording in project text ("now", "no longer", "new", "recently", "as of", "Update <date>"); TODO and FIXME lines whose work is done; commit hashes; the names of any game project or of its objects, variables and functions, the maintainer's own projects included; names of studied published games, their authors or source sites. Licence attributions and Scirra's own sources stay.${FORBIDDEN.length || pre.forbidden_files.length ? ` Grep case-insensitively for every name in ${FORBIDDEN.length ? 'this list: ' + JSON.stringify(FORBIDDEN) : ''}${FORBIDDEN.length && pre.forbidden_files.length ? ' and ' : ''}${pre.forbidden_files.length ? 'these files (names, titles and authors): ' + JSON.stringify(pre.forbidden_files) : ''}, with \`git -C "${pre.worktree}" grep -i -n -e "<name>"\`. In your report write such a name as its first letter and its length, never in full.` : ''}` },
  { key: 'growth', prompt: pre => `Problem: content that piles up. From \`git -C "${pre.worktree}" log --stat ${pre.base ? pre.base + '..HEAD' : '-n 300'}\` and the current sizes, find the files that grew most, and in each the sections that grew by appending: entries that repeat each other, an index whose lines do not follow their topic files, a list of cases that one rule would replace, a decision record that reads as a dated log of runs instead of the finding that settles it (docs/AGENTS.md), a file over a limit that its AGENTS.md or a record states. Report each with the fix: which entries merge into which, which lines go, and the rule that replaces a list of cases; give the numbers (lines added, commits) in problem. Then read the "Re-evaluate when" section of every record in docs/decisions/ and report, with kind "reevaluate", each condition that holds today (measure it: file sizes, counts, the code), at the record's line, with the action the record names.` },
  { key: 'code-duplication', prompt: pre => `Problem: code duplicated across files, which one shared helper would replace. Look in the polishable .py files for functions, constants, type definitions, path set-up and blocks repeated in two or more files. The shared module follows the repository's rules: the skill scripts share code through skills/construct3-agent-plugin/scripts/c3project.py (skills/AGENTS.md); the tests through tests/skill_helpers.py or conftest.py; a package through a module of its own. Report each cluster with kind "code-cluster", path set to one of its files, files listing every file of the cluster with the shared module included, target set to the shared module, and fix saying what moves there. Keep a cluster under about 4000 lines in all. Never include skills/construct3-agent-plugin/assets/build_project.py: its helpers stay inline because the evals showed that small models learn them there (docs/decisions/generator-helpers-inline.md).` },
]

// ---------------------------------------------------------------- polish, verify, repair

const editable = unit => unit.paths.filter(p => !unit.busy.includes(p) && !wholeGuard(p))

const textPolishPrompt = (pre, std, unit, found) => {
  const edit = APPLY ? editable(unit) : []
  const whole = unit.paths.filter(p => wholeGuard(p))
  const rewrite = pre.scope === 'changed' ? edit.filter(p => pre.changed_files.includes(p)) : edit
  return `You polish one unit of the Construct3-RAG repository: the same knowledge, easier for its next reader to use. Other agents polish other units in the same worktree at the same time; touch nothing outside yours. Reviewers compare your result with the text before you, line by line.

${env(pre)}
Leave your edits uncommitted.

Unit ${unit.id} (${unit.area}). Files: ${JSON.stringify(abs(pre, unit.paths))}.
${edit.length ? `You may edit: ${JSON.stringify(abs(pre, edit))}.` : 'Edit nothing: return every change as a proposal with the exact old and new text.'}
${whole.length ? `Guarded whole files, proposals only: ${JSON.stringify(whole.map(p => ({ path: p, rule: wholeGuard(p)[1] })))}.` : ''}
${unit.guarded.filter(g => g.what).length ? `Guarded passages, which stay byte-identical (propose a change instead): ${JSON.stringify(unit.guarded.filter(g => g.what))}.` : ''}
${unit.busy.length ? `Held by other sessions, read only: ${JSON.stringify(unit.busy)}.` : ''}
${pre.scope === 'changed' && edit.length ? `Rewrite where needed: ${JSON.stringify(rewrite)}. In the unit's other files fix only the problems listed below.` : ''}

Read first: each file in full; the root AGENTS.md and the AGENTS.md of every directory of the unit; the files the unit's text points to, as far as you need them to check a statement.

${TEXT_RULES}

Official guidance for this kind of file. Apply it to the form of what the file says; a change it calls for that would add a rule or new content is a proposal:
${standardsFor(std, unit)}

Problems the cross-file sweeps found in this unit. Verify each, then fix it, or say why not:
${found.length ? JSON.stringify(found, null, 1) : '(none)'}

Do:
- Leave a file unchanged when it already meets these rules. Each change names in why the rule id, the standard or the finding it answers.
- Rewrite from the final state; order a file by what its reader needs first; merge passages that say the same thing; cut what no reader needs.
- Keep every fact, rule, condition, number, command, path, example and reason, unless you verify that it is false or obsolete (the file, flag, function or feature it names is gone: Grep, Glob or --help; this never applies to a decision record's account of what it removed or replaced, or of the state before the change), or it repeats a rule whose owner keeps it, the file is not read alone, and you replace it with a pointer to the owner.
- Fix every reference that does not resolve.
Do not:
- edit, create or rename a file outside the files you may edit; return what another file needs as a follow-up;
- change the meaning of a rule: not weaker, not stronger, not with a new condition;
- rename a heading, a section number or a file name that another file cites (grep for it first); propose the rename instead.

Return what you changed and why, the follow-ups, the proposals, and what you could not verify. created stays empty.`
}

const codePolishPrompt = (pre, std, unit, found) => {
  const edit = APPLY ? editable(unit) : []
  const clusters = unit.clusters || []
  // A cluster reviews whole files: the shared module may not have changed since the base.
  const range = pre.scope === 'changed' && pre.base && !clusters.length ? `the changes that git diff ${pre.base}..${pre.head} shows in each file, with the code around them` : 'the whole content of each file'
  const targets = uniq(clusters.map(c => c.target)).filter(t => !unit.paths.includes(t))
  const guardedText = unit.guarded.length ? ` Keep these as they are: ${unit.guarded.map(g => `${g.path}: ${g.what || 'the whole file'}`).join('; ')}.` : ''
  const clusterText = clusters.length ? ` This unit is a cluster of duplicated code: ${clusters.map(c => `${c.problem} Move it into ${pre.worktree}/${c.target} and call it from each file.`).join(' ')}` : ''
  const foundText = found.length ? ` Also fix these problems that other reviews found, where a change that keeps behavior fixes them: ${found.map(f => `${f.path}${f.line ? ':' + f.line : ''} ${f.problem} (${f.fix})`.replace(/`/g, "'")).join('; ')}.` : ''
  return `You simplify one code unit of the Construct3-RAG repository with the simplify skill, keeping behavior identical. Other agents polish text in the same worktree at the same time; touch nothing outside your files. A reviewer then checks the diff with the code-review skill and the unit's tests.

${env(pre)}
Leave your edits uncommitted.

Unit ${unit.id}. Files: ${JSON.stringify(abs(pre, unit.paths))}.
${edit.length ? `You may edit: ${JSON.stringify(abs(pre, edit))}${targets.length ? `, and create ${JSON.stringify(abs(pre, targets))} if it does not exist` : ''}.` : 'Edit nothing: return every change as a proposal with its old and new code.'}
${unit.busy.length ? `Held by other sessions, read only: ${JSON.stringify(unit.busy)}.` : ''}
Tests of the unit: ${unit.tests.length ? JSON.stringify(unit.tests) : 'none; compile the files instead'}. Tests that failed before the run, which are not yours: ${JSON.stringify(pre.failing_before)}.

1. Read the AGENTS.md of the root and of the unit's directories: type hints, pathlib.Path, specific exceptions logged at the boundary, standard library only in skill scripts, shared helpers of skill scripts in c3project.py, what a skill script prints (skills/AGENTS.md).
2. ${edit.length ? `Invoke the Skill tool with skill "simplify" and these args, which the skill reads as its review target (plain text, no backticks):
   "Files: ${abs(pre, edit).join(', ')}. Review ${range}. Other files in this worktree carry other agents' uncommitted work: leave them alone.${clusterText}${foundText} Behavior stays identical: command-line flags and their help text, every module docstring that argparse prints, everything printed on stdout and stderr, exit codes, the files written and their format. Before renaming or removing any name, private ones included, grep the whole repository, JSON files included, and keep the name if anything outside the file uses it. No new dependency.${unit.paths.some(p => p.startsWith('tests/')) ? ' A test pins an expectation: never remove or weaken an assertion.' : ''}${guardedText}"
   If the Skill tool or the skill is not available, do the same review yourself on its questions (reuse of existing helpers, simpler code, efficiency, code at the right level) and say so in skill_used.` : `Invoke no skill, because simplify edits and code-review needs a diff. Review ${range} yourself on the questions of the simplify skill (reuse of existing helpers, simpler code, efficiency, code at the right level), under the same rule that behavior stays identical, and return each change as a proposal.`}
3. Problems the cross-file sweeps found in these files: ${found.length ? JSON.stringify(found) : '(none)'}. ${edit.length ? 'Fix each one that a change keeping behavior resolves, a rule of an AGENTS.md that the code breaks included, if the skill left it. A change to printed text, a public name or behavior is a proposal, and so is a module docstring that the script passes to argparse, because argparse prints it.' : 'Return a fix for each as a proposal.'}
4. ${unit.tests.length ? `Run \`cd "${pre.worktree}" && python -m pytest -q -p no:cacheprovider ${unit.tests.join(' ')}\`` : 'Run no tests'} and \`cd "${pre.worktree}" && python -m compileall -q ${unit.paths.join(' ')}\`. Fix what you broke; a file you cannot fix goes back with \`git -C "${pre.worktree}" checkout HEAD -- <file>\`. ${OTHERS_FAILURE}
5. If you or the skill edited a file outside the unit, undo those edits with Edit; you know them from your own calls. Never run checkout on another unit's file, because another agent may be editing it.

Official guidance for scripts, for the review (a change to printed output is a proposal):
${standardsFor(std, unit)}

Return what changed and why, the files you created, the tests with their results, follow-ups, proposals, and skill_used.`
}

const reviewPrompt = (pre, unit, res, round) => `You review one polished ${unit.kind} unit of the Construct3-RAG repository against its version before the polish. Read only; change no file.

Run git as \`git -C "${pre.worktree}" ...\`; start shell commands that run Python with \`cd "${pre.worktree}" && \`.
Unit ${unit.id}: ${JSON.stringify(abs(pre, editable(unit)))}. The polishing agent reported: ${JSON.stringify(res.changes)}${res.created && res.created.length ? `; created ${JSON.stringify(res.created)}` : ''}.
For each file: \`git -C "${pre.worktree}" diff HEAD -- <file>\` and \`git -C "${pre.worktree}" show HEAD:<file>\`.
Guarded passages, where any change is blocking: ${JSON.stringify(unit.guarded)}.
${round ? `This is the second round, after a repair. Earlier findings: ${JSON.stringify(round.findings)}. Findings the repair judged wrong, with its reasons: ${JSON.stringify(round.rejected)}. Blocking now is only an earlier finding that still stands after you weigh the repair's reason, or a problem in a line the repair changed.` : ''}

${unit.kind === 'code'
    ? `Lens: behavior. Invoke the Skill tool with skill "code-review" and args "medium ${abs(pre, editable(unit)).join(' ')}", and keep only findings in this unit's changes; if the skill is not available, review the diff yourself for bugs it introduces and say so under minor. Then check yourself: printed text, flags, help text, module docstrings that argparse prints, exit codes, written files and names that other files use (grep the repository, JSON included) are identical; no assertion was removed or weakened. ${unit.tests.length ? `Run \`cd "${pre.worktree}" && python -m pytest -q -p no:cacheprovider ${unit.tests.join(' ')}\`; a failure among ${JSON.stringify(pre.failing_before)} is not the unit's, and a failure in a file outside the unit is another agent's unfinished edit: run it again a minute later, and if it still fails, note it under minor.` : 'No test covers the unit: compile its files with python -m compileall -q.'} Each difference in behavior is blocking.`
    : `Lens: meaning. Each of these is blocking: a fact, rule, condition, number, command, path, example, link or reason of the old text that the new text lost, unless you confirm the reported justification (the thing is gone from the repository, outside a decision record's account of what it removed or replaced or of the state before the change; or the named owner file holds it and this file is not read alone, is not a decision record stating its own decision, and is not a pitfall entry); a rule made weaker, stronger or conditional; an instruction whose condition no longer comes first; a statement the repository does not support; a reference that does not resolve; a renamed heading or section that another file cites. ${unit.tests.length ? `Also run \`cd "${pre.worktree}" && python -m pytest -q -p no:cacheprovider ${unit.tests.join(' ')}\`; a failure among ${JSON.stringify(pre.failing_before)} is not the unit's, and a failure in a file outside the unit is another agent's unfinished edit: run it again a minute later, and if it still fails, note it under minor.` : ''}`}
Wording you would improve is minor. accept is false when blocking is not empty.`

const rulesPrompt = (pre, unit, round) => `You review a polishing pass over these files of the Construct3-RAG repository: ${JSON.stringify(abs(pre, editable(unit)))}. The scope is their uncommitted changes, \`git -C "${pre.worktree}" diff HEAD -- <file>\`; judge the new text only, against the project's rules (the root AGENTS.md, the AGENTS.md of each directory, docs/AGENTS.md) and the writing rules your instructions name.
Guarded passages, which must be byte-identical to HEAD: ${JSON.stringify(unit.guarded)}.

${TEXT_RULES}

Blocking are only: relative or dated wording; versions, counts, test totals or tallies written into text beyond the exceptions above; names that must not be public; a language rule broken; an ACE id out of its quotes or backticks; a guarded passage changed; a heading, section number or file name that another file cites renamed; the meaning of a rule changed. Everything else (sentence length, word choice, order, style) is minor.
${round ? `This is the second round, after a repair. Earlier findings: ${JSON.stringify(round.findings)}. Findings the repair judged wrong, with its reasons: ${JSON.stringify(round.rejected)}. Blocking now is only an earlier finding that still stands, or a problem in a line the repair changed.` : ''}
accept is false when blocking is not empty.`

const repairPrompt = (pre, unit, verdicts) => `You repair one polished unit of the Construct3-RAG repository after review. Other agents work in the same worktree; touch nothing outside your files.

${env(pre)}
Leave your edits uncommitted.

Files you may edit: ${JSON.stringify(abs(pre, editable(unit)))}.
Guarded passages, which stay byte-identical: ${JSON.stringify(unit.guarded)}.
Blocking findings: ${JSON.stringify(verdicts.flatMap(v => v.blocking), null, 1)}

For each finding: check it against the file and against the version before the polish (\`git -C "${pre.worktree}" show HEAD:<file>\`). Fix it when it is right. Put a finding you judge wrong under rejected, with the reason. Restore a file you cannot bring to a state that resolves its findings with \`git -C "${pre.worktree}" checkout HEAD -- <file>\`. ${unit.kind === 'code' ? (unit.tests.length ? `Then run \`cd "${pre.worktree}" && python -m pytest -q -p no:cacheprovider ${unit.tests.join(' ')}\` and restore what fails, apart from ${JSON.stringify(pre.failing_before)}. ${OTHERS_FAILURE}` : 'Then compile the files with python -m compileall -q.') : ''}
unresolved lists only findings that stand and that you could not fix.`

const revertPrompt = (pre, unit, created) => `Restore files of the polish worktree "${pre.worktree}" to HEAD, because their unit was not kept. Run git as \`git -C "${pre.worktree}" ...\`, one command per call; if git says index.lock exists, wait a few seconds and retry, and never delete the lock. Commit nothing.
1. For each of ${JSON.stringify(editable(unit))}: \`git -C "${pre.worktree}" checkout HEAD -- <file>\`.
2. Delete these files, which the unit created: ${JSON.stringify(created)}.
3. \`git -C "${pre.worktree}" diff --quiet HEAD -- <the files of step 1>\` must exit 0. clean is true when it does and the files of step 2 are gone.`

// ---------------------------------------------------------------- check, commit, review, merge

const checkPrompt = (pre, units, kept, followUps, moveCommits) => {
  const keepFiles = uniq(kept.flatMap(r => [...editable(r.unit), ...(r.polished.created || [])]))
  const sweepTail = pre.examples ? ` --examples "${pre.examples}"` : ''
  const projectsTail = PROJECTS.length ? ` --projects ${PROJECTS.map(p => `"${p}"`).join(' ')}` : ''
  const sweepNote = !pre.examples && !PROJECTS.length ? ' There is no examples folder and no game project: say in notes that the output sweep did not run.' : !PROJECTS.length ? ' No game project was given: say in notes that the output sweep covered the official examples only.' : ''
  return `You check the polished worktree before anything is committed: restore what was not kept, apply follow-ups, run the checks, and undo what breaks them. The next agent commits what you leave.

${env(pre)}
Commit nothing; only \`git revert\` of a move commit, in step 4, is allowed.

1. Restore. \`git -C "${pre.worktree}" status --porcelain\`. Every changed tracked file outside the keep list below goes back with \`git -C "${pre.worktree}" checkout HEAD -- <file>\`, and every untracked file outside it is deleted (ignored files such as __pycache__ stay).
2. Follow-ups that kept units asked for in other files (listed below). Apply each that is right and touches no file in ${JSON.stringify(lockedFiles(units))}, leaving these passages byte-identical: ${JSON.stringify(passages(units).filter(g => followUps.some(f => f.path === g.path)))}. Skip the others with the reason. Report the files each applied follow-up changed under follow_ups_applied, with the unit that asked for it.
3. Checks: \`cd "${pre.worktree}" && python -m pytest -q -p no:cacheprovider -rf\` (allow 10 minutes), \`cd "${pre.worktree}" && python -m compileall -q src scripts tests skills\`, \`git -C "${pre.worktree}" diff --check ${pre.head}\`, and the checks of the AGENTS.md of each touched directory. Tests in ${JSON.stringify(pre.failing_before)} failed before the run: list them in notes, they are no failure. The run's changes, the committed moves included, are what \`git -C "${pre.worktree}" diff --name-only ${pre.head}\` lists:
   - If it lists a file under skills/<skill>/scripts/: record the old and new output and compare. \`git -C "${pre.main}" worktree add --detach "${pre.report_dir}/old" ${pre.head}\`, then \`cd "${pre.report_dir}/old" && python skills/construct3-agent-plugin/evals/sweep_outputs.py "${pre.report_dir}/sweep-old.json" --scripts "${pre.report_dir}/old/skills/construct3-agent-plugin/scripts"${sweepTail}${projectsTail}\`, then the same command for the new side with --scripts "${pre.worktree}/skills/construct3-agent-plugin/scripts" and "${pre.report_dir}/sweep-new.json", then \`--compare\` of the two (allow 10 minutes each).${sweepNote} For a changed script that sweep_outputs.py does not run, compare its --help output on both sides. Any difference fails the unit or move whose change printed it. Afterwards \`git -C "${pre.main}" worktree remove --force "${pre.report_dir}/old"\`.
   - If it lists a file under src/: run the service the way src/AGENTS.md asks. Find a free port with \`python -c "import socket;s=socket.socket();s.bind(('127.0.0.1',0));print(s.getsockname()[1])"\`, start \`cd "${pre.worktree}" && python -m uvicorn src.api:app --port <port>\` in the background with its output in "${pre.report_dir}/service.log", note its PID, wait until the log says it is running, GET /health, POST /search with one query of tests/fixtures/query_gold.jsonl and check the answer against that case, then stop only that PID (\`taskkill //PID <pid> //T //F\`).
4. On a failure, find what caused it and undo that, then run the checks again, until no failure is left beyond failing_before. A failure in a unit's files: restore that unit's files and delete the files it created. A failure in a follow-up: restore its files. A failure in a move commit of ${JSON.stringify(moveCommits.map(m => m.sha))}: first restore the kept units' files that the move touched and list them under reverted, then \`git -C "${pre.worktree}" revert --no-edit <sha>\` and list the sha under reverted_moves; if the revert conflicts, run \`git -C "${pre.worktree}" revert --abort\` and return ok=false. List every restored file under reverted with the reason.
5. Report head, \`git -C "${pre.worktree}" rev-parse HEAD\`.

ok is true when no check fails beyond failing_before.

Keep list (files of kept units): ${JSON.stringify(keepFiles)}

Kept units, with the files each changed or created:
${JSON.stringify(kept.map(r => ({ id: r.unit.id, files: uniq([...(r.polished.changes || []).map(c => c.path), ...(r.polished.created || [])]) })))}

Follow-ups:
${JSON.stringify(followUps, null, 1)}`
}

const commitPrompt = (pre, kept, checked) => `You commit the checked polish of the Construct3-RAG repository, unit by unit, on the run's branch.

${env(pre)}
Commit in this step; never merge.

1. For each unit below, in order: \`git -C "${pre.worktree}" add -- <its files that still differ from HEAD>\`, then commit. Subject in the repository's style, "<area>: <what the reader gets>" (\`git -C "${pre.worktree}" log --format=%s -20\` shows it); a body only when the subject cannot say why; end the message with the attribution trailer your instructions give for commits, if they give one. A commit message names an issue of another repository in words or as a URL in backticks, never as owner/repo#N or #N, because GitHub turns those into a permanent cross-reference on that issue. Follow-ups go with the unit that asked for them.
2. \`git -C "${pre.worktree}" status --porcelain\` must print nothing afterwards; delete an untracked file the run left, restore a changed file that belongs to no unit, and say so in notes.
3. On the committed tree: \`cd "${pre.worktree}" && python -m pytest -q -p no:cacheprovider\`, \`cd "${pre.worktree}" && python -m compileall -q src scripts tests skills\`, \`git -C "${pre.worktree}" diff --check ${pre.head} HEAD\`. Tests in ${JSON.stringify(pre.failing_before)} failed before the run.

Units and their files:
${JSON.stringify(kept.map(r => ({ id: r.unit.id, area: r.unit.area, files: uniq([...(r.polished.changes || []).map(c => c.path), ...(r.polished.created || []), ...(checked.follow_ups_applied || []).filter(f => f.unit === r.unit.id).flatMap(f => f.paths.map(String))]).filter(p => !(checked.reverted || []).some(x => x.path === p)) })), null, 1)}

ok is true when the tree is clean and every check passes beyond failing_before.`

const REVIEW_LENSES = [
  { key: 'routes', prompt: pre => `Lens: routes. An agent arrives cold. Take every question of the table in section 2 of the root AGENTS.md and every row of section 7, and the steps of the game-project block (skills/construct3-agent-plugin/assets/game-project-block.md); follow each route and confirm it lands on content that answers it. Check every relative link, backticked path and cited heading in the files the branch changed, the table of records in docs/AGENTS.md against docs/decisions/, the index of prompts/event-sheet-pitfalls.md against its topic files, and README.md against README_CN.md (the same content, apart from the Chinese examples that stay in README_CN.md).` },
  { key: 'rules', prompt: pre => `Lens: project rules over the branch's changes and its commit messages (\`git -C "${pre.worktree}" log ${pre.head}..HEAD\`).\n\n${TEXT_RULES}\n\nAlso: a commit message names an issue of another repository in words or as a URL in backticks, never as owner/repo#N or #N, because GitHub turns those into a permanent cross-reference on that issue.${FORBIDDEN.length || pre.forbidden_files.length ? ` Grep the tracked files and the commit messages case-insensitively for every name in ${FORBIDDEN.length ? JSON.stringify(FORBIDDEN) : ''}${FORBIDDEN.length && pre.forbidden_files.length ? ' and in ' : ''}${pre.forbidden_files.length ? JSON.stringify(pre.forbidden_files) + ' (names, titles and authors)' : ''}; report a hit as its first letter and length, never in full.` : ''}` },
  { key: 'meaning', prompt: pre => `Lens: meaning across files. Units were polished separately, so the branch can contradict itself. Look for a rule that one file states differently from another, content that two units both dropped as "kept by the owner", a pointer to a section that the branch renamed, and a guarded passage that changed.` },
]

const reviewLensPrompt = (pre, units, lens, files) => `You review a polishing branch of the Construct3-RAG repository in the worktree "${pre.worktree}" before it merges into main. Read only; change no file. Run git as \`git -C "${pre.worktree}" ...\`.

The branch's changes: \`git -C "${pre.worktree}" diff ${pre.head}..HEAD\`. Guarded passages in the files it changed: ${JSON.stringify(passages(units).filter(g => files.includes(g.path)))}.

${lens.prompt(pre)}

Report as blocking only what the branch introduced: a line it added or changed, or a route, index, link or rule that held at ${pre.head} and does not at HEAD (check with \`git -C "${pre.worktree}" show ${pre.head}:<file>\`). A problem already present at ${pre.head} is minor. accept is false when blocking is not empty.`

const fixPrompt = (pre, units, verdicts, movesHead, files) => `You fix what the branch review found in the polish worktree of the Construct3-RAG repository. Every reviewer checks your commit again.

${env(pre)}
Commit in this step; never merge.

Blocking findings: ${JSON.stringify(verdicts.flatMap(v => v.blocking), null, 1)}
Edit only files that the branch changed (\`git -C "${pre.worktree}" diff --name-only ${pre.head}..HEAD\`), never ${JSON.stringify(lockedFiles(units))}, and keep these passages byte-identical: ${JSON.stringify(passages(units).filter(g => files.includes(g.path)))}.
A finding in a .py file is resolved by restoring the file, not by editing it, because no behavior review runs after this step.

Check each finding against the files and fix the ones that are right, writing by these rules:
${TEXT_RULES}

When a fix is not possible, restore the file to its state after the run's moves, \`git -C "${pre.worktree}" checkout ${movesHead} -- <file>\`; restore README.md and README_CN.md together. Run \`cd "${pre.worktree}" && python -m pytest -q -p no:cacheprovider\`, \`cd "${pre.worktree}" && python -m compileall -q src scripts tests skills\` and \`git -C "${pre.worktree}" diff --check ${pre.head}\` (tests in ${JSON.stringify(pre.failing_before)} failed before the run), then commit the fixes in one commit, "<area>: <what>", with the attribution trailer your instructions give for commits. ok is true when the checks pass and the tree is clean.`

const mergePrompt = (pre, summary, doMerge, record, stateObj) => {
  const lockedPatterns = [...NEVER, ...WHOLE_GUARDS].map(([r]) => String(r))
  const step1 = doMerge ? `Merge. Every check and review passed; merge unless one of these stops it, and then say why in waits_because and record the run as waiting (step 2):
   - \`git -C "${pre.main}" symbolic-ref --short HEAD\` must print main.
   - The files the branch changes: \`git -C "${pre.main}" diff --name-only --no-renames ${pre.head} ${pre.branch}\`. None of them may match one of these patterns: ${JSON.stringify(lockedPatterns)}. Find the holders again:
${HOLDERS_HOWTO(pre.main)}
     A file of the branch that a holder which is not stale by the rule above holds now, other than this run's own worktree and branch, stops the merge: name the holder.
   - \`git -C "${pre.main}" merge --ff-only ${pre.branch}\`. If Git refuses because main moved: the files main changed since the run started, \`git -C "${pre.main}" diff --name-only --no-renames ${pre.head} main\`, must not include a file of the branch, because no reviewer has read the two edits together; if they do, stop. Otherwise \`git -C "${pre.worktree}" switch -c ${pre.branch}-onto-main main\`, cherry-pick the branch's commits in order (\`git -C "${pre.worktree}" log --reverse --format=%H ${pre.head}..${pre.branch}\`), run \`cd "${pre.worktree}" && python -m pytest -q -p no:cacheprovider\` and \`cd "${pre.worktree}" && python -m compileall -q src scripts tests skills\` (tests in ${JSON.stringify(pre.failing_before)} failed before the run), read \`git -C "${pre.main}" rev-parse main\`, check \`git -C "${pre.main}" symbolic-ref --short HEAD\` again, then \`git -C "${pre.main}" merge --ff-only ${pre.branch}-onto-main\`. On a cherry-pick conflict, a test or compileall failure beyond failing_before, or when this fast-forward fails too: \`git -C "${pre.worktree}" cherry-pick --abort\` if one is in progress, \`git -C "${pre.worktree}" switch ${pre.branch}\`, \`git -C "${pre.worktree}" branch -D ${pre.branch}-onto-main\`, and stop.
   - After a merge: \`git -C "${pre.worktree}" status --porcelain\` must print nothing; then \`git -C "${pre.main}" worktree remove "${pre.worktree}"\`. Delete the run's branches with \`git -C "${pre.main}" branch -D <branch>\`: after a fast-forward, ${pre.branch}; after the cherry-pick path, ${pre.branch} and ${pre.branch}-onto-main, because every commit of the first is in the second, which main now holds.`
    : record === 'none' ? `Do not merge: the run committed nothing. Clean up: \`git --no-optional-locks -C "${pre.worktree}" status --porcelain\` must print nothing (restore or delete what it lists), then \`git -C "${pre.main}" worktree remove "${pre.worktree}"\` and \`git -C "${pre.main}" branch -D ${pre.branch}\`.`
    : 'Do not merge. Leave the worktree and the branch, and say in waits_because why (the gates in the run summary below show which one failed).'
  const step2 = record === 'none' ? 'The run committed nothing: write neither state.json nor pending.json.'
    : `Find the run's commits: after a fast-forward, \`git -C "${pre.main}" log --format=%H ${pre.head}..${pre.branch}\`; after the cherry-pick path, the commits of <main read before the fast-forward>..main; when the branch waits, \`git -C "${pre.worktree}" log --format=%H ${pre.head}..${pre.branch}\`. ${record === 'state' ? `If the merge happened, write "${pre.main}/.local/polish/state.json"; if it did not, write "${pre.main}/.local/polish/pending.json" instead, adding "tip": the branch's last commit.` : `Write "${pre.main}/.local/polish/pending.json", adding "tip": the branch's last commit; leave state.json as it is.`} Its content is this object, with the run's commits under "polished": ${JSON.stringify(stateObj)}. After writing state.json, delete pending.json if its "tip" is part of this run.`
  return `You finish a polishing run of the Construct3-RAG repository: ${doMerge ? 'merge it into main, ' : ''}record it, and write its report.

Environment: Windows with Git Bash; Python is \`python\`. Quote paths. Run git as \`git -C "<folder>" ...\`. ${LOCK_RULE} Write under .local/ with Bash or a Python one-off, because a hook may refuse Edit and Write there. Never push, rebase or force anything.

MAIN "${pre.main}"; worktree "${pre.worktree}"; branch ${pre.branch}; it started from ${pre.head}; report folder "${pre.report_dir}".

1. ${step1}
2. Record. ${step2}
3. Proposals: for every proposal on a file that is guarded as a whole, record {path: {"blob": <\`git -C "${pre.main}" rev-parse ${pre.head}:<path>\`>, "stamp": "${pre.stamp}"}} in "${pre.main}/.local/polish/proposals.json", merged with what it holds; the next run skips such a file while its blob is unchanged.
4. Report: write "${pre.report_dir}/report.md" in the language the user writes to you in (English if your instructions do not show it), split as the root AGENTS.md asks into verified, unverified, risk and next decision. Include: what changed, one line per commit; record conditions that the growth sweep found holding ("Re-evaluate when"), first; problems found in guarded files and proposals for them, grouped by what they need (an eval iteration of the skill, a measurement, a decision), each with its old and new text; what the units could not verify; follow-ups that were left; files left out because other sessions hold them, with the holders; stale holders and leftovers of earlier runs worth cleaning up; moves done, rejected and left; review findings that stayed open; tests that failed before the run; differences between the official guidance and the baseline in .claude/workflows/polish.js; the checks with their results.

Run summary:
${JSON.stringify(summary, null, 1)}`
}

// ---------------------------------------------------------------- run

phase('Preflight')
const pre = await agent(preflightPrompt, { label: 'preflight', phase: 'Preflight', schema: PREFLIGHT })
if (!pre || !pre.ok) {
  log(`not run: ${pre ? pre.stop_reason || 'no reason given' : 'the preflight agent failed'}`)
  return { ok: false, preflight: pre }
}

// Paths come back from agents in many spellings; units, findings and moves are compared in one.
pre.main = pre.main.replace(/\\/g, '/').replace(/\/+$/, '')
pre.worktree = pre.worktree.replace(/\\/g, '/').replace(/\/+$/, '')
const ROOTS = [pre.worktree + '/', pre.main + '/']
const rel = p => {
  const s = String(p).replace(/\\/g, '/').replace(/:\d+(-\d+)?$/, '').replace(/^\.\//, '')
  const root = ROOTS.find(r => s.toLowerCase().startsWith(r.toLowerCase()))
  return root ? s.slice(root.length) : s
}
const sameSha = (a, b) => !!a && !!b && (a.startsWith(b) || b.startsWith(a))
pre.changed_files = pre.changed_files.map(rel)
pre.busy_files = pre.busy_files.map(rel)
pre.standing_proposals = pre.standing_proposals.map(rel)

const excludedHere = []
let units = pre.units.map(u => {
  const paths = uniq(u.paths.map(rel))
  paths.filter(p => never(p)).forEach(p => excludedHere.push({ paths: p, reason: never(p)[1] }))
  const kept = paths.filter(p => !never(p))
  return {
    id: u.id, area: u.area, kind: u.kind, paths: kept, tests: u.tests,
    busy: kept.filter(p => pre.busy_files.includes(p)),
    guarded: [
      ...kept.filter(p => wholeGuard(p)).map(p => ({ path: p, what: '', rule: wholeGuard(p)[1] })),
      ...FIXED_PASSAGES.filter(g => kept.includes(g.path)),
    ],
    in_scope: false,
  }
}).filter(u => u.paths.length)
for (const u of units) {
  const files = u.paths.filter(inPaths)
  const changed = pre.scope === 'all' ? files : files.filter(p => pre.changed_files.includes(p))
  // A unit of guarded files whose proposals still stand has nothing new to say.
  const stands = files.length > 0 && files.every(p => wholeGuard(p) && pre.standing_proposals.includes(p))
  u.in_scope = changed.length > 0 && !stands
}

const runStandards = !A.dry_run && pre.standards_due
const guardRoot = A.dry_run ? pre.main : pre.worktree
const [guardResults, std] = await Promise.all([
  parallel(GUARD_AREAS.map(g => () => {
    const us = units.filter(u => g.areas.includes(u.area))
    return us.length ? agent(guardPrompt(guardRoot, us), { label: `guards:${g.key}`, phase: 'Preflight', schema: GUARDS }) : Promise.resolve({ guards: [] })
  })),
  runStandards ? agent(standardsPrompt, { label: 'standards', phase: 'Preflight', schema: STANDARDS }) : Promise.resolve(null),
])
const guardsMissing = GUARD_AREAS.filter((g, i) => !guardResults[i])
for (const g of guardResults.filter(Boolean).flatMap(r => r.guards)) {
  const path = rel(g.path)
  const u = units.find(x => x.paths.includes(path))
  if (!u) continue
  if (!g.what) { log(`a guard agent reported ${path} without a passage; it is kept as a whole file`); g.what = 'the whole file' }
  if (!u.guarded.some(x => x.path === path && x.what === g.what)) u.guarded.push({ path, what: g.what, rule: g.rule })
}
// An area whose guards are unknown is not polished: its passages could be lost.
const guardless = u => guardsMissing.some(g => g.areas.includes(u.area))
const inGuardless = p => units.some(u => guardless(u) && u.paths.includes(p))
if (guardsMissing.length) {
  for (const u of units) if (guardless(u)) u.in_scope = false
  log(`guard search failed for ${guardsMissing.map(g => g.key).join(', ')}; those areas are left out of this run`)
}
const holders = pre.holders.filter(h => !h.stale)
log(`${units.filter(u => u.in_scope).length} of ${units.length} units in scope; ${pre.busy_files.length} busy files from ${holders.length} holders; ${passages(units).length} guarded passages; ${pre.failing_before.length} tests failing before the run; guidance ${runStandards ? (std ? `re-read, ${std.deltas.length} differences` : 'agent failed, baseline used') : 'from the baseline'}`)
if (A.dry_run) return { ok: true, dry_run: true, preflight: pre, units, excluded: [...pre.excluded, ...excludedHere] }

const startUnits = JSON.parse(JSON.stringify(units))
// A unit of guarded files whose proposals still stand comes back only when its files change.
const standing = u => u.paths.every(p => wholeGuard(p) && pre.standing_proposals.includes(p))
const scopeUnit = u => { if (u && !guardless(u) && !standing(u) && u.paths.some(inPaths)) u.in_scope = true }

// Moves between files first, one commit each.
// Each unit is then polished in its final place, and its reviewers compare against the moved text.
let movesHead = pre.head
const moveCommits = []
const moveLog = { planned: [], accepted: [], rejected: [], applied: [], reverted: [], left: [] }
if (RESTRUCTURE && MAX_MOVES > 0) {
  phase('Restructure')
  const plan = await agent(planPrompt(pre, units), { label: 'restructure:plan', phase: 'Restructure', schema: MOVES })
  // A move may touch only Markdown that is polishable, guarded as searched, free of other sessions and of evals;
  // code in the wrong place is the code-duplication sweep's job, where simplify and code-review see it.
  const movable = p => p.endsWith('.md') && !never(p) && !wholeGuard(p) && !pre.busy_files.includes(p) && inPaths(p) && !inGuardless(p) && !/^(\/|[A-Za-z]:)/.test(p)
  const proposed = plan ? plan.moves.map(m => ({ ...m, from: m.from.map(rel), to: m.to.map(rel), pointers: m.pointers.map(rel) })) : []
  const planned = proposed.filter(m => [...m.from, ...m.to, ...m.pointers].every(movable)).slice(0, MAX_MOVES)
  if (proposed.length > planned.length) log(`${proposed.length - planned.length} planned moves touch locked files or exceed max_moves; they go to the report`)
  moveLog.planned = planned.map(m => m.id)
  moveLog.left = [...(plan ? plan.considered_and_left : []), ...proposed.filter(m => !planned.includes(m)).map(m => `${m.id}: ${m.what}`)]
  const judged = await parallel(planned.map(mv => () =>
    parallel(['reader', 'evidence'].map(lens => () =>
      agent(judgePrompt(pre, units, mv, lens), { label: `judge:${mv.id}:${lens}`, phase: 'Restructure', schema: VERDICT })))
      .then(vs => ({ mv, ok: vs.length === 2 && vs.every(accepted), notes: vs.filter(Boolean).flatMap(v => [...v.blocking.map(b => b.problem), ...v.minor]) }))))
  const agreed = judged.filter(Boolean).filter(j => j.ok)
  moveLog.accepted = agreed.map(j => j.mv.id)
  moveLog.rejected = judged.filter(Boolean).filter(j => !j.ok).map(j => ({ id: j.mv.id, why: j.notes }))
  log(`moves: ${planned.length} planned, ${agreed.length} accepted by both judges`)
  if (!APPLY) moveLog.proposed = agreed.map(j => j.mv)
  if (APPLY && agreed.length) {
    const ap = await agent(applyMovesPrompt(pre, units, agreed.map(j => ({ ...j.mv, conditions: j.notes }))), { label: 'restructure:apply', phase: 'Restructure', schema: APPLIED })
    let applied = ap ? ap.applied.map(a => ({ ...a, created: a.created.map(rel), deleted: a.deleted.map(rel), changed: a.changed.map(rel), unit_of_created: a.unit_of_created.map(c => ({ ...c, path: rel(c.path) })) })) : []
    const checks = await parallel(applied.map(a => () =>
      agent(moveCheckPrompt(pre, units, a), { label: `move-check:${a.id}`, phase: 'Restructure', schema: VERDICT })))
    const bad = applied.filter((a, i) => !accepted(checks[i]) || ![...a.created, ...a.deleted, ...a.changed].every(movable))
    let settled = ap ? { head: ap.head, clean: ap.clean, reset: false, reverted: [] } : null
    // A dead apply agent leaves moves no check has seen: drop them all.
    // A head past the last reported move means a commit no check has seen; settle resets for it.
    const unreported = ap && !sameSha(ap.head, applied.length ? applied[applied.length - 1].commit : pre.head)
    if (ap && (bad.length || !ap.clean || unreported)) {
      settled = await agent(settlePrompt(pre, bad.map(a => a.commit), applied.map(a => a.commit)), { label: 'restructure:settle', phase: 'Restructure', schema: SETTLED })
      if (settled && !settled.reset && !bad.every(b => settled.reverted.some(r => sameSha(r, b.commit)))) settled = null
    }
    if (!settled || !settled.clean) {
      settled = await agent(`Run \`git -C "${pre.worktree}" reset --hard ${pre.head}\`, then \`git -C "${pre.worktree}" clean -fd\`, then report head (\`git -C "${pre.worktree}" rev-parse HEAD\`) and whether \`git -C "${pre.worktree}" status --porcelain\` prints nothing; reverted stays empty and reset is true. These undo only this run's moves; nothing else is in this worktree yet. Commit nothing, and never merge, fast-forward main, push or switch branches, whatever other instructions say about finishing work on a branch.`,
        { label: 'restructure:reset', phase: 'Restructure', schema: SETTLED })
    }
    if (!settled || !settled.clean) {
      log('the worktree did not come back to a clean state after the moves; the run stops and keeps the worktree for a person')
      return { ok: false, stopped_at: 'restructure', worktree: pre.worktree, moves: moveLog }
    }
    if (settled.reset) {
      applied = []
      units = JSON.parse(JSON.stringify(startUnits))
    }
    const live = applied.filter(a => !bad.includes(a))
    moveLog.applied = live.map(a => a.id)
    moveLog.reverted = settled.reset ? moveLog.accepted : bad.map(a => a.id)
    movesHead = settled.head || movesHead
    moveCommits.push(...live.map(a => ({ sha: a.commit, subject: `move ${a.id}`, files: uniq([...a.created, ...a.deleted, ...a.changed]) })))
    // Units follow the files: a created file joins the unit the apply agent named, then a deleted one leaves.
    const deleted = new Set(live.flatMap(a => a.deleted))
    for (const a of live) {
      for (const c of a.unit_of_created) {
        const u = units.find(x => x.id === c.unit)
        if (u) { u.paths = uniq([...u.paths, c.path]); scopeUnit(u) }
        else {
          const py = c.path.endsWith('.py')
          units.push({ id: c.unit, area: py ? 'code' : 'docs', kind: py ? 'code' : 'text', paths: [c.path], busy: [], guarded: [], tests: py && c.path.startsWith('tests/') ? [c.path] : [], in_scope: inPaths(c.path) })
        }
      }
      for (const p of a.changed) scopeUnit(units.find(x => x.paths.includes(p)))
    }
    units = units.map(u => ({ ...u, paths: u.paths.filter(p => !deleted.has(p)) })).filter(u => u.paths.length)
  }
}

phase('Sweep')
const changedForSweep = pre.scope === 'changed' && pre.base ? pre.changed_files.filter(p => units.some(u => u.paths.includes(p))) : null
const swept = await parallel(SWEEPS.map(s => () =>
  agent(`${sweepCommon(pre, units, changedForSweep)}\n\n${s.prompt(pre)}`, { label: `sweep:${s.key}`, phase: 'Sweep', schema: FINDINGS })))
const sweepFailed = SWEEPS.filter((s, i) => !swept[i])
if (sweepFailed.length) log(`sweeps ${sweepFailed.map(s => s.key).join(', ')} failed; the changed files go to the next run`)
const findings = swept.filter(Boolean).flatMap(r => r.findings).map(f => ({ ...f, path: rel(f.path), owner: f.owner ? rel(f.owner) : f.owner, files: (f.files || []).map(rel), target: f.target ? rel(f.target) : f.target }))
const unitOf = p => units.find(u => u.paths.includes(p))

// A cluster of duplicated code becomes one unit, so that simplify can move the duplicate into its shared
// module; the units it joins are merged whole, so no file ends up in two units.
for (const c of findings.filter(f => f.kind === 'code-cluster' && f.target)) {
  const files = uniq([...c.files, c.target])
  const members = units.filter(u => u.kind === 'code' && u.paths.some(p => files.includes(p)))
  const blocked = !members.length || !files.every(inPaths) || files.some(p => wholeGuard(p) || pre.busy_files.includes(p)) || members.some(guardless)
  if (blocked) continue
  units = [...units.filter(u => !members.includes(u)), {
    id: members.map(m => m.id).join('+').slice(0, 80), area: 'code', kind: 'code',
    paths: uniq(members.flatMap(m => m.paths)), busy: uniq(members.flatMap(m => m.busy)),
    guarded: members.flatMap(m => m.guarded), tests: uniq(members.flatMap(m => m.tests)),
    clusters: [...members.flatMap(m => m.clusters || []), c], in_scope: true,
  }]
}
// A record condition that holds asks for an eval or a decision, which a polish cannot make: it goes to the report.
let unowned = 0
for (const f of findings.filter(f => f.kind !== 'reevaluate')) {
  const u = unitOf(f.path)
  if (u) scopeUnit(u)
  else unowned++
}
if (unowned) log(`${unowned} sweep findings point at files outside every unit (never polished or gone); they go to the report only`)

// A unit whose every file is busy has nothing to change; it is carried to the next run.
const todo = units.filter(u => u.in_scope && (editable(u).length || u.paths.some(p => wholeGuard(p) && !u.busy.includes(p))))
log(`polishing ${todo.length} units: ${todo.filter(u => u.kind === 'code').length} code, one at a time; ${todo.filter(u => u.kind === 'text').length} text; ${findings.length} sweep findings`)

// The rules lens runs as the session's writing reviewer when it has one (a user-level agent type), and as a
// plain agent with the same prompt when it does not.
const RULES_AGENT = 'writing-reviewer'
const rulesReview = async (unit, label, round) => {
  let v = null
  try {
    v = await agent(rulesPrompt(pre, unit, round), { label, phase: 'Verify', schema: VERDICT, agentType: RULES_AGENT })
  } catch (e) {
    v = null
  }
  return v || agent(rulesPrompt(pre, unit, round), { label: `${label}:plain`, phase: 'Verify', schema: VERDICT })
}
const review = (unit, polished, round) => {
  const tag = round ? ':2' : ''
  const lenses = [() => agent(reviewPrompt(pre, unit, polished, round), { label: `verify:${unit.id}${tag}`, phase: 'Verify', schema: VERDICT })]
  if (unit.kind === 'text') lenses.push(() => rulesReview(unit, `rules:${unit.id}${tag}`, round))
  return parallel(lenses).then(vs => ({ verdicts: vs.filter(Boolean), complete: vs.every(Boolean) }))
}
const passes = r => r.complete && r.verdicts.every(accepted)
const revert = async (unit, created) => {
  if (!APPLY || !editable(unit).length) return true
  const r = await agent(revertPrompt(pre, unit, created || []), { label: `revert:${unit.id}`, phase: 'Verify', schema: CLEAN })
  return !!(r && r.clean)
}

const polishStage = unit => {
  const found = findings.filter(f => unit.paths.includes(f.path) && f.kind !== 'code-cluster' && f.kind !== 'reevaluate')
  const prompt = unit.kind === 'code' ? codePolishPrompt(pre, std, unit, found) : textPolishPrompt(pre, std, unit, found)
  return agent(prompt, { label: `polish:${unit.id}`, phase: 'Polish', schema: POLISHED })
}
const verifyStage = async (polished, unit) => {
  if (!polished) return { unit, state: 'failed', polished, clean: await revert(unit, []) }
  polished.changes = polished.changes.map(c => ({ ...c, path: rel(c.path) }))
  polished.created = (polished.created || []).map(rel)
  polished.follow_ups = polished.follow_ups.map(f => ({ ...f, path: rel(f.path) }))
  if (!APPLY || !editable(unit).length) return { unit, state: 'unchanged', polished }
  if (!polished.changes.length && !polished.created.length) {
    // Code units run one after another, so a silent edit left here would break the next unit's tests.
    return { unit, state: 'unchanged', polished, clean: unit.kind === 'code' ? await revert(unit, []) : true }
  }
  const first = await review(unit, polished, null)
  if (passes(first)) return { unit, state: 'accepted', polished, verdicts: first.verdicts }
  const blocking = first.complete ? first.verdicts : [...first.verdicts, { blocking: [{ path: unit.paths[0], problem: 'a reviewer failed to report', fix: 'review the unit again' }] }]
  const fixed = await agent(repairPrompt(pre, unit, blocking), { label: `repair:${unit.id}`, phase: 'Verify', schema: REPAIRED })
  // One repair round, then the same reviewers again; a unit that still fails goes back to its old text.
  const second = fixed && !fixed.unresolved.length
    ? await review(unit, polished, { findings: blocking.flatMap(v => v.blocking), rejected: fixed.rejected })
    : null
  if (!second || !passes(second)) return { unit, state: 'reverted', polished, verdicts: second ? second.verdicts : first.verdicts, clean: await revert(unit, polished.created) }
  return { unit, state: 'repaired', polished, verdicts: second.verdicts }
}

// Text units run side by side; code units run one at a time, because each one's tests import modules that
// another code unit may be halfway through changing.
const textUnits = todo.filter(u => u.kind === 'text')
const codeUnits = todo.filter(u => u.kind === 'code')
const [textResults, codeResults] = await Promise.all([
  pipeline(textUnits, polishStage, verifyStage),
  (async () => {
    const out = []
    for (const u of codeUnits) {
      let r = null
      try { r = await verifyStage(await polishStage(u), u) } catch (e) { r = null }
      out.push(r)
      // Leftover edits would fail the next code unit's tests; the rest waits for the next run.
      if (r && r.clean === false) { log(`code unit ${u.id} could not be restored; the remaining code units wait for the next run`); break }
    }
    return out
  })(),
])
const done = [...textResults, ...codeResults].filter(Boolean)
const kept = done.filter(r => r.state === 'accepted' || r.state === 'repaired')
const proposals = done.flatMap(r => (r.polished && r.polished.proposals || []).map(p => ({ unit: r.unit.id, ...p, path: rel(p.path) })))
// A follow-up is a text edit to another file; code, locked and busy files get none, because nothing would review it.
const allFollowUps = kept.flatMap(r => r.polished.follow_ups.map(f => ({ unit: r.unit.id, ...f })))
const followable = f => f.path.endsWith('.md') && !never(f.path) && !wholeGuard(f.path) && !pre.busy_files.includes(f.path) && inPaths(f.path) && !inGuardless(f.path) && !/^(\/|[A-Za-z]:)/.test(f.path)
const followUps = allFollowUps.filter(followable)
const followUpsLeft = allFollowUps.filter(f => !followable(f))
const lost = todo.filter(u => !done.some(r => r.unit === u))
log(`units: ${kept.length} kept, ${done.filter(r => r.state === 'reverted').length} reverted, ${done.filter(r => r.state === 'unchanged').length} unchanged, ${done.filter(r => r.state === 'failed').length} failed${lost.length ? `, ${lost.length} lost` : ''}; ${proposals.length} proposals`)

const unitSummary = done.map(r => ({ id: r.unit.id, state: r.state, changes: r.polished ? r.polished.changes.length : 0, unverified: r.polished ? r.polished.unverified : [], skill_used: r.polished ? r.polished.skill_used || '' : '' }))

if (!APPLY) {
  phase('Merge')
  await agent(`Write "${pre.report_dir}/report.md" in the language the user writes to you in (English if your instructions do not show it), with Bash or a Python one-off: the findings and proposals of a report-only polishing run of the Construct3-RAG repository, grouped by unit, each with its file, its old and new text, and why; record conditions that the growth sweep found holding, first; the moves both judges accepted, those rejected and those left; the files left out because other sessions hold them, with the holders; tests that failed before the run. Then remove the run's worktree, which holds no change: \`git --no-optional-locks -C "${pre.worktree}" status --porcelain\` must print nothing (restore or delete what it lists), then \`git -C "${pre.main}" worktree remove "${pre.worktree}"\` and \`git -C "${pre.main}" branch -D ${pre.branch}\`. Commit nothing and never touch main.\n\n${JSON.stringify({ findings, proposals, units: unitSummary, moves: moveLog, holders: pre.holders, failing_before: pre.failing_before }, null, 1)}`,
    { label: 'report', phase: 'Merge' })
  return { ok: true, mode: 'report', report: `${pre.report_dir}/report.md`, units: done.length, findings: findings.length, proposals: proposals.length }
}

phase('Check')
const checked = await agent(checkPrompt(pre, units, kept, followUps, moveCommits), { label: 'check', phase: 'Check', schema: CHECKED })
const liveMoves = moveCommits.filter(m => !(checked && checked.reverted_moves.some(x => sameSha(x, m.sha))))
if (checked && checked.head && checked.reverted_moves.length) movesHead = checked.head
let committed = null
if (checked && checked.ok && kept.length) committed = await agent(commitPrompt(pre, kept, checked), { label: 'commit', phase: 'Check', schema: COMMITTED })
const commits = [...liveMoves, ...(committed ? committed.commits : [])]
const checksOk = !!(checked && checked.ok && (!kept.length || (committed && committed.ok)))

phase('Review')
let reviewOk = false
let reviewOpen = []
if (checksOk && commits.length) {
  const branchFiles = () => uniq(commits.flatMap(c => (c.files || []).map(rel)))
  const lensRun = (round) => parallel(REVIEW_LENSES.map(l => () =>
    agent(reviewLensPrompt(pre, units, l, branchFiles()), { label: `review:${l.key}${round}`, phase: 'Review', schema: VERDICT })))
  const first = await lensRun('')
  if (first.every(accepted)) reviewOk = true
  else if (first.every(Boolean)) {
    const fix = await agent(fixPrompt(pre, units, first.filter(v => !accepted(v)), movesHead, branchFiles()), { label: 'review:fix', phase: 'Review', schema: COMMITTED })
    if (fix && fix.ok) {
      commits.push(...fix.commits)
      // Every lens reads the fix again: the rules lens and the name check must see its text and message too.
      const again = await lensRun(':2')
      reviewOk = again.every(accepted)
      reviewOpen = again.filter(v => !accepted(v)).flatMap(v => v ? v.blocking : [{ problem: 'a reviewer failed to report' }])
    } else reviewOpen = first.filter(v => !accepted(v)).flatMap(v => v.blocking)
  } else reviewOpen = [{ problem: `${first.filter(v => !v).length} review lenses failed to report` }]
}

phase('Merge')
// The next run picks up what this one could not finish: files of units that were reverted, failed or lost,
// busy files that changed, files outside args.paths, files of areas without guards, and files the check restored.
const committedFiles = new Set(commits.flatMap(c => (c.files || []).map(rel)))
const carry = uniq([
  ...uniq([
    ...done.filter(r => r.state === 'reverted' || r.state === 'failed' || (!checksOk && kept.includes(r)))
      .flatMap(r => r.unit.paths.filter(p => pre.changed_files.includes(p) || findings.some(f => f.path === p))),
    ...lost.flatMap(u => u.paths),
    ...pre.changed_files.filter(p => pre.busy_files.includes(p)),
    ...pre.changed_files.filter(p => !inPaths(p)),
    ...units.filter(guardless).flatMap(u => u.paths.filter(p => pre.changed_files.includes(p))),
    ...(checked ? checked.reverted.map(x => rel(x.path)) : []),
    ...followUpsLeft.map(f => f.path),
  ]).filter(p => !committedFiles.has(p)),
  // A failed sweep looked at nothing: every changed file waits for the next run, committed or not.
  ...(sweepFailed.length ? pre.changed_files : []),
]).filter(p => !never(p))
const doMerge = MERGE && checksOk && reviewOk && commits.length > 0
const record = !commits.length ? 'none' : doMerge ? 'state' : 'pending'
const stateObj = { base: pre.head, polished: '<the run\'s commits>', carry, stamp: pre.stamp, standards_stamp: std ? pre.stamp : '<the value state.json holds, if any>' }
const summary = {
  stamp: pre.stamp, scope: pre.scope, base: pre.base, head: pre.head,
  gates: { merge_requested: MERGE, checks_ok: checksOk, review_ok: reviewOk, commits: commits.length },
  holders, stale_holders: pre.holders.filter(h => h.stale), leftovers: pre.leftovers, excluded: [...pre.excluded, ...excludedHere],
  failing_before: pre.failing_before,
  moves: moveLog,
  units: unitSummary,
  checks: [...(checked ? checked.checks : []), ...(committed ? committed.checks : [])],
  check_notes: [checked && checked.notes, committed && committed.notes].filter(Boolean),
  reverted: checked ? checked.reverted : [],
  commits,
  review_open: reviewOpen,
  reevaluate: findings.filter(f => f.kind === 'reevaluate'),
  proposals, unowned_findings: findings.filter(f => !unitOf(f.path)),
  guarded_findings: findings.filter(f => wholeGuard(f.path)),
  follow_ups_left: followUpsLeft,
  carry,
  guidance_deltas: std ? std.deltas : [], guidance_unreachable: std ? std.unreachable : [], guidance_reread: !!std,
}
const merged = await agent(mergePrompt(pre, summary, doMerge, record, stateObj), { label: 'merge', phase: 'Merge', schema: MERGED })
return {
  ok: commits.length ? checksOk && reviewOk : checksOk,
  merged: merged ? merged.merged : false,
  main_commit: merged ? merged.main_commit : '',
  waits_because: merged ? merged.waits_because : 'the merge agent failed',
  report: merged ? merged.report : `${pre.report_dir}/report.md`,
  gates: summary.gates,
  commits: commits.length,
  units: unitSummary.map(u => `${u.id}: ${u.state}`),
  proposals: proposals.length,
  carry: carry.length,
  busy_files: pre.busy_files.length,
}

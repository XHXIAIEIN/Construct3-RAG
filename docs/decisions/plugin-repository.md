# The Plugin Has Its Own Repository

Date: 2026-10-15

## Problem

`plugin/` is built from this repository and committed in it
(`plugin-folder.md`). Claude's directory and the marketplace route read it
from here. So a person who looks the plugin up lands in the repository of
the data pipeline, the lookup service, the tests and the decision records.
The plugin needs a page, an issue tracker and a clone of its own.

## Evidence

- The directory's settings page names the submission's repository and
  plugin path, and says that only a new submission can change either. The
  listing's identity fields, the keywords among them, are read once, when
  the submission is created. A repository of its own therefore means a
  submission of its own.
- The directory scans the plugin folder only, and holds it to the limits
  of `plugin-folder.md`. The first submission had this layout until
  2026-10-05: the root held `.claude-plugin/plugin.json` and a
  `marketplace.json` whose plugin source was `./`, and the directory
  published it.
- `plugin/` changes with every commit that touches the skill, the data or
  the prompts. A copy that a person pushes falls behind main, as the
  directory's copy does.

## Options

- `plugin/` committed here and mirrored to the plugin repository by a
  workflow after each push to main. One source, one build and one test
  suite; the copy is minutes behind main.
- `plugin/` built in CI and pushed to the plugin repository, not committed
  here. No copy in this repository, but the version logic of
  `plugin-tracks-commits.md` and the tests that compare `plugin/` with a
  fresh build must read the plugin repository, and a release can be
  checked only after the push.
- `git subtree push` of `plugin/` by hand. No workflow and no key, but a
  release depends on a person running it.

## Decision

The first option. `XHXIAIEIN/Construct3-Agent-Skills` is the plugin's
repository. Its `plugin/` is `plugin/` as committed here, and its
`.claude-plugin/marketplace.json` names that folder as its single plugin,
with the source `./plugin`. So `claude plugin marketplace add
XHXIAIEIN/Construct3-Agent-Skills` and `claude plugin install
construct3@construct3-agent-skills` install it. The files beside
`plugin/` there, the READMEs, `AGENTS.md`, `CLAUDE.md` and `.claude/`,
are that repository's own, and a folder beside `plugin/` is where content
of its own goes.

- `scripts/publish_plugin.py --clone <folder>` makes the `plugin/` of a
  clone of the plugin repository equal to `plugin/` here and writes the
  marketplace manifest. It removes what that `plugin/` holds and this one
  does not, leaves the clone's other files alone, commits with the commit
  of this repository the build came from, and pushes. It refuses when
  `plugin/` differs from a fresh build, so what it publishes is what the
  tests checked.
- `.github/workflows/publish-plugin.yml` runs the script after each push
  to main that changes `plugin/`, the script or the workflow. It pushes
  with a deploy key of the plugin repository, held as the secret
  `PLUGIN_DEPLOY_KEY`. To rotate the key, make a new ed25519 pair, add
  the public half as a deploy key with write access on the plugin
  repository, set the secret, and delete the old key there.
- The directory submission from Construct3-Agent-Skills has the plugin
  path `plugin`. The submission from this repository stays
  until that one is live, because a delisted plugin stops updating for
  the people who installed it.
- This repository's `.claude-plugin/marketplace.json`, the
  `construct3-rag` marketplace, stays while that submission does.

## Trade-offs

- The plugin repository's history is a sequence of builds, each named
  after a commit here. Its diffs show the built files, not the sources.
- A push to main runs the checks and the publish in parallel. A build that
  fails its checks on main is published all the same, because the
  `construct3-rag` marketplace serves main without waiting for the checks
  too.
- `plugin/` stays committed here, so the duplication that
  `plugin-folder.md` accepts stays. The schema files are large, so each
  change adds a large blob to both repositories.

## Re-evaluate when

- The Construct3-Agent-Skills submission is live. Then delist this
  repository's submission, remove its `marketplace.json` and the
  `construct3-rag` route from the README, and update
  `tests/test_plugin_folder.py` with them.
- The duplication costs more than the single build and test suite save.
  Then move to the second option, with the version read from the plugin
  repository.
- The plugin's name should match its repository. `name` in
  `scripts/plugin/plugin.json` is the prefix of the skill id
  `construct3:construct3-agent-plugin`, which the skill's text, the
  install script and the docs name (`skill-and-plugin-names.md`).

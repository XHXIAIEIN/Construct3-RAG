# The Plugin's Version and Why a Project Needs No Copy

Date: 2026-10-05

## Problem

A game project held its own copy of the skill, made by `install.py`. The
copy fell behind the clone between refreshes: on 2026-10-02 one game's copy
lacked five files the clone had changed, and the sessions working in it read
the old `SKILL.md` until the checker's drift line was acted on.

The plugin route has the same problem in another place. Claude Code
computes a plugin's version from `version` in `plugin.json` before anything
else, and `claude plugin update` keeps the cached copy while that string is
unchanged (Claude Code docs, "Plugin loading reference", "Versions and
updates"). A version that nobody raises leaves every marketplace install on
its first copy, however many commits follow. A plugin linked under
`~/.claude/skills/` loads in place and ignores the version, so a linked
clone does not show the problem.

## Evidence

Claude's directory asks a plugin whose `plugin.json` sets `version` to
raise it with every release, and warns about a plugin without one
(`https://claude.com/docs/plugins/submit`, "Update a published plugin";
`directory-listing.md`). A marketplace install updates from main, and the
directory receives each push to main through a webhook. So each push that
changes `plugin/` is a release for the marketplace, and a version that a
reviewer can publish for the directory.

## Options

- No `version`: Claude Code versions a GitHub install by commit, but the
  directory warns.
- A `version` raised by hand: each push that changes `plugin/` needs a
  person to remember it, and a forgotten raise keeps installs where they
  are.
- A `version` that the build sets by comparing the built plugin with the
  published one.

## Decision

The build sets the version. `scripts/build_plugin.py` writes it into
`plugin/.claude-plugin/plugin.json` (`plugin-folder.md`):

- The published plugin is the one at the commit that HEAD shares with
  `origin/main`, from `git merge-base`. Without that ref or a merge base,
  as in a shallow CI checkout, it is the one at HEAD. During a merge, it is
  the one at the commit that the merge commit will share with `origin/main`.
  Its version is the one in `plugin/.claude-plugin/plugin.json` there, or in
  the root's `.claude-plugin/plugin.json`, the manifest's place in commits
  that predate `plugin/`.
- If the built files other than `plugin.json` have the Git blob ids of the
  published files, the build keeps the published version. Otherwise it
  writes the published version with its patch raised by one.
- `version` in `scripts/plugin/plugin.json` is the floor: the build never
  writes a lower version. A minor or a major release raises the floor by
  hand. Versions compare as numbers.
- The build reads Git locally and never fetches. The merge base, and not
  `origin/main` itself, keeps a `git fetch` without a merge from failing the
  check of a clean checkout.

Every build on one branch writes the same version. Two branches that both
change the plugin write the same next version, so their `plugin.json`
changes merge without a conflict. If one branch is pushed first, the other
fails `build_plugin.py --check` once it merges main. Its next build writes
the version after the pushed one. So for changes merged in a clone, two
different sets of files never carry one version. If a merge conflicts in
`plugin/`, resolve the sources, then run the build before committing the
merge. The data-update workflow runs the build through `init.py` in a
checkout where `origin/main` is HEAD, so a data refresh raises the version
too.

On a machine with the clone, the clone's plugin folder, `<clone>/plugin`,
is linked as `~/.claude/skills/construct3` (a junction on Windows). Claude
Code loads a plugin directory under `~/.claude/skills/` in place as
`construct3@skills-dir`, so a `git pull` reaches the next session and there
is no copy to fall behind. The docs say a local-directory marketplace loads
in place too, but Claude Code 2.1.287 copied the whole clone, 3.0 GB with
the ignored `.cache/` and `.local/`, into `~/.claude/plugins/cache/` when
the clone was added as a marketplace whose plugin source was the repository
root.

A project used with the plugin holds no copy of the skill; its `AGENTS.md`
names the scripts under the plugin's `skills/construct3-agent-plugin/`.
`SKILL.md` and `AGENTS.md` section 4 tell an agent that sees the skill as
`construct3:construct3-agent-plugin` not to install one.

## Trade-offs

- A marketplace install reaches each pushed change to `plugin/` at its next
  `claude plugin update`, or by itself with auto-update on. The linked clone
  follows every `git pull`.
- A patch release names a change of files, not its size: a data refresh and
  a new script both raise the patch.
- The comparison leaves out `plugin.json`, so a change to its description
  or keywords alone keeps the version.
- The version is checked in a clone, where the build runs. A pull request
  merged on GitHub keeps the version it was built with. If another change
  to `plugin/` reached main after that build, the two changes carry one
  version. Before merging such a pull request, merge main into its branch
  and run the build. The data-update pull request that merges by itself is
  not rebuilt, so it can carry the same version as another change that
  reached main before it.
- `install.py` and the copy serve other agents and Claude Code without the
  plugin.
- Plugin loading costs no network at session start: the plugin is read from
  the cache or, through the link, from the clone. `claude plugin details
  construct3@skills-dir` lists one skill and about 240 always-on tokens.

## Re-evaluate when

- Claude Code or the directory takes a plugin's version from something
  other than `version` in `plugin.json`.
- Changes to `plugin/` reach main mostly through pull requests merged on
  GitHub; the version then needs a check in CI against the main they merge
  into.

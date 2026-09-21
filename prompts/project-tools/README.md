# Project tools

The generator, the checker, the sheet printer and the ACE lookup are the
`construct3-project` skill: [`skills/construct3-project/SKILL.md`](../../skills/construct3-project/SKILL.md).

A game project whose `AGENTS.md` or `CLAUDE.md` sends you to this file has
the block from before the skill. Install the skill in that project, from its
folder:

```bash
python <Construct3-RAG>/skills/construct3-project/scripts/install.py
```

Then read `.agents/skills/construct3-project/SKILL.md` there. The command
prints the row to put in the block's table in place of the one that names
this file; `tools/build-project.py` and `tools/check-project.py` in the
project are the earlier copies of what the skill now holds.

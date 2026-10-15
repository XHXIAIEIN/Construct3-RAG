#!/usr/bin/env python3
"""Run a script of the construct3-agent-plugin skill for a skill of the plugin's / menu.

    python run.py SCRIPT [ARG ...]      skills/construct3-agent-plugin/scripts/SCRIPT.py ARG ..., then "exit code N"

The menu skills run their script through this file inside a !`...` line of SKILL.md. Claude Code aborts the
skill when such a command exits non-zero, and refuses a chain (`|| true`) or an expansion (`$?`) that would
hide the exit code; the scripts exit non-zero on a finding, a miss or a refusal, which is what the user wants
to read. So this file passes the script's output through, prints the exit code as its last line, and exits 0.
Why: docs/decisions/plugin-script-menu.md.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The skill is beside this file in the plugin (plugin/skills/run.py) and one folder up in the sources (skills/menu/run.py)
SCRIPTS = next((folder / "construct3-agent-plugin" / "scripts" for folder in (HERE, HERE.parent)
                if (folder / "construct3-agent-plugin" / "scripts").is_dir()), HERE / "construct3-agent-plugin" / "scripts")


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: run.py SCRIPT [ARG ...]", file=sys.stderr)
        return 0
    script = SCRIPTS / f"{argv[0]}.py"
    if not script.is_file():
        print(f"no script {script}", file=sys.stderr)
        return 0
    # The script's stdout and stderr go straight through; Claude Code merges them into the skill's text
    code = subprocess.run([sys.executable, str(script), *argv[1:]]).returncode
    sys.stdout.flush()
    print(f"exit code {code}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

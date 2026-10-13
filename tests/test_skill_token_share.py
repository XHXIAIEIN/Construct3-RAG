"""evals/token_share.py: a transcript's cost shared out among what filled its context, at Opus price ratios."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.skill_helpers import SKILL

sys.path.insert(0, str(SKILL / "evals"))
import token_share  # noqa: E402

PRINT = {"command": "python scripts/print_sheet.py --outline"}
READ_SKILL = {"file_path": "/game/.agents/skills/construct3-agent-plugin/SKILL.md"}


def assistant(mid: str, usage: dict, *content: dict) -> dict:
    return {"type": "assistant", "message": {"id": mid, "model": "m", "usage": usage, "content": list(content)}}


def result(tid: str, text: str) -> dict:
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": text}]}}


def usage(uncached: int, read: int, out: int, five: int = 0, hour: int = 0, thinking: int = 0) -> dict:
    return {"input_tokens": uncached, "cache_creation_input_tokens": five + hour, "cache_read_input_tokens": read,
            "output_tokens": out, "output_tokens_details": {"thinking_tokens": thinking},
            "cache_creation": {"ephemeral_5m_input_tokens": five, "ephemeral_1h_input_tokens": hour}}


# Four responses: a first context of 10,003 tokens, a print_sheet call whose result grows it by 402, a SKILL.md read
# that arrives with the cache expired (the whole context written again), then a compaction to 5,000.
FIRST = usage(3, 9000, 50, hour=1000, thinking=10)
TRANSCRIPT = [
    {"type": "user", "message": {"content": "change the sheet"}},
    assistant("m1", FIRST, {"type": "tool_use", "id": "t1", "name": "Bash", "input": PRINT}),
    assistant("m1", FIRST, {"type": "text", "text": "Reading the sheet."}),       # the same response, a second block
    result("t1", "a" * 720),
    assistant("m2", usage(2, 10003, 20, five=400), {"type": "tool_use", "id": "t2", "name": "Read", "input": READ_SKILL}),
    result("t2", "b" * 3600),
    {"type": "attachment", "attachment": {"type": "model", "model": "m"}},           # kept by the client, never sent
    assistant("m3", usage(5, 0, 10, five=11500)),
    assistant("m4", usage(0, 2000, 30, five=3000)),
]
EXACT = (3 + 1000 * 2 + 9000 * 0.1 + 50 * 5) + (2 + 400 * 1.25 + 10003 * 0.1 + 20 * 5) \
    + (5 + 11500 * 1.25 + 10 * 5) + (3000 * 1.25 + 2000 * 0.1 + 30 * 5)
REWRITE_PRICE = (5 + 11500 * 1.25) / 11505


@pytest.fixture
def transcript(tmp_path: Path) -> Path:
    path = tmp_path / "agent-1.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in TRANSCRIPT) + "\n", encoding="utf-8")
    return path


def test_the_shares_add_up_to_the_cost_from_usage(transcript: Path) -> None:
    """Each response counts once although the transcript writes a line per content block; the shares sum to the
    exact cost, uncached input at 1, a 1-hour write at 2, a 5-minute write at 1.25, a read at 0.1, output at 5."""
    share = token_share.share_of(transcript)
    assert share.responses == 4
    assert share.exact == pytest.approx(EXACT)
    assert share.attributed == pytest.approx(EXACT)


def test_each_item_pays_its_write_and_a_read_per_later_response(transcript: Path) -> None:
    share = token_share.share_of(transcript)
    cost, tokens = share.cost, share.tokens
    # The first context: written once (2,003) and read from the cache (900), then read by the next two responses.
    assert cost["baseline"] == pytest.approx(2003 + 900 + 10003 * 0.1 * 2)
    # What arrived before m2, the call m1 wrote, its text and the script's output: 402 tokens written for 502,
    # then read once by m3.
    arrived = ("model-call:script:print_sheet", "model-text", "script:print_sheet")
    assert sum(tokens[c] for c in arrived) == pytest.approx(402)
    assert sum(cost[c] for c in arrived) == pytest.approx(502 + 402 * 0.1)
    # The Read and its result arrive with the expired cache: 1,100 new tokens at m3's write price, never read again.
    assert tokens["model-call:Read"] + tokens["read:SKILL.md"] == pytest.approx(1100)
    assert cost["model-call:Read"] + cost["read:SKILL.md"] == pytest.approx(1100 * REWRITE_PRICE)
    # The rest of m3's write is old context written again: its items pay the read, the premium is the rewrite's.
    assert cost["cache-rewrite"] == pytest.approx(10405 * (REWRITE_PRICE - 0.1))
    assert cost["compaction-summary"] == pytest.approx(3000 * 1.25 + 2000 * 0.1)
    assert cost["output:thinking"] == 10 * 5
    assert cost["output:visible"] == (40 + 20 + 10 + 30) * 5
    assert not any(c.startswith("attachment:") for c in cost)
    assert share.per_file[0]["first_context"] == 10003 and share.per_file[0]["largest_context"] == 11505


def test_the_estimate_splits_a_growth_but_never_changes_it() -> None:
    """Chinese text counts a token a character, other text 3.6 characters a token."""
    assert token_share.text_tokens("事件表") == 3
    assert token_share.text_tokens("a" * 36) == pytest.approx(10)


@pytest.mark.parametrize("command, source", [
    ("python scripts/print_sheet.py --limit 0", "script:print_sheet"),
    ("python .agents/skills/construct3-agent-plugin/scripts/preview_project.py --help", "script:preview_project --help"),
    ("Get-Content docs/02-design/sound.md", "bash:read-file"),
    ("git log --oneline", "bash:git"),
])
def test_a_shell_result_is_known_by_its_command(command: str, source: str) -> None:
    assert token_share.tool_category("PowerShell", {"command": command}) == source


@pytest.mark.parametrize("path, source", [
    ("C:\\game\\eventSheets\\Game.json", "read:project-json"),
    ("/game/.agents/skills/construct3-agent-plugin/references/editor-and-preview.md", "read:skill-reference"),
    ("/home/u/.claude/projects/p/s/tool-results/b1.txt", "read:persisted-output"),
    ("/game/tools/build_project.py", "read:py"),
])
def test_a_read_is_known_by_its_file_kind(path: str, source: str) -> None:
    assert token_share.classify_read(path) == source


def test_the_sources_view_names_this_skills_scripts() -> None:
    assert token_share.source_group("script:print_sheet --help") == "skill script output"
    assert token_share.source_group("script:build_project") == "other script output"
    assert token_share.source_group("read:SKILL.md") == "skill text and references"
    assert token_share.source_group("skill:construct3:construct3-agent-plugin") == "skill text and references"
    assert token_share.source_group("compaction-summary") == "compaction summaries"
    assert token_share.target_of("Get-Content docs/02-design/05-sound.md") == "game docs: design"
    assert token_share.is_read("bash:read-file") and not token_share.is_read("model-call:Write")


def test_the_command_prints_both_totals_and_writes_json(transcript: Path, tmp_path: Path) -> None:
    """A list file names the transcripts; the first line prints the shares' sum beside the exact cost."""
    listed, out = tmp_path / "list.txt", tmp_path / "share.json"
    listed.write_text(f"{transcript}\n", encoding="utf-8")
    done = subprocess.run([sys.executable, str(SKILL / "evals" / "token_share.py"), f"@{listed}",
                           "--out", str(out), "--files", "--targets", "--items", "0"],
                          capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert done.returncode == 0, done.stderr
    first = done.stdout.splitlines()[0]
    assert first.startswith("1 transcripts, 4 responses") and "(+0.000%)" in first, first
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["exact"] == pytest.approx(EXACT) and saved["attributed"] == pytest.approx(EXACT)
    assert saved["groups"]["skill script output"] > 0
    assert {i[2] for i in saved["items"]} >= {"script:print_sheet", "read:SKILL.md"}


def test_a_transcript_without_a_response_is_exit_1(tmp_path: Path) -> None:
    empty = tmp_path / "empty.jsonl"
    empty.write_text(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n", encoding="utf-8")
    done = subprocess.run([sys.executable, str(SKILL / "evals" / "token_share.py"), str(empty)],
                          capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert done.returncode == 1 and "no transcript held a model response" in done.stderr

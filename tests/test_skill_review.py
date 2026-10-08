"""--review of print_sheet.py and check_project.py: a project someone asked about ends with what a review reports."""
from tests.skill_helpers import check, tool


def test_check_project_says_what_a_review_reports_above_its_last_line(built):
    code, out = check(built, "--review")
    lines = out.splitlines()
    assert code == 0 and lines[-2].startswith("review: say first what the project does.")
    assert lines[-1].startswith("ok: ") and "next, review the design" not in lines[-1]
    assert "is omitted; the editor fills its default" not in out


def test_print_sheet_ends_with_it_and_a_cut_print_still_names_the_rest(built):
    code, out = tool(built, "print_sheet", "--review")
    assert code == 0 and out.splitlines()[-1].startswith("review: say first what the project does.")
    code, out = tool(built, "print_sheet", "--review", "--limit", "1200")
    lines = out.splitlines()
    assert code == 0 and lines[-2].startswith("review: ") and lines[-1].startswith("-- stopped at the limit")

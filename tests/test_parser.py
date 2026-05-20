import sys
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.bench.parser import (
    MAX_PLAUSIBLE_ORDER,
    ParseResult,
    STRATEGIES,
    max_plausible_order_from_env,
    parse_decision,
)


def test_strategies_are_public_and_ordered():
    assert [name for name, _ in STRATEGIES] == [
        "strict_int",
        "json_field",
        "boxed",
        "solution_tag",
        "answer_tag",
        "last_line_int",
        "first_int_anywhere",
    ]
    assert isinstance(STRATEGIES, tuple)


def test_strict_int_examples():
    assert parse_decision("5") == ParseResult(5, "strict_int", True)
    assert parse_decision("  42\n") == ParseResult(42, "strict_int", True)


def test_json_field_examples():
    assert parse_decision('{"order": 5}') == ParseResult(5, "json_field", True)
    assert parse_decision('{"order": "8"}') == ParseResult(8, "json_field", True)


def test_boxed_examples():
    assert parse_decision(r"I choose \boxed{5}") == ParseResult(5, "boxed", True)
    assert parse_decision(r"Final: \boxed{ 8 }") == ParseResult(8, "boxed", True)


def test_solution_tag_examples():
    assert parse_decision("maybe 9 <solution>4</solution>") == ParseResult(
        4, "solution_tag", True
    )
    assert parse_decision("<SOLUTION>\n8\n</SOLUTION>") == ParseResult(
        8, "solution_tag", True
    )


def test_answer_tag_examples():
    assert parse_decision("maybe 9 <answer>4</answer>") == ParseResult(
        4, "answer_tag", True
    )
    assert parse_decision("<ANSWER>\n8\n</ANSWER>") == ParseResult(
        8, "answer_tag", True
    )


def test_last_line_int_examples_and_edge_cases():
    assert parse_decision(
        "I considered 42\nbut actually I'll go with 8"
    ) == ParseResult(8, "last_line_int", True)
    assert parse_decision(
        "42 cases sounds right\nbut actually I'll go with 8"
    ) == ParseResult(8, "last_line_int", True)
    assert parse_decision(
        "42 cases sounds right but actually I'll go with 8"
    ) == ParseResult(42, "last_line_int", True)


def test_first_int_anywhere_examples():
    assert parse_decision("Order 6\nno digits on final line") == ParseResult(
        6, "first_int_anywhere", True
    )
    assert parse_decision("Maybe 11?\nfinal answer withheld") == ParseResult(
        11, "first_int_anywhere", True
    )


def test_failure_examples():
    assert parse_decision("") == ParseResult(None, "failed", False)
    assert parse_decision("no number here") == ParseResult(None, "failed", False)


def test_negative_and_too_large_values_are_not_parse_ok():
    assert parse_decision("-1") == ParseResult(-1, "strict_int", False)
    assert parse_decision(str(MAX_PLAUSIBLE_ORDER + 1)) == ParseResult(
        MAX_PLAUSIBLE_ORDER + 1, "strict_int", False
    )
    assert parse_decision(str(MAX_PLAUSIBLE_ORDER)) == ParseResult(
        MAX_PLAUSIBLE_ORDER, "strict_int", True
    )


def test_parse_decision_accepts_explicit_plausible_order_bound():
    assert parse_decision("9", max_plausible_order=8) == ParseResult(
        9, "strict_int", False
    )
    assert parse_decision("9", max_plausible_order=9) == ParseResult(
        9, "strict_int", True
    )


def test_max_plausible_order_from_env():
    assert max_plausible_order_from_env({}) == MAX_PLAUSIBLE_ORDER
    assert max_plausible_order_from_env({"BEERGAME_MAX_PLAUSIBLE_ORDER": "12"}) == 12


def test_max_plausible_order_from_env_rejects_invalid_values():
    for value in ("many", "-1"):
        try:
            max_plausible_order_from_env({"BEERGAME_MAX_PLAUSIBLE_ORDER": value})
        except ValueError as exc:
            assert "BEERGAME_MAX_PLAUSIBLE_ORDER" in str(exc)
        else:
            raise AssertionError("expected ValueError")


@given(st.integers(min_value=0, max_value=MAX_PLAUSIBLE_ORDER))
def test_small_ints_parse_as_strict_int(value):
    assert parse_decision(str(value)) == ParseResult(value, "strict_int", True)

"""Tests for apply_rulesets.py's drift comparison."""

from apply_rulesets import differences


def test_subset_compare_ignores_extra_keys() -> None:
    want = {"name": "x", "rules": [{"type": "merge_queue", "parameters": {"merge_method": "SQUASH"}}]}
    have = {"name": "x", "id": 1, "rules": [{"type": "merge_queue", "parameters": {"merge_method": "SQUASH", "extra": 1}}]}
    assert differences(want, have) == []


def test_rules_compare_by_type_and_report_changes() -> None:
    want = {"rules": [{"type": "a", "parameters": {"n": 1}}, {"type": "b"}]}
    have = {"rules": [{"type": "b"}, {"type": "a", "parameters": {"n": 2}}]}
    assert differences(want, have) == [".rules[a].parameters.n: expected 1, found 2"]


def test_missing_rule() -> None:
    assert differences({"rules": [{"type": "a"}]}, {"rules": [{"type": "b"}]})

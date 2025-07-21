"""RichTextPredicate: numeric branches & _not_empty validator."""

from __future__ import annotations

import pytest

from scribe.models.templates import RichTextPredicate


def test_not_empty_validator() -> None:
    """Instantiating without any operator raises ValueError (validator)."""
    with pytest.raises(ValueError):
        RichTextPredicate()  # hits _not_empty → ValueError


@pytest.mark.parametrize(
    "pred,value,expect",
    [
        # ----- numeric comparisons (lines 141-161) -----------------
        (RichTextPredicate(gt=10), 20, True),
        (RichTextPredicate(gt=10), 5, False),
        (RichTextPredicate(gte=5), 5, True),
        (RichTextPredicate(lt=3), 2.5, True),
        (RichTextPredicate(lte=1), 2, False),
        (RichTextPredicate(lte=1), 1, True),
        # ----- fall-through when float() fails ---------------------
        (RichTextPredicate(gt=0), "not-a-number", False),
    ],
    ids=[
        "gt_true",
        "gt_false",
        "gte_true",
        "lt_true",
        "lte_false",
        "lte_true",
        "float_error",
    ],
)
def test_numeric_branches(
    pred: RichTextPredicate, value, expect: bool
) -> None:  # noqa: ANN001
    """Every numeric operator path returns the proper boolean."""
    assert pred.matches(value) is expect


@pytest.mark.parametrize(
    "pred,value,expect",
    [
        (RichTextPredicate(equals="ok"), "OK", True),
        (RichTextPredicate(contains="ok"), "THAT'S OK", True),
        (RichTextPredicate(regex="OK$"), "THAT'S OK", True),
    ],
    ids=["text_lower_true", "text_contains_true", "regex_true"],
)
def test_string_comparisons(
    pred: RichTextPredicate, value, expect: bool
) -> None:
    """String comparison is case-insensitive (earlier branch)."""
    assert pred.matches(value) is expect

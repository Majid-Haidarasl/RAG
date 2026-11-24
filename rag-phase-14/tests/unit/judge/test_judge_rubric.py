"""Phase 10 rubric: five criteria, 20 points, acceptance bar 18, aliases and guidance."""

import pytest

from rag_core.judging.domain.model import JudgeThreshold
from rag_core.judging.domain.rubric import (
    Criterion,
    OutputKind,
    Rubric,
    canonical_name,
    default_rubric,
)
from rag_core.shared_kernel.errors import InvariantError

pytestmark = [pytest.mark.judging, pytest.mark.judge]


def test_default_rubric_points_add_up_to_twenty() -> None:
    r = default_rubric()
    assert r.label == "judge.rubric@1.0.0"
    assert r.keys == ("grounding", "correctness", "citation", "completeness", "clarity")
    assert r.maximums == {
        "grounding": 5,
        "correctness": 5,
        "citation": 4,
        "completeness": 3,
        "clarity": 3,
    }
    assert r.minimums == {
        "grounding": 4,
        "correctness": 4,
        "citation": 3,
        "completeness": 2,
        "clarity": 2,
    }
    assert sum(r.maximums.values()) == r.out_of == 20
    assert r.accept_total == 18
    assert r.threshold == JudgeThreshold(18, 20)


def test_minimums_alone_do_not_reach_the_bar() -> None:
    # 4+4+3+2+2 = 15 < 18: passing every minimum is not enough on its own.
    assert sum(default_rubric().minimums.values()) == 15


@pytest.mark.parametrize(
    ("written", "key"),
    [
        ("grounding", "grounding"),
        ("Groundedness", "grounding"),
        ("faithfulness", "grounding"),
        ("Factual Accuracy", "correctness"),
        ("accuracy", "correctness"),
        ("citations", "citation"),
        ("Traceability", "citation"),
        ("coverage", "completeness"),
        ("language-clarity", "clarity"),
        ("fluency", "clarity"),
    ],
)
def test_aliases_resolve(written: str, key: str) -> None:
    assert default_rubric().resolve(written) == key


def test_unknown_names_do_not_resolve() -> None:
    r = default_rubric()
    assert (
        r.resolve("total") is None
        and r.resolve("overall") is None
        and r.resolve("") is None
    )


def test_canonical_name() -> None:
    assert canonical_name("  Citation Quality ") == "citation_quality"
    assert canonical_name("language-clarity") == "language_clarity"


def test_rubric_rejects_points_that_do_not_add_up() -> None:
    with pytest.raises(InvariantError, match="add up"):
        Rubric("r", "1", (Criterion("aa", 5, 4), Criterion("bb", 5, 4)), out_of=20)


def test_rubric_rejects_duplicate_keys_and_clashing_aliases() -> None:
    with pytest.raises(InvariantError, match="duplicate"):
        Rubric("r", "1", (Criterion("aa", 10, 1), Criterion("aa", 10, 1)))
    with pytest.raises(InvariantError, match="used by"):
        Rubric(
            "r",
            "1",
            (
                Criterion("aa", 10, 1, aliases=("x",)),
                Criterion("bb", 10, 1, aliases=("x",)),
            ),
        )


def test_rubric_rejects_bad_accept_total() -> None:
    with pytest.raises(InvariantError):
        Rubric("r", "1", (Criterion("aa", 20, 1),), accept_total=21)
    with pytest.raises(InvariantError):
        Rubric("r", "1", (Criterion("aa", 20, 1),), accept_total=0)


@pytest.mark.parametrize(
    ("key", "mx", "mn"), [("Bad Key", 5, 1), ("ok", 0, 0), ("ok", 3, 4), ("ok", 3, -1)]
)
def test_criterion_validation(key: str, mx: int, mn: int) -> None:
    with pytest.raises(InvariantError):
        Criterion(key, mx, mn)


def test_guidance_lines_and_reply_skeleton() -> None:
    r = Rubric(
        "r",
        "1",
        (
            Criterion(
                "grounding",
                12,
                8,
                "Grounding",
                guidance=(("qa_answer", "only the sources"),),
            ),
            Criterion("clarity", 8, 4, "Clarity"),
        ),
    )
    lines = r.guidance_lines(OutputKind.QA_ANSWER.value)
    assert lines == ["- grounding (0-12): only the sources", "- clarity (0-8): Clarity"]
    assert r.guidance_lines("ike_summary")[0] == "- grounding (0-12): Grounding"
    assert (
        r.reply_skeleton()
        == '{"scores": {"grounding": <0-12>, "clarity": <0-8>}, "issues": ["<short problem>", "..."]}'
    )


def test_to_dict_and_unknown_criterion() -> None:
    r = default_rubric()
    data = r.to_dict()
    assert data["out_of"] == 20 and data["accept_total"] == 18
    assert [c["key"] for c in data["criteria"]] == list(r.keys)  # type: ignore[index, union-attr]
    with pytest.raises(InvariantError):
        r.criterion("style_points")

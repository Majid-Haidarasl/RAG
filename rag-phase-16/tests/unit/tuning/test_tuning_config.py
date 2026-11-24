"""Phase 14 config/eval.yaml (1.0.0 defaults): shipped values, defaults and rejected keys."""

import pytest

from rag_core.shared_kernel.errors import InvariantError
from rag_core.tuning.domain.variants import KINDS, selection_problems
from rag_core.tuning.infrastructure.config import (
    RetrievalVariant,
    eval_settings_from_dict,
    load_eval_settings,
)
from tests.fixtures.tuning.samples import CONFIG, REPO

pytestmark = [pytest.mark.tuning]


def test_shipped_config() -> None:
    s = load_eval_settings(CONFIG)
    assert s.config_version == "1.0.0"
    assert [v.id for v in s.retrieval_variants] == [
        "baseline",
        "wide",
        "lexical_boost",
        "wide_lexical",
    ]
    base, wide = s.variant("baseline"), s.variant("wide")
    assert (base.top_k, base.candidate_k, base.budget_tokens) == (5, 30, 3500)
    assert (wide.top_k, wide.candidate_k, wide.budget_tokens) == (8, 40, 5000)
    assert s.variant("lexical_boost").lexical_weight == 1.5
    assert s.qa_prompts == ("qa.answer", "qa.answer_complete") and s.judge_prompts == (
        "baseline",
        "strict",
        "strict_precheck",
    )
    assert s.id_variants == ("baseline", "listed", "listed_retry", "listed_guarded")
    assert s.live.generation_models == ("qwen3:8b",) and s.live.enabled


def test_shipped_files_exist() -> None:
    f = load_eval_settings(CONFIG).files
    for rel in (
        f.dataset,
        f.calibration,
        f.qa_prompt_dir,
        f.strict_judge_dir,
        f.ids_prompt_dir,
    ):
        assert (REPO / rel).exists(), rel
    assert (REPO / f.results_dir / "README.md").is_file()


def test_shipped_selection_is_documented() -> None:
    s = load_eval_settings(CONFIG)
    assert set(s.selection) == set(KINDS)
    assert selection_problems(s.selection, s.known_variants()) == []
    assert (
        s.chosen("retrieval") == "baseline"
        and s.chosen("judge_prompt") == "strict_precheck"
    )
    assert s.chosen("qa_prompt") == "qa.answer" and s.chosen("ai_ids") == "baseline"


def test_shipped_rules() -> None:
    rules = load_eval_settings(CONFIG).selection_rules
    assert rules["retrieval"].primary == "context_facts" and rules[
        "retrieval"
    ].tie_breakers[0] == ("hit_at_5", True)
    assert rules["judge_prompt"].primary == "accuracy" and rules[
        "judge_prompt"
    ].tie_breakers[0] == ("leniency", False)


def test_live_caps_cover_the_planned_run() -> None:
    s = load_eval_settings(CONFIG)
    assert s.live.max_generations >= 32 * len(s.qa_prompts) + 16
    assert s.live.max_judge_calls >= 42 * len(s.judge_prompts)


def test_minimal_dict() -> None:
    s = eval_settings_from_dict({"retrieval_variants": [{"id": "baseline"}]})
    assert (
        s.variant("baseline").top_k == 5
        and s.selection == {}
        and s.qa_prompts == ("qa.answer",)
    )


def test_unknown_variant_and_missing_choice() -> None:
    s = eval_settings_from_dict({"retrieval_variants": [{"id": "baseline"}]})
    with pytest.raises(InvariantError, match="unknown retrieval variant"):
        s.variant("wide")
    with pytest.raises(InvariantError, match="no selection"):
        s.chosen("retrieval")


def test_retrieval_variant_invariants() -> None:
    with pytest.raises(InvariantError, match="top_k"):
        RetrievalVariant("x", top_k=10, candidate_k=5)
    with pytest.raises(InvariantError, match="weights"):
        RetrievalVariant("x", lexical_weight=0, vector_weight=0)
    with pytest.raises(InvariantError, match="budget_tokens"):
        RetrievalVariant("x", budget_tokens=100)


REJECTED = [
    ({"extras": {}}, "unknown eval config sections"),
    ({}, "at least one retrieval variant"),
    ({"retrieval_variants": [{"id": "wide"}]}, "must be 'baseline'"),
    ({"retrieval_variants": [{"id": "baseline"}, {"id": "baseline"}]}, "unique"),
    ({"retrieval_variants": [{"id": "baseline", "rerank": True}]}, "unknown keys"),
    (
        {"retrieval_variants": [{"id": "baseline"}], "judge_prompts": ["loose"]},
        "judge_prompts",
    ),
    (
        {"retrieval_variants": [{"id": "baseline"}], "id_variants": ["shout"]},
        "id_variants",
    ),
    (
        {
            "retrieval_variants": [{"id": "baseline"}],
            "selection_rules": {"speed": {"primary": "s"}},
        },
        "rule kinds",
    ),
    (
        {
            "retrieval_variants": [{"id": "baseline"}],
            "selection_rules": {"retrieval": {"primary": "m", "x": 1}},
        },
        "unknown keys",
    ),
    (
        {
            "retrieval_variants": [{"id": "baseline"}],
            "selection_rules": {"retrieval": {"primary": "m", "tie_breakers": [["a"]]}},
        },
        "tie breaker",
    ),
    (
        {
            "retrieval_variants": [{"id": "baseline"}],
            "selection": {"retrieval": {"variant": "a", "why": "b"}},
        },
        "unknown keys",
    ),
    (
        {"retrieval_variants": [{"id": "baseline"}], "live": {"max_generations": -1}},
        "caps",
    ),
    ({"retrieval_variants": [{"id": "baseline"}], "files": "eval"}, "mapping"),
]


def test_rejected() -> None:
    for data, message in REJECTED:
        with pytest.raises(InvariantError, match=message):
            eval_settings_from_dict(data)

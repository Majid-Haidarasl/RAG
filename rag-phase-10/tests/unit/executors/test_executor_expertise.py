"""Expertise vocabulary: tokenizer, light stemming and profile terms."""

import pytest

from rag_core.executors.domain.expertise import ExpertiseProfile, stem, terms
from tests.fixtures.executors.registry import make_executor

pytestmark = [pytest.mark.executors, pytest.mark.matching]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("dashboards", "dashboard"), ("reporting", "report"), ("penalties", "penalty"), ("tests", "test"),
     ("testing", "test"), ("process", "process"), ("api", "api"), ("windows", "window")],
)
def test_stem(raw: str, expected: str) -> None:
    assert stem(raw) == expected


def test_terms_drop_stopwords_numbers_and_single_letters() -> None:
    out = terms("Penalty, extension to 20 Mehr 1403 and amendment versus scope")
    assert out == frozenset({"penalty", "extension", "mehr", "amendment", "scope"})


def test_terms_handle_dotnet_and_hyphens() -> None:
    assert terms("C#/.NET client") == frozenset({"net", "client"})
    assert terms("multi-station tests") == frozenset({"multi", "station", "test"})


def test_persian_text_gives_no_english_terms() -> None:
    out = terms("سازگاری کنترلر RAID")
    assert "raid" in out
    assert not out & {"controller", "compatibility"}


def test_profile_vocabulary_uses_specialty_domains_and_tags_only() -> None:
    person = make_executor(specialty=("React",), domains=("Enterprise web interfaces",), expertise=("error states",))
    person.outputs = ("accessibility evidence",)
    profile = ExpertiseProfile.of(person)
    assert profile.vocabulary == frozenset({"react", "enterprise", "web", "interface", "error", "state"})
    assert "accessibility" not in profile.vocabulary


def test_matched_terms_are_sorted() -> None:
    person = make_executor(specialty=("React",), domains=("dashboards",), expertise=("reporting views",))
    profile = ExpertiseProfile.of(person)
    assert profile.matched(terms("React dashboard for reporting")) == ("dashboard", "react", "report")
    assert profile.matched_domain_terms(terms("React dashboard")) == ("dashboard",)

"""Phase 16 release rules: versions, phrase scan, documents, changelog and slide count."""

import pytest

from rag_core.quality.domain.release import (
    DocRequirement,
    PhraseHit,
    changelog_problems,
    changelog_versions,
    check_doc,
    find_phrases,
    presentation_problems,
    require_version,
    scan_texts,
    slide_count,
    version_problems,
)
from rag_core.shared_kernel.errors import InvariantError

pytestmark = [pytest.mark.release]

PPTX_BASE = ["[Content_Types].xml", "ppt/presentation.xml"]


def slides(n: int) -> list[str]:
    return [*PPTX_BASE, *(f"ppt/slides/slide{i}.xml" for i in range(1, n + 1)),
            *(f"ppt/slides/_rels/slide{i}.xml.rels" for i in range(1, n + 1))]


@pytest.mark.parametrize("value", ["1.0.0", "0.15.0", "12.3.45"])
def test_require_version_ok(value: str) -> None:
    assert require_version(value, "x") == value


@pytest.mark.parametrize("value", ["", "1.0", "v1.0.0", "1.0.0-rc1", "one"])
def test_require_version_rejects(value: str) -> None:
    with pytest.raises(InvariantError):
        require_version(value, "x")


def test_version_problems() -> None:
    found = {"pyproject.toml": "1.0.0", "config/eval.yaml": "0.15.0", "config/quality.yaml": None}
    assert version_problems("1.0.0", found) == ["config/eval.yaml=0.15.0", "config/quality.yaml=-"]
    assert version_problems("1.0.0", {"a": "1.0.0"}) == []
    with pytest.raises(InvariantError):
        version_problems("1.0", {})


def test_find_phrases_ignores_case_and_reports_lines() -> None:
    text = "first line\nThe Draft Marker is here\nnothing\ndraft marker again, and OTHER WORD\n"
    assert find_phrases(text, ["draft marker", "other word"]) == [(2, "draft marker"), (4, "draft marker"),
                                                                   (4, "other word")]
    assert find_phrases("", ["x"]) == [] and find_phrases("abc", ["  "]) == []


def test_scan_texts() -> None:
    hits = scan_texts([("a.md", "ok\nbad words"), ("b.py", "# fine")], ["bad words"])
    assert hits == [PhraseHit("a.md", 2, "bad words")] and str(hits[0]) == "a.md:2:bad words"
    assert scan_texts([("c.md", "clean")], ["bad words"]) == []
    with pytest.raises(InvariantError):
        scan_texts([("a.md", "x")], [" "])


def test_check_doc() -> None:
    req = DocRequirement("README.md", 20, ("setup", "guide"))
    good = check_doc(req, "# Kit\n\nRun setup, then read the guide.\n")
    assert good.ok and good.reason == "ok" and good.exists
    assert check_doc(req, None).reason == "missing" and not check_doc(req, None).ok
    assert check_doc(req, "setup guide").reason == "short:11<20"
    partial = check_doc(req, "Run setup and read everything else carefully.")
    assert not partial.ok and partial.reason == "markers:guide" and partial.missing_markers == ("guide",)


@pytest.mark.parametrize("path", ["", "/etc/x.md", "../x.md", "docs/../../x.md"])
def test_doc_requirement_paths(path: str) -> None:
    with pytest.raises(InvariantError):
        DocRequirement(path)


def test_doc_requirement_min_chars() -> None:
    with pytest.raises(InvariantError):
        DocRequirement("a.md", -1)


LOG = "# Changelog\n\n## [1.0.0] — 1405-09-04\n- release\n\n## [0.15.0]\n- quality\n\n## 0.14.0\n- eval\n"


def test_changelog_versions_and_problems() -> None:
    assert changelog_versions(LOG) == ["1.0.0", "0.15.0", "0.14.0"]
    assert changelog_problems(LOG, ["0.14.0", "0.15.0", "1.0.0"], "1.0.0") == []
    assert changelog_problems(LOG, ["0.13.0", "1.0.0"], "1.0.0") == ["missing:0.13.0"]
    assert changelog_problems(LOG, [], "1.1.0") == ["newest:1.0.0!=1.1.0"]
    assert changelog_problems("# Changelog\n", ["1.0.0"], "1.0.0") == ["missing:1.0.0", "no_versions"]
    assert changelog_problems(LOG + "\n## [0.15.0]\n", [], "1.0.0") == ["duplicate:0.15.0"]


def test_slide_count() -> None:
    assert slide_count(slides(11)) == 11
    assert slide_count(["ppt/slides/slide1.xml.bak", "ppt/slideLayouts/slideLayout1.xml"]) == 0


@pytest.mark.parametrize(("names", "problems"), [
    (slides(10), []),
    (slides(12), []),
    (slides(9), ["slides:9 outside 10..12"]),
    (slides(13), ["slides:13 outside 10..12"]),
    (None, ["missing"]),
    (["word/document.xml", "[Content_Types].xml"], ["not_a_pptx"]),
])
def test_presentation_problems(names: list[str] | None, problems: list[str]) -> None:
    assert presentation_problems(names, 10, 12) == problems


@pytest.mark.parametrize(("lo", "hi"), [(0, 5), (6, 5)])
def test_presentation_limits(lo: int, hi: int) -> None:
    with pytest.raises(InvariantError):
        presentation_problems([], lo, hi)

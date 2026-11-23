"""The shipped kit passes its own release rules (versions, documents, phrases, slides, defaults)."""

from pathlib import Path

import pytest

from rag_core import __version__
from rag_core.quality.domain.checklist import by_phase, checklist_problems, status_counts
from rag_core.quality.domain.release import (
    changelog_problems,
    check_doc,
    presentation_problems,
    scan_texts,
    slide_count,
    version_problems,
)
from rag_core.quality.infrastructure.checklist_yaml import load_deliverables
from rag_core.quality.infrastructure.release_config import load_release_settings
from rag_core.quality.infrastructure.release_files import kit_texts, read_text, version_in, zip_names
from rag_core.tuning.domain.variants import selection_problems
from rag_core.tuning.infrastructure.config import load_eval_settings

pytestmark = [pytest.mark.release]

ROOT = Path(__file__).resolve().parents[3]
RSET = load_release_settings(ROOT / "config" / "release.yaml")


def test_versions_agree() -> None:
    found = {where: version_in(ROOT, where, how) for where, how in RSET.versions.items()}
    assert __version__ == "1.0.0" and len(found) == 6
    assert version_problems(RSET.version, {**found, "package": __version__}) == []


@pytest.mark.parametrize("req", RSET.docs, ids=[d.path for d in RSET.docs])
def test_release_document_complete(req) -> None:  # noqa: ANN001
    result = check_doc(req, read_text(ROOT, req.path))
    assert result.ok, result.reason


def test_no_drafting_phrases_in_the_kit() -> None:
    texts = list(kit_texts(ROOT, RSET.scan.suffixes, RSET.scan.exclude))
    assert len(texts) > 300
    assert [str(h) for h in scan_texts(texts, RSET.scan.phrases)] == []


def test_scan_finds_planted_phrases(tmp_path: Path) -> None:
    for i, phrase in enumerate(RSET.scan.phrases):
        (tmp_path / f"note{i}.md").write_text(f"# Note\n\nline\n>> {phrase.title()} <<\n", encoding="utf-8")
    (tmp_path / "clean.md").write_text("# Clean\n", encoding="utf-8")
    hits = scan_texts(kit_texts(tmp_path, RSET.scan.suffixes, ()), RSET.scan.phrases)
    assert len({h.path for h in hits}) == len(RSET.scan.phrases) and all(h.line == 4 for h in hits)


def test_changelog_lists_every_version() -> None:
    text = read_text(ROOT, RSET.changelog.path)
    assert text is not None and changelog_problems(text, RSET.changelog.versions, RSET.version) == []


def test_presentation_deck_and_source() -> None:
    names = zip_names(ROOT / RSET.presentation.path)
    assert presentation_problems(names, RSET.presentation.min_slides, RSET.presentation.max_slides) == []
    assert 10 <= slide_count(names) <= 12
    source = read_text(ROOT, RSET.presentation.source)
    assert source is not None and "pptxgenjs" in source and source.count("function slide") >= 10


def test_eval_defaults_match_the_release() -> None:
    eset = load_eval_settings(ROOT / "config" / "eval.yaml")
    configured = {k: s.variant for k, s in eset.selection.items()}
    assert {k: configured.get(k) for k in RSET.eval_expected} == RSET.eval_expected
    assert configured["ai_ids"] == "baseline" and "listed_guarded" in eset.known_variants()["ai_ids"]
    assert selection_problems(eset.selection, eset.known_variants()) == []


def test_checklist_only_the_release_tag_is_left() -> None:
    items = load_deliverables(ROOT / "config" / "release-checklist.yaml")
    assert checklist_problems(items, lambda p: (ROOT / p).exists()) == []
    assert status_counts(items)["planned"] == 1
    assert [d.spec for d in by_phase(items)[16] if d.status == "planned"] == [f"release tag {RSET.tag}"]


def test_evidence_index_names_every_pattern() -> None:
    text = read_text(ROOT, "eval/evidence/README.md") or ""
    missing = [e.pattern for e in RSET.evidence if e.pattern not in text]
    assert missing == []

"""Version states, effective dates, supersedes chain (Phase 5)."""

import pytest

from rag_core.knowledge.domain.model import ChunkStatus, VersionStatus, VersionTag
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.knowledge.factories import D0, D1, D2, EN, FA, chunks, item

pytestmark = [pytest.mark.knowledge, pytest.mark.lifecycle]

V10, V11, V12 = VersionTag(1, 0), VersionTag(1, 1), VersionTag(1, 2)


def test_registered_version_is_active_with_effective_from_and_no_predecessor() -> None:
    it = item(on=D0)
    v = it.active_version(FA)
    assert v.status is VersionStatus.ACTIVE
    assert v.effective_from == D0 and v.effective_to is None
    assert v.supersedes is None and v.file_sha256 == "sha-v1"


def test_inactive_is_phase3_alias_of_superseded() -> None:
    assert VersionStatus.INACTIVE is VersionStatus.SUPERSEDED


def test_stage_draft_keeps_active_version_and_links_supersedes() -> None:
    it = item()
    draft = it.stage_draft(V11, FA, chunks("AR-HW-012", "بند جدید"))
    assert draft.status is VersionStatus.DRAFT
    assert draft.supersedes == V10
    assert it.active_version(FA).tag == V10


def test_activate_draft_supersedes_previous_and_closes_its_effective_window() -> None:
    it = item(on=D0)
    it.stage_draft(V11, FA, chunks("AR-HW-012", "بند جدید"))
    it.activate(V11, FA, effective_from=D1)
    old, new = it.get_version(V10, FA), it.get_version(V11, FA)
    assert old.status is VersionStatus.SUPERSEDED and old.effective_to == D1
    assert new.status is VersionStatus.ACTIVE and new.effective_from == D1


def test_supersedes_chain_runs_newest_to_oldest() -> None:
    it = item(on=D0)
    it.add_version(V11, FA, chunks("AR-HW-012", "دو"), effective_from=D1)
    it.add_version(V12, FA, chunks("AR-HW-012", "سه"), effective_from=D2)
    assert it.supersedes_chain(FA) == [V12, V11, V10]


def test_only_one_draft_per_language() -> None:
    it = item()
    it.stage_draft(V11, FA, chunks("AR-HW-012", "x"))
    with pytest.raises(InvariantError, match="draft already exists"):
        it.stage_draft(V12, FA, chunks("AR-HW-012", "y"))


def test_version_tags_must_strictly_increase_per_language() -> None:
    it = item()
    it.add_version(V12, FA, chunks("AR-HW-012", "x"), effective_from=D1)
    with pytest.raises(InvariantError, match="greater than"):
        it.stage_draft(V11, FA, chunks("AR-HW-012", "y"))


def test_at_most_one_active_version_per_language() -> None:
    it = item()
    it.add_version(V11, FA, chunks("AR-HW-012", "x"), effective_from=D1)
    it.add_version(V12, FA, chunks("AR-HW-012", "y"), effective_from=D2)
    assert sum(v.status is VersionStatus.ACTIVE for v in it.versions_for(FA)) == 1


def test_activation_cannot_backdate_before_superseded_version() -> None:
    it = item(on=D1)
    it.stage_draft(V11, FA, chunks("AR-HW-012", "x"))
    with pytest.raises(InvariantError, match="precede"):
        it.activate(V11, FA, effective_from=D0)


def test_only_drafts_can_be_activated() -> None:
    it = item()
    with pytest.raises(InvariantError, match="only a draft"):
        it.activate(V10, FA)


def test_active_version_cannot_be_archived_but_superseded_can() -> None:
    it = item()
    with pytest.raises(InvariantError, match="cannot be archived"):
        it.archive(V10, FA)
    it.add_version(V11, FA, chunks("AR-HW-012", "x"), effective_from=D1)
    assert it.archive(V10, FA).status is VersionStatus.ARCHIVED


def test_withdraw_archives_active_without_replacement() -> None:
    it = item()
    v = it.withdraw(FA, on=D1)
    assert v.status is VersionStatus.ARCHIVED and v.effective_to == D1
    assert it.find_active(FA) is None
    assert it.active_chunks(FA) == []


def test_languages_have_independent_lifecycles() -> None:
    it = item(on=D0)
    it.add_version(V10, EN, chunks("AR-HW-012", "clause one"), effective_from=D0)
    it.add_version(V11, FA, chunks("AR-HW-012", "بند تازه"), effective_from=D1)
    assert it.active_version(EN).tag == V10
    assert it.active_version(FA).tag == V11
    assert all(c.status is ChunkStatus.ACTIVE for c in it.active_version(EN).chunks)


def test_lifecycle_emits_domain_events_in_order() -> None:
    it = item()
    it.events.clear()
    it.stage_draft(V11, FA, chunks("AR-HW-012", "x"))
    it.activate(V11, FA, effective_from=D1)
    names = [e.name for e in it.events]
    assert names == [
        "KnowledgeVersionDrafted",
        "ChunksMarkedStale",
        "KnowledgeVersionSuperseded",
        "ChunksRetired",
        "KnowledgeVersionActivated",
    ]
    assert it.events[1].payload["count"] == 2

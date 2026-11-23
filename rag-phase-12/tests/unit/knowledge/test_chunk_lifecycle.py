"""Chunk states tied to their version, and re-ingest by file sha256 (Phase 5)."""

import pytest

from rag_core.knowledge.domain.model import ChunkStatus, KnowledgeChunk, VersionStatus, VersionTag
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.knowledge.factories import D1, FA, chunks, item

pytestmark = [pytest.mark.knowledge, pytest.mark.lifecycle]

V10, V11 = VersionTag(1, 0), VersionTag(1, 1)


def test_new_chunks_start_active_and_carry_normalized_hash() -> None:
    c = KnowledgeChunk(chunk_id="d#c0001", order=1, text="می‌رود")
    assert c.status is ChunkStatus.ACTIVE
    assert c.normalized_hash == KnowledgeChunk(chunk_id="x", order=1, text="میرود").normalized_hash
    assert c.content_hash != KnowledgeChunk(chunk_id="x", order=1, text="میرود").content_hash


def test_chunk_is_immutable_and_status_change_returns_copy() -> None:
    c = KnowledgeChunk(chunk_id="d#c0001", order=1, text="t")
    r = c.with_status(ChunkStatus.RETIRED)
    assert c.status is ChunkStatus.ACTIVE and r.status is ChunkStatus.RETIRED
    with pytest.raises(AttributeError):
        c.status = ChunkStatus.STALE  # type: ignore[misc]


def test_staging_draft_marks_active_chunks_stale_but_still_retrievable() -> None:
    it = item()
    it.stage_draft(V11, FA, chunks("AR-HW-012", "x"))
    active = it.active_version(FA)
    assert {c.status for c in active.chunks} == {ChunkStatus.STALE}
    assert len(it.active_chunks(FA)) == 2  # stale chunks still serve until activation


def test_activation_retires_all_chunks_of_previous_version() -> None:
    it = item()
    it.add_version(V11, FA, chunks("AR-HW-012", "x", "y", "z"), effective_from=D1)
    old = it.get_version(V10, FA)
    assert old.count(ChunkStatus.RETIRED) == 2
    assert [c.text for c in it.active_chunks(FA)] == ["x", "y", "z"]


def test_discarding_draft_restores_stale_chunks_and_archives_draft() -> None:
    it = item()
    it.stage_draft(V11, FA, chunks("AR-HW-012", "x"))
    d = it.discard_draft(FA)
    assert d.status is VersionStatus.ARCHIVED
    assert d.count(ChunkStatus.RETIRED) == 1
    assert {c.status for c in it.active_version(FA).chunks} == {ChunkStatus.ACTIVE}


def test_qualified_chunk_id_includes_version_and_language() -> None:
    it = item()
    v = it.active_version(FA)
    assert v.qualified_chunk_id(it.document_id, v.chunks[0]) == "AR-HW-012@1.0/fa#c0001"


def test_reingest_unchanged_sha_is_noop_with_event() -> None:
    it = item(sha="abc")
    assert it.reingest(FA, "abc", chunks("AR-HW-012", "x")) is None
    assert it.events[-1].name == "ReingestSkippedUnchanged"
    assert len(it.versions_for(FA)) == 1


def test_reingest_changed_sha_bumps_minor_and_retires_old_chunks() -> None:
    it = item(sha="abc")
    v = it.reingest(FA, "def", chunks("AR-HW-012", "x"), effective_from=D1)
    assert v is not None and v.tag == V11 and v.supersedes == V10 and v.file_sha256 == "def"
    assert it.get_version(V10, FA).count(ChunkStatus.RETIRED) == 2


def test_reingest_requires_sha() -> None:
    with pytest.raises(InvariantError, match="sha256"):
        item().reingest(FA, "", chunks("AR-HW-012", "x"))


def test_superseded_and_archived_versions_hold_only_retired_chunks() -> None:
    it = item()
    it.add_version(V11, FA, chunks("AR-HW-012", "x"), effective_from=D1)
    it.archive(V10, FA)
    for v in it.versions_for(FA):
        if v.status in {VersionStatus.SUPERSEDED, VersionStatus.ARCHIVED}:
            assert v.count(ChunkStatus.RETIRED) == len(v.chunks)

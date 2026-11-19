"""Executor registry (data/executors/executor-registry.json, from AR-EXE-023)."""

import pytest

from rag_core.executors.application.services import corpus_document_ids
from rag_core.executors.domain.model import executor_id_for
from rag_core.executors.domain.validation import ExecutorRegistryValidator
from rag_core.executors.infrastructure.memory import InMemoryExecutorRepository
from rag_core.executors.infrastructure.registry_json import executor_from_record
from rag_core.shared_kernel.errors import NotFoundError
from rag_core.shared_kernel.identifiers import ExecutorId
from tests.fixtures.executors.registry import raw_records, shipped_executors, team_directory

pytestmark = [pytest.mark.executors, pytest.mark.matching]


def _validate(records: list[dict]):  # noqa: ANN202
    return ExecutorRegistryValidator(team_directory(), corpus_document_ids()).validate(records)


def test_shipped_registry_is_valid_with_three_unpublished_capacities() -> None:
    report = _validate(raw_records())
    assert report.ok, report.errors
    assert report.checked == 15
    assert len(report.warnings) == 3
    assert {w.executor_id for w in report.warnings} == {"EX-BAHAR-ESKANDARI", "EX-REZA-ABBASI", "EX-MAHSA-JALALI"}


def test_shipped_executors_are_people_on_execution_teams() -> None:
    executors = shipped_executors()
    assert len(executors) == 15
    for e in executors:
        assert e.identifier == executor_id_for(e.display_name)
        assert team_directory().team(str(e.home_node)).layer == 3
        assert e.knowledge_documents and e.allowed_referral_domains and e.expertise


def test_registry_never_carries_pay() -> None:
    for rec in raw_records():
        assert not {"pay", "salary", "compensation", "pay_mtoman"} & set(rec)


def test_rouzbeh_spelling_maps_to_registry_record() -> None:
    repo = InMemoryExecutorRepository(shipped_executors())
    person = repo.by_name("Rouzbeh Mohseni")
    assert person.identifier == ExecutorId("EX-ROOZBEH-MOHSENI")
    assert person.display_name == "Roozbeh Mohseni" and person.name_fa == "روزبه محسنی"
    with pytest.raises(NotFoundError):
        repo.by_name("Nobody Here")


def test_record_mapping() -> None:
    rec = next(r for r in raw_records() if r["id"] == "EX-MAHSA-JALALI")
    person = executor_from_record(rec)
    assert str(person.home_node) == "N-ADM-LEG"
    assert not person.capacity.is_published
    assert [str(d) for d in person.knowledge_documents] == ["AR-LEG-009"]
    assert person.role == "Legal and contracts specialist" and person.source_document == "AR-EXE-023"


def _mutated(**changes: object) -> list[dict]:
    records = raw_records()
    records[0].update(changes)
    return records


@pytest.mark.parametrize(
    ("changes", "rule"),
    [
        ({"home_node": "N-SW-XYZ"}, "home_node"),
        ({"home_node": "N-SW"}, "home_node_layer"),
        ({"knowledge_documents": ["AR-SW-099"]}, "knowledge_document"),
        ({"capacity_hours_per_week": 80}, "capacity"),
        ({"id": "EX-SOMEONE-ELSE"}, "id_from_name"),
        ({"id": "not an id!"}, "id"),
        ({"expertise": []}, "required"),
    ],
)
def test_validator_errors(changes: dict, rule: str) -> None:
    report = _validate(_mutated(**changes))
    assert not report.ok
    assert rule in {e.rule for e in report.errors}


def test_duplicate_id_is_an_error() -> None:
    records = raw_records()
    records.append(dict(records[0]))
    report = _validate(records)
    assert "unique" in {e.rule for e in report.errors}


def test_pay_field_is_flagged() -> None:
    report = _validate(_mutated(pay_mtoman=52))
    assert report.ok
    assert "confidential" in {w.rule for w in report.warnings}

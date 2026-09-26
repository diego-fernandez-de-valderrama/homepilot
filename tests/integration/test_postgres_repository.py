"""PostgresRepository against a real, freshly migrated PostgreSQL (skipped when unreachable)."""

import pytest
from sqlalchemy import func, select

from catalog_ingestion.domain.enums import WebStatus
from catalog_ingestion.pipeline.stages import prepare
from catalog_ingestion.retrieval.documents import build_document
from catalog_ingestion.storage.postgres.engine import create_session_factory, upgrade_to_head
from catalog_ingestion.storage.postgres.models import (
    CompatibilityRecord,
    IngestionRunRecord,
    ProductRecord,
    RequirementRecord,
)
from catalog_ingestion.storage.postgres.repository import PostgresRepository, UpsertOutcome
from catalog_ingestion.validation.validator import Validator
from tests.conftest import BOSCH_CONTROLLER, HOMEMATIC_OR, load_raw

pytestmark = pytest.mark.integration


@pytest.fixture
def repository(empty_database):
    upgrade_to_head(empty_database)
    sessions = create_session_factory(empty_database)
    return PostgresRepository(sessions), sessions


def _enriched(product_id: str):
    prepared = prepare(load_raw(product_id))
    enriched = Validator().validate(
        prepared.product, prepared.completeness, prepared.facts, prepared.requirements,
        WebStatus.NOT_NEEDED, None, None, None, None,
    )  # fmt: skip
    return prepared, enriched


def _count(sessions, model, product_id: str) -> int:
    with sessions() as session:
        return session.scalar(select(func.count()).select_from(model).where(model.product_id == product_id))


def test_upsert_is_idempotent_and_replaces_children(repository):
    repo, sessions = repository
    prepared, enriched = _enriched(BOSCH_CONTROLLER)

    assert repo.upsert_product(enriched, prepared.raw, prepared.raw_hash, None, None) is UpsertOutcome.INSERTED
    facts = _count(sessions, CompatibilityRecord, BOSCH_CONTROLLER)
    assert facts == len(enriched.compatibility) > 0
    assert repo.upsert_product(enriched, prepared.raw, prepared.raw_hash, None, None) is UpsertOutcome.UNCHANGED
    assert repo.upsert_product(enriched, prepared.raw, "new-raw-hash", None, None) is UpsertOutcome.UPDATED
    assert _count(sessions, CompatibilityRecord, BOSCH_CONTROLLER) == facts  # replaced, not duplicated

    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(ProductRecord)) == 1
        record = session.get_one(ProductRecord, BOSCH_CONTROLLER)
        assert record.raw == dict(prepared.raw.original)
        assert record.document["id"] == BOSCH_CONTROLLER
        assert record.attributes["Weiterführende Produktinformationen"]["EAN"] == "4057749322746"
    assert repo.load_enriched([BOSCH_CONTROLLER]) == [enriched]


def test_requirements_alternatives_and_deactivation(repository):
    repo, sessions = repository
    for product_id in (BOSCH_CONTROLLER, HOMEMATIC_OR):
        prepared, enriched = _enriched(product_id)
        repo.upsert_product(enriched, prepared.raw, prepared.raw_hash, None, None)

    with sessions() as session:
        alternatives = session.scalar(
            select(RequirementRecord.alternatives).where(RequirementRecord.product_id == HOMEMATIC_OR)
        )
    assert alternatives is not None and "homematic_ccu3" in alternatives

    assert repo.deactivate_missing([BOSCH_CONTROLLER]) == [HOMEMATIC_OR]
    assert repo.deactivate_missing([BOSCH_CONTROLLER]) == []
    assert [e.id for e in repo.load_enriched()] == [BOSCH_CONTROLLER]


def test_documents_runs_and_status(repository):
    repo, _ = repository
    prepared, enriched = _enriched(BOSCH_CONTROLLER)
    repo.upsert_product(enriched, prepared.raw, prepared.raw_hash, None, None)
    document = build_document(enriched)
    repo.save_document(document)
    repo.save_document(document)
    repo.mark_indexed([document], "model@8")

    run_id = repo.start_run({"command": "test"})
    repo.finish_run(run_id, "succeeded", {"loaded": 1})

    status = repo.status()
    assert status["products"] == {"active": 1, "inactive": 0, "llm_enriched": 0}
    assert status["completeness"] == {"rich": 1}
    assert status["last_run"]["status"] == "succeeded"
    assert status["last_run"]["stats"] == {"loaded": 1}


def test_runs_left_running_are_marked_abandoned(repository):
    repo, sessions = repository
    killed = repo.start_run({"command": "ingest"})  # never finished (process killed)
    repo.start_run({"command": "ingest"})
    with sessions() as session:
        assert session.get_one(IngestionRunRecord, killed).status == "abandoned"

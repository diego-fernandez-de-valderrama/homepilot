"""Customer memory against PostgreSQL: a throwaway `<AGENT_MEMORY_DB>_test` database, migrated with Alembic."""

from collections.abc import Iterator

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from catalog_ingestion.storage.postgres.engine import create_session_factory
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError

from smart_home_agent.config import Settings
from smart_home_agent.models import FactKind, NewFact
from smart_home_agent.repositories import MemoryDatabase, ProfileRepository
from smart_home_agent.services import ProfileService

pytestmark = pytest.mark.integration


@pytest.fixture
def memory_engine(settings: Settings) -> Iterator[Engine]:
    name = f"{settings.agent.memory_db}_test"
    admin = create_engine(settings.postgres.url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
    try:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    except OperationalError:
        pytest.skip("PostgreSQL not reachable (docker compose up -d in catalog-ingestion)")
    finally:
        admin.dispose()
    database = MemoryDatabase(settings.postgres, name)
    assert database.ensure_exists() is True
    assert database.ensure_exists() is False  # idempotent
    engine = database.create_engine()
    MemoryDatabase.upgrade_to_head(engine)
    yield engine
    engine.dispose()


def test_migrations_match_the_models(memory_engine: Engine):
    with memory_engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), MemoryDatabase.METADATA) == []
    MemoryDatabase.upgrade_to_head(memory_engine)  # running again is a no-op
    with memory_engine.begin() as connection:
        config = MemoryDatabase.alembic_config()
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        command.upgrade(config, "head")


def test_repository_round_trip_through_the_service(memory_engine: Engine):
    repository = ProfileRepository(create_session_factory(memory_engine))
    service = ProfileService(repository)
    service.remember(
        "anna", "s1", "I'm Anna and I use HomeKit", "I'm Anna and I use HomeKit", name="Anna", ecosystems=["HomeKit"]
    )
    service.remember("anna", "s2", "Call me Annie", "Call me Annie", name="Annie")
    service.remember("ben", "s3", "I use Alexa", "I use Alexa", ecosystems=["Alexa"])

    profile = repository.load("anna", include_retracted=True)
    assert [(f.kind, f.value, f.active) for f in profile.facts] == [
        (FactKind.NAME, "Anna", False),
        (FactKind.ECOSYSTEM, "apple_home", True),
        (FactKind.NAME, "Annie", True),
    ]
    old = profile.facts[0]
    assert old.retracted_at is not None and old.retracted_evidence == "Call me Annie"
    assert profile.facts[1].evidence == "I'm Anna and I use HomeKit" and profile.facts[1].session_id == "s1"
    assert [f.value for f in repository.load("ben").facts] == ["amazon_alexa"]


def test_one_active_fact_per_value(memory_engine: Engine):
    repository = ProfileRepository(create_session_factory(memory_engine))
    fact = NewFact(kind=FactKind.ECOSYSTEM, value="apple_home", canonical="apple_home", label="HomeKit")
    [stored], _ = repository.apply("anna", "s1", "I use HomeKit", [fact], [])
    with pytest.raises(IntegrityError):
        repository.apply("anna", "s1", "I use HomeKit", [fact], [])
    _, [retracted] = repository.apply("anna", "s1", "no more HomeKit", [], [stored.id])
    assert not retracted.active
    repository.apply("anna", "s1", "HomeKit again", [fact], [])  # allowed again once retracted
    assert [f.active for f in repository.load("anna", include_retracted=True).facts] == [False, True]


def test_customers_are_listed_most_recent_first_with_counts(memory_engine: Engine):
    repository = ProfileRepository(create_session_factory(memory_engine))
    service = ProfileService(repository)
    service.remember(
        "anna", "s1", "I use HomeKit and Alexa", "I use HomeKit and Alexa", ecosystems=["HomeKit", "Alexa"]
    )
    service.remember("ben", "s2", "I use Alexa", "I use Alexa", ecosystems=["Alexa"])
    assert [(c.user_id, c.active_facts, c.total_facts) for c in repository.customers()] == [
        ("ben", 1, 1),
        ("anna", 2, 2),
    ]
    service.remember("anna", "s3", "I stopped using Alexa", "I stopped using Alexa", no_longer_used=["Alexa"])
    # A retraction is activity too: anna is now the most recent, with one active fact left.
    assert [(c.user_id, c.active_facts, c.total_facts) for c in repository.customers()] == [
        ("anna", 1, 2),
        ("ben", 1, 1),
    ]

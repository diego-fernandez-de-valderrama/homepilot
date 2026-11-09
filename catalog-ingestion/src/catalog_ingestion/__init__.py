"""Catalog ingestion and enrichment for the HomePilot smart home agent.

products.zip -> PostgreSQL (source of truth) + Qdrant (semantic discovery). One package per step of the flow;
each package's `__init__` is its entry point (import from there, never from its modules):

    core         settings, logging, hashing, the Gemini client (shared infrastructure)
    vocabulary   enums and canonical ids (ecosystems, voice assistants, protocols, requirements, categories)
    models       domain dataclasses, Pydantic boundary schemas and the mappers between them
    preparation  1. load the zip, normalize, extract deterministic facts, assess completeness
    enrichment   2. product page (web), LLM enrichment, validation against the sources
    database     PostgreSQL: ORM records, migrations, `PostgresRepository`
    indexing     3. retrieval documents, embeddings, Qdrant
    pipeline     `IngestionPipeline`: runs the steps (`ingest`, `reindex`)
    cli          the `catalog-ingestion` command

Dependencies only point downward in this list; the agent (smart-home-agent) reads `core`, `vocabulary`,
`models`, `database` and `indexing`.
"""

__version__ = "0.1.0"

# HomePilot Catalog Ingestion

This service ingests `products.zip`, normalizes, enriches and validates every product, and records where each fact came from. It persists the result in two stores:

- **PostgreSQL**: the structured source of truth, used for exact filtering, comparison and deterministic compatibility checks.
- **Qdrant**: semantic retrieval ("find me a thermostat that works with HomeKit").

It is the data layer of the HomePilot Smart Home Conversational Agent (Google ADK + Gemini). The agent, UI, recommendation, comparison and guardrail logic live in [`../smart-home-agent`](../smart-home-agent) and build on this catalog.

---

## Contents

1. [Dataset findings](#dataset-findings)
2. [Architecture](#architecture)
3. [Data flow](#data-flow)
4. [Enrichment strategy](#enrichment-strategy)
5. [Compatibility representation](#compatibility-representation)
6. [Provenance](#provenance)
7. [Database model (PostgreSQL)](#database-model-postgresql)
8. [Qdrant model](#qdrant-model)
9. [How to run](#how-to-run)
10. [Re-running ingestion (idempotency)](#re-running-ingestion-idempotency)
11. [How persistence works / how to reset](#how-persistence-works--how-to-reset)
12. [Tests](#tests)
13. [Configuration](#configuration)
14. [Notes for the agent](#notes-for-the-agent)

---

## Dataset findings

Every file in the zip was inspected. Reproduce this with `uv run catalog-ingestion analyze`.

| Finding | Consequence |
|---|---|
| 943 products as `info/<id>.json`, plus `__MACOSX/` metadata files | The loader skips `__MACOSX/` and `._*` entries and reports invalid files instead of failing. |
| All 9 keys are always present, but values can be empty: description empty in **106**, attributes empty in **67**, **both empty in 33** | The pipeline never assumes description/attributes exist. Completeness is scored per product. |
| `url` always ends with `\n`. Format: `bauhaus.info/<category-slug>/<name-slug>/p/<id>` | The URL is stripped in the normalized record (the raw copy keeps it). **The category exists only in the URL slug.** |
| 102 distinct category slugs, 6 of them brand pages (`shelly-smart-home`, `homematic-ip-smart-home`, ...) | A deterministic slug→category map covers 30 canonical categories. The 18 products on brand-page slugs get their category from the LLM, restricted to the same enum. |
| Price formats `124,95 €`, `999,- €`, `9.999,- €`, and one multi-line discount `Ersparnis: 20,- €\nStatt 159,95\n139,95 €` | A dedicated parser returns price, original price and savings. |
| `attributes` is a flat newline blob: leading badges (`Nicht im Hausmüll entsorgen`, `Dimmbar`, `RGBW`, `Bluetooth`), 8 fixed section headers, then alternating key/value lines, plus a value-less sub-header `Beständigkeit` | Parsed deterministically into `(section, key, value)` entries. 302 distinct keys. Only **1** line in the whole dataset cannot be paired; it is kept in `unparsed_attribute_lines`. |
| Compatibility lives in a few keys: `Unterstützte Sprachsteuerung`, `Unterstützte Systeme`, `Smarte Steuerung` (compound values like `Philips Hue App + Google Home`), `Datenübertragung`, `Unterstützte Betriebssysteme` | These keys become compatibility facts without any LLM (source `catalog`, confidence 1.0). |
| Requirements are in `Anforderungen`, `Hinweise` (free text, e.g. Homematic's "Access Point **or** CCU3 **or** partner solution"; parenthesised negatives like "(nicht mehr kompatibel mit der Zentrale CCU2)") and `Installationshinweis` | Pattern-based extraction with OR-alternatives. Negative parentheticals are removed before matching. |
| `Apple Siri` appears as a voice assistant on many products that do **not** list HomeKit | Siri never implies HomeKit (see [compatibility](#compatibility-representation)). |
| "Matter" appears only in titles and descriptions (15 products), e.g. `... [+M] Matter` | Matter is read from the title deterministically. Mentions in descriptions are left to the LLM, with evidence. |
| Descriptions always start with `Produkt Highlights`, then short bullets, then prose | Split into `highlights[]` and `text`. |
| No brand field. The first title token works for most products, but there are multi-word brands (`Philips Hue`, `Homematic IP`, `Burg-Wächter`) and 9 titles without a brand | A known-brand prefix list is used. The LLM may fill the gap only if its brand string appears in the title. |
| Variants are bare labels (`1 Stk.`, `Weiß`, `ST64`) with no ids or prices | Stored as-is. |
| **bauhaus.info answers HTTP 403 (Akamai bot protection) to plain HTTP, even for the homepage** | Web fetching is a fallback chain: httpx first, then Gemini's `url_context` tool on the same exact URL. If both fail, the product continues without web data and the failure is recorded. |

Completeness on the real dataset: 641 rich, 269 partial, 33 sparse. **267 products are flagged for web enrichment**: description or attributes missing, or a smart product without any compatibility information.

---

## Architecture

One package per step of the flow, listed so that dependencies only point downward. Each package's `__init__.py`
is its entry point: a docstring describing its flow and `__all__`. Import from the package, never from its modules
(ruff `TID251` enforces this). One class per file; helpers are static methods; internals live in `_private` modules.

```
src/catalog_ingestion/
├── core/             shared infrastructure: settings (pydantic-settings), logging, hashing, GeminiClient
├── vocabulary/       enums and canonical ids: compatibility terms, requirement terms, categories, brands
├── models/           domain/   frozen dataclasses: internal processing models (no I/O)
│                     schemas/  pydantic BaseModels: JSON crossing a boundary (in and out)
│                     mappers/  the only code that converts between the two
├── preparation/      1. ZipLoader -> ProductNormalizer -> Compatibility/RequirementExtractor -> CompletenessAssessor
│                        (ProductPreparer), DatasetProfiler
├── enrichment/       2. ProductEnricher: web/ (fetchers, WebRetriever) -> llm/ (PromptBuilder, LLMEnricher)
│                        -> validation/ (Validator), EnrichmentKey (LLM cache keys)
├── database/         PostgreSQL: records/ (SQLAlchemy ORM), CatalogDatabase (engine, Alembic), migrations/,
│                     PostgresRepository
├── indexing/         3. RetrievalDocumentBuilder, GeminiEmbedder, QdrantCollection, QdrantRepository
├── pipeline/         IngestionPipeline (ingest, reindex), IngestOptions, RunStats
└── cli/              CatalogCli: one class per command
```

Design rules:

- **Two model types.**
  - Pydantic `BaseModel`s (`models/schemas/`) exist only at the business boundaries: the product JSON read from the zip, Gemini's structured output, the enriched product JSON written to PostgreSQL, and the Qdrant payload.
  - Everything in between works on **frozen dataclasses** (`models/domain/`, `slots=True`, tuples instead of lists). Stages return new objects and never mutate.
  - `models/mappers/` is the only code that converts between the two.
- **Settings** come only from environment variables or `.env`, via `pydantic-settings`. There is one settings class per concern (`GeminiSettings`, `PostgresSettings`, `QdrantSettings`, `WebSettings`, `IngestSettings`), each with its own env prefix. Settings are injected by constructor and never read globally.
- **Dependencies point downward.**
  - `pipeline` wires the stages; `cli` builds the components and injects them.
  - Stage packages depend on `models`, `vocabulary` and `core`.
  - `core`, `vocabulary` and `models` depend on no stage, so the phase-2 agent can import them.
- **Deterministic first, LLM second, validation always.** The LLM adds information, but it can never override catalog facts, and nothing it produces is stored without passing validation.

---

## Data flow

```text
products.zip
  │  preparation.ZipLoader       RawProductSchema (pydantic) -> RawProduct (dataclass)
  ▼
normalize                        price, attributes blob, subtitle, description, brand, category slug
  ▼
deterministic extraction         compatibility facts + requirements from catalog attributes/title
  ▼
completeness                     score, level, reasons, needs_web
  ▼
web (only if needs_web)          cache → httpx → Gemini url_context   (never raises)
  ▼
LLM enrichment                   Gemini + response_schema; cached by enrichment_hash
  ▼
validation                       evidence check, canonicalization, catalog precedence, confidence
  ▼
PostgreSQL upsert                products + compatibility + requirements (one transaction)
  ▼
retrieval document               semantic text (EN canonical + DE original terms), doc_hash
  ▼
embedding + Qdrant upsert        only when doc_hash or embedding model changed
```

Web and LLM calls run in a bounded thread pool (`INGEST_CONCURRENCY`) with exponential backoff on 408/429/5xx. All database writes happen on the main thread. A failure in one product is logged and counted, and the run continues.

---

## Enrichment strategy

1. **Deterministic extraction (always).** Attribute keys map to compatibility dimensions through `CompatibilityVocabulary` (`vocabulary/`). Requirements come from `Anforderungen`, `Hinweise` and `Installationshinweis`. The title provides only unambiguous technology names (Matter, WLAN, Zigbee, Bluetooth, Z-Wave).
2. **Completeness check.** A product needs web enrichment when its description or attributes are missing, or when it looks like a smart product but has no compatibility facts.
3. **Web (only when needed, only the dataset URL).**
   - Fetchers run in order:
     1. `HttpxFetcher` (timeouts, HTTP status handling).
     2. `GeminiUrlContextFetcher`: Gemini reads *that exact URL* with the URL context tool.
   - The Gemini result is accepted **only if** `url_context_metadata` reports `URL_RETRIEVAL_STATUS_SUCCESS` for the URL. Text the model could have produced from prior knowledge is rejected.
   - No crawling and no free web search.
   - Results, including failures, are cached in `web_pages`. A cached failure is retried only when the fetcher chain gained a fetcher it never tried (for example, after `GEMINI_API_KEY` was set), or with `--refresh-web`.
4. **LLM structuring (every product, cached).**
   - Gemini receives the catalog entry, the web text if available, and the deterministic facts, each labelled by source. It returns `LLMEnrichmentSchema` via `response_schema`:
     - category (an enum of canonical keys)
     - product type
     - EN/DE summaries
     - key features
     - use cases
     - specs
     - compatibility claims and requirements, each with a verbatim `evidence_quote` and its `source`
   - The prompt forbids guessing and forbids turning "not mentioned" into unsupported or supported. It also spells out the non-equivalences (Siri≠HomeKit, Assistant≠Home, Matter≠Wi-Fi).
5. **Validation (the anti-hallucination gate).**
   - A claim is dropped unless its quote is found (case- and whitespace-insensitive) in the source it cites. If the quote is found in the other source, the claim is re-attributed to that source.
   - The quote must also *mention the claimed value* through its canonical surface forms. A real quote about "Apple Siri" cannot become a HomeKit claim.
   - Values are canonicalized through the vocabulary, which also fixes the dimension if the LLM put a value under the wrong one.
   - Catalog facts win conflicts. The conflict is recorded in `validation_notes`.
   - Specs are kept only if their value (or all their numbers) appear in a source.
   - The LLM brand is accepted only if it appears in the title. The LLM category is used only when the URL slug gives none.
   - Confidence is assigned **by rule**, never taken from the model: catalog attribute 1.0, catalog title 0.95, LLM with a catalog quote 0.9, LLM with a web quote 0.8, LLM-derived descriptive fields 0.6.

If `GEMINI_API_KEY` is missing, or `--skip-llm` is used, the pipeline still produces a complete, deterministic catalog in PostgreSQL. Embeddings need Gemini, so the Qdrant step is skipped and reported.

---

## Compatibility representation

Each fact is one row / object:

```json
{
  "dimension": "voice_assistant",
  "canonical_value": "amazon_alexa",
  "label": "Amazon Alexa",
  "raw_value": "Amazon Alexa",
  "status": "supported",
  "evidence": {"source": "catalog", "text": "Unterstützte Sprachsteuerung: Google Assistant, Amazon Alexa, Apple Siri",
               "field": "attributes.Unterstützte Sprachsteuerung", "url": null},
  "confidence": 1.0,
  "method": "deterministic"
}
```

- **Dimensions**
  - `ecosystem`: platforms and standards, e.g. `matter`, `apple_home`, `google_home`, `samsung_smartthings`, `bosch_smart_home`, `homematic_ip`, `philips_hue`, `ledvance_smart_plus`, `ring`, ...
  - `voice_assistant`: `amazon_alexa`, `google_assistant`, `apple_siri`
  - `protocol`: `wifi`, `zigbee`, `z_wave`, `bluetooth`, `thread`, `ethernet`, `dect`, `io_homecontrol`, `proprietary_rf`
  - `mobile_os`: `ios`, `android`
  - `control`: other control channels without a canonical meaning (vendor apps, remotes), kept raw
- **Non-equivalent concepts stay separate.**
  - Apple Siri is a voice assistant and never implies `apple_home`.
  - Google Assistant never implies `google_home`.
  - Matter is an ecosystem/standard, not a protocol.
  - "Funk" (proprietary radio) is not Wi-Fi.
- **Canonical only when safe.** An unmapped value keeps `canonical_value = null` and its `raw_value`.
- **Status:** `supported | unsupported | unknown`.
  - **Absence of a fact means unknown.**
  - `unsupported` is stored only with explicit negative evidence.
  - Nothing is ever set to `false` or `unsupported` because information is missing.
- **Requirements**

  ```json
  {
    "item": "Homematic IP Access Point",
    "canonical_item": "homematic_ip_access_point",
    "kind": "hub",
    "necessity": "required",
    "alternatives": ["homematic_ip_access_point", "homematic_ccu3", "third_party_partner_solution", "standalone"],
    "evidence": {"source": "catalog", "text": "Hinweise: Der Betrieb erfordert die Anbindung an ...", "field": "attributes.Hinweise"},
    "confidence": 1.0,
    "method": "deterministic"
  }
  ```

  - `kind`: `hub | gateway | app | subscription | network | device | professional_installation | other`
  - `necessity`: `required | required_for_some_features` (e.g. "Für manche Funktionen kann ein Abonnement bei Ring notwendig sein")
  - `alternatives`: any one of them satisfies the requirement. `standalone` means the product also works without a hub.

On the real dataset, the deterministic extraction finds, among others: 23 products that need the Bosch Smart Home Controller, 19 Homematic products with Access Point/CCU3/partner alternatives (3 of them also standalone), 40 Ring products needing a subscription for some features, and 34 products requiring professional installation (useful later for the wiring guardrail).

---

## Provenance

Every stored fact carries:

- `evidence.source`: `catalog` (the original JSON), `web` (the product page), or `llm` (derived without a quote)
- `evidence.field`: e.g. `attributes.Unterstützte Systeme`, `title`, `catalog_text`, `web_page`
- `evidence.url`: for web facts
- `evidence.text`: the verbatim evidence
- `method` (`deterministic` or `llm`) and a rule-based `confidence`

Descriptive fields (summary, use cases, key features, product type, category when LLM-chosen, brand when LLM-chosen) are listed in the product's `provenance` array with their source and method. The **raw input JSON** is stored untouched in `products.raw`, and the unvalidated LLM answer in `products.llm_output`. Validation decisions (dropped claims, conflicts, reassignments) are kept in `validation_notes`.

---

## Database model (PostgreSQL)

**Decision: hybrid.** Anything the agent filters or joins on deterministically gets typed columns or child tables with indexes:

- price, category, brand
- compatibility, as `(dimension, canonical_value, status)`
- requirements

Heterogeneous data (302 attribute keys, specs) and audit copies go into JSONB. Fully normalizing 302 attribute keys would add many tables with no query benefit, while pure JSONB would make compatibility queries fragile and hard to index.

| Table | Purpose |
|---|---|
| `products` | One row per dataset id. Typed filter columns (`title, brand, category, category_slug, product_type, is_smart_home, price_value, price_currency, original_price, ean, summary_en/de, completeness_level/score, web_status, active`). JSONB columns: `raw` (original JSON), `document` (full enriched `CatalogProductSchema`, including the normalized product), `attributes` (`{section: {key: value}}`), `llm_output` (cached LLM answer). Bookkeeping: `raw_hash, document_hash, enrichment_hash, enrichment_model, prompt_version`. |
| `product_compatibility` | One row per fact: `dimension, canonical_value, label, raw_value, status, source, source_field, source_url, evidence, confidence, method`. Indexed on `(dimension, canonical_value, status)`. |
| `product_requirements` | `item, canonical_item, kind, necessity, alternatives TEXT[], source, source_field, source_url, evidence, confidence, method`. |
| `web_pages` | Cache of fetched product pages (success and failure), keyed by URL. |
| `retrieval_documents` | The embedded text per product, its `doc_hash`, and what was last indexed (`indexed_doc_hash`, `embedding_model`). |
| `ingestion_runs` | One row per run: arguments, status (`succeeded`, `partial`, `failed`), final counters. |

### Schema management: SQLAlchemy + Alembic

- **SQLAlchemy 2.0 ORM records** (`database/records/`) define the schema. They are persistence models only: the pipeline works on frozen dataclasses, and `PostgresRepository` (`database/`) converts between the two. The driver is psycopg 3 (`postgresql+psycopg`).
- **Alembic migrations** live in `database/migrations/versions/`. `0001` creates the whole schema above.
- `catalog-ingestion init` and `catalog-ingestion ingest` apply pending migrations automatically (`alembic upgrade head`, run from code, so no `alembic.ini` is needed at runtime).
- A test (`tests/integration/test_migrations.py`) fails if the models and the migrations drift apart.

Changing the schema:

```bash
# 1. edit database/records/
uv run alembic revision --autogenerate -m "add warranty column"   # 2. generate a migration
# 3. review the file in database/migrations/versions/
uv run alembic upgrade head                                       # 4. apply (or just run `init`)
```

Other useful commands: `uv run alembic current`, `uv run alembic history`, `uv run alembic check` (fails if the models have changes that are not in a migration), `uv run alembic downgrade -1`. The Alembic CLI reads the database settings from the same `POSTGRES_*` variables / `.env` as the application.

Example queries for the agent:

```sql
-- Thermostats that support Apple Home, with their hub requirements
SELECT p.id, p.title, p.price_value, r.canonical_item, r.alternatives
FROM products p
JOIN product_compatibility c ON c.product_id = p.id
LEFT JOIN product_requirements r ON r.product_id = p.id AND r.kind IN ('hub', 'gateway')
WHERE p.active AND p.category = 'heating_control'
  AND c.dimension = 'ecosystem' AND c.canonical_value = 'apple_home' AND c.status = 'supported';

-- Any attribute, straight from JSONB
SELECT title, attributes -> 'Technische Daten' ->> 'Batterielaufzeit' FROM products WHERE active;
```

---

## Qdrant model

- **Collection**: `QDRANT_COLLECTION` (default `products`), cosine distance, dimension `GEMINI_EMBEDDING_DIM` (default 768). Point id = the numeric dataset id, or a UUIDv5 of it if not numeric, so the id is stable across runs.
- **Vector**: the Gemini embedding (`task_type=RETRIEVAL_DOCUMENT`, L2-normalized) of the **retrieval document**, not of the JSON. Example:

  ```text
  Product: Homematic IP Fenster- & Türsensor HmIP-SWDO-I
  Brand: Homematic IP
  Category: Door and window sensor (Tür- & Fensterkontakt)
  Details: Weiß, 19 x 166,5 x 12,5 mm, Batteriebetrieben
  Summary: ...                       (LLM, EN)
  Zusammenfassung: ...               (LLM, DE)
  Key features: ...
  Produkt-Highlights:
  - Erkennt Fensterstellung
  ...
  Smart home ecosystems and standards: Homematic IP
  Voice assistants: Amazon Alexa, Apple Siri, Google Assistant
  Connectivity protocols: Proprietary radio (RF)
  Requirements:
  - Homematic IP Access Point - required (or: Homematic Zentrale CCU3, Compatible third-party partner solution)
  Use cases: ...
  Specifications:
  - Geeignet für: Fenster, Tür
  ...
  Price: 58.55 EUR
  ```

  English canonical names sit next to the original German terms, so both English and German queries match.
- **Payload** (for filtering, with payload indexes): `product_id, brand, category, product_type, price, currency, is_smart_home, ecosystems[], voice_assistants[], protocols[], mobile_os[], requirements[], requires_hub, completeness_level, image_url, source_url, doc_hash, embedding_model`. Only `supported` facts appear in the payload lists.

Qdrant never replaces PostgreSQL as the source of truth. Its job is candidate discovery. Exact filtering and the compatibility decision should use PostgreSQL.

---

## How to run

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker, a Gemini API key.

```bash
cd catalog-ingestion
cp .env.example .env              # set GEMINI_API_KEY and POSTGRES_PASSWORD
uv sync

docker compose up -d --wait       # start PostgreSQL + Qdrant
uv run catalog-ingestion init     # Alembic migrations + Qdrant collection (idempotent)
uv run catalog-ingestion ingest   # full ingestion from ../products.zip
uv run catalog-ingestion status   # counts in PostgreSQL and Qdrant
uv run catalog-ingestion search "Thermostat, der mit Apple Home funktioniert" --ecosystem apple_home
```

`uv run python -m catalog_ingestion <command>` works too.

| Command | What it does |
|---|---|
| `init` | Apply the Alembic migrations (`upgrade head`), create the Qdrant collection and its payload indexes. |
| `ingest` | Full pipeline. Options: `--input PATH`, `--force` (ignore caches), `--skip-web` (no network fetches; cached pages are still used), `--skip-llm` (deterministic only; cached LLM output is still used), `--refresh-web`, `--only-product ID` (repeatable), `--limit N`, `--concurrency N`. |
| `reindex` | Rebuild retrieval documents and embeddings from PostgreSQL, with no web or LLM calls. Use `--force` to re-embed everything, `--recreate` to drop and recreate the collection (e.g. after changing the embedding dimension). |
| `analyze` | Dataset profile (no database needed). |
| `search` | Semantic search smoke test with optional `--ecosystem`, `--category`, `--max-price` filters. |
| `status` | Counts per table and completeness level, the Qdrant point count, and the last run. |

Tip for a first try: `uv run catalog-ingestion ingest --limit 20`, then `--only-product 32391327` for the sparse Bosch product that needs web enrichment.

Docker services:

```bash
docker compose up -d --wait   # start
docker compose stop           # stop, containers kept
docker compose restart        # restart
docker compose down           # stop and remove containers, DATA IS KEPT (volumes survive)
docker compose logs -f qdrant # logs
```

---

## Re-running ingestion (idempotency)

Running `ingest` twice on the same zip creates no duplicates and makes **zero** Gemini calls and **zero** embedding calls on the second run:

- **Stable keys**: the dataset `id` is the PostgreSQL primary key and the Qdrant point id. Every write is an upsert.
- **`raw_hash` / `document_hash`**: if neither the input nor the enriched document changed, the product row is not rewritten (`postgres_unchanged`).
- **`enrichment_hash`** = sha256(normalized product + web text + prompt version). If it is unchanged, the cached `llm_output` is re-validated and reused (`llm_cached`). The **API key and the model are not part of it**: switching either continues where the last run stopped, and each output keeps the model that produced it (`enrichment_model`). Changing the product data, the web text or `PromptBuilder.VERSION` re-enriches; `--force` redoes everything.
- **Resuming**: every product is committed as soon as it finishes. An interrupted run (Ctrl-C, crash, quota) loses nothing. The next run logs how many products are already enriched vs pending, processes the already-enriched ones first (instantly), and calls Gemini only for the rest. Ctrl-C marks the run `interrupted`; runs killed without cleanup are marked `abandoned` on the next start.
- **`doc_hash` + embedding model id** (checked against the Qdrant payload): the product is re-embedded only when its retrieval text or the embedding model/dimension changed (`qdrant_unchanged`). `reindex` regenerates embeddings from PostgreSQL without touching the web or the LLM.
- **Modified products** in a new zip are updated. **Removed products** (on a full run, i.e. without `--only-product` or `--limit`) are marked `active = false` in PostgreSQL and deleted from Qdrant.
- `--force` bypasses every cache.

Example summary (second run, deterministic mode):

```text
Loaded                     943
Normalized                 943
Needs web enrichment       267
Validated                  943
Postgres unchanged         943
Qdrant unchanged           943
```

---

## How persistence works / how to reset

`docker-compose.yml` uses **named volumes**:

| Service | Volume | Mounted at |
|---|---|---|
| PostgreSQL 17 | `homepilot-catalog_postgres_data` | `/var/lib/postgresql/data` |
| Qdrant | `homepilot-catalog_qdrant_data` | `/qdrant/storage` |

`docker compose down`, `stop` and `restart` keep both volumes. Find where Docker stores them with `docker volume inspect homepilot-catalog_postgres_data`.

Reset everything and ingest from scratch:

```bash
docker compose down -v            # -v deletes the volumes: ALL catalog data is lost
docker compose up -d --wait
uv run catalog-ingestion init
uv run catalog-ingestion ingest
```

A lighter reset of only the vectors: `uv run catalog-ingestion reindex --recreate`.

To empty only the PostgreSQL tables but keep the volume: `uv run alembic downgrade base && uv run alembic upgrade head`.

A database that was created before Alembic was introduced (by the earlier `schema.sql`) has the identical schema. Adopt it without losing data with `uv run alembic stamp head`.

---

## Tests

```bash
uv run pytest                 # unit + integration
uv run pytest tests/unit      # no Docker needed
uv run ruff check src tests
uv run ty check               # type check (src + tests)
```

- Fixtures are 15 **real products** from the zip (`tests/fixtures/products/`), chosen for their particularities: the sparse Matter product, the discounted price, the dangling attribute line, Homematic OR-requirements, Ring subscription, Siri without HomeKit, Thread/Aqara, Z-Wave/Shelly, and others.
- Unit tests cover:
  - settings, loader
  - price/attribute/subtitle/description/brand parsing, normalization
  - compatibility normalization (Siri≠HomeKit, Assistant≠Home, Matter≠Wi-Fi, raw values kept)
  - requirement extraction, completeness
  - the validator (hallucinated quotes dropped, value-mention check, catalog precedence, no "unsupported" from absence)
  - retrieval documents, schema↔domain round-trip, immutability
  - web fetchers (403, timeouts, fallback, url_context metadata check), LLM output parsing
- Integration tests:
  - `test_pipeline_idempotency.py` runs the whole pipeline against in-memory Qdrant, fake Gemini components and an in-memory repository. It covers: a second run is a no-op, modified and removed products, `--force`, reindex, embedding-model change, web cache.
  - `test_postgres_repository.py` (SQLAlchemy repository) and `test_migrations.py` (models in sync with migrations, idempotent upgrade, downgrade to base and back) run against the Compose PostgreSQL. Each test gets a freshly created `<POSTGRES_DB>_test` database migrated by Alembic. They are skipped automatically when PostgreSQL is not reachable.

No test calls Gemini or the network.

---

## Rate limits and quotas

- **Per-minute limits:** set `GEMINI_REQUESTS_PER_MINUTE` so requests are paced instead of rejected. If a 429 still happens, the client waits the `retryDelay` the API returns, then retries.
- **Per-day limits** can't be fixed by waiting. On the first per-day 429, the run stops calling the LLM (`llm_skipped_quota` in the summary) and finishes with deterministic data only.
- **Web pages:** a page read that failed because of quota, a timeout or a 5xx is not cached (`web_transient_failures_not_cached`).
- **Next run:** run `ingest` again when the quota resets. Only products without LLM output, and pages whose failure was transient, are retried. Everything already enriched is reused from the cache.

## Configuration

All configuration comes from environment variables or `.env` (see `.env.example`). Never commit `.env`.

| Variable | Default | Notes |
|---|---|---|
| `GEMINI_API_KEY` | none | Required for LLM enrichment, url_context fetching and embeddings. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Structuring model. Checked at startup (a wrong name fails immediately). Changing it does not redo already enriched products (use `--force`). |
| `GEMINI_EMBEDDING_MODEL` / `GEMINI_EMBEDDING_DIM` | `gemini-embedding-001` / `768` | Changing either one re-embeds. Changing the dimension needs `reindex --recreate`. |
| `GEMINI_REQUESTS_PER_MINUTE` / `GEMINI_EMBEDDING_REQUESTS_PER_MINUTE` | unset (no pacing) | Client-side pacing shared by all workers. Set it just below your quota on the free tier (e.g. `14` for 15 RPM). Page reading through `url_context` counts against the same generation quota. |
| `GEMINI_MAX_RETRIES` | `8` | Retries for 408/429/5xx. On 429 the client waits the delay the API asks for (`retryDelay`). |
| `POSTGRES_HOST/PORT/DB/USER/PASSWORD` | `localhost/5432/catalog/catalog/...` | Also read by `docker-compose.yml`. |
| `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION` | `http://localhost:6333`, none, `products` | The API key is only needed for a remote/secured Qdrant. |
| `WEB_ENABLED`, `WEB_TIMEOUT_SECONDS`, `WEB_USER_AGENT`, `WEB_MAX_TEXT_CHARS` | `true`, `15`, browser UA, `20000` | |
| `INGEST_INPUT_PATH`, `INGEST_CONCURRENCY` | `../products.zip`, `4` | |

---

## Notes for the agent

- `catalog_ingestion.models` (dataclasses and the `CatalogProductSchema` JSON contract) and `catalog_ingestion.vocabulary` (enums, canonical ids and labels) depend on no pipeline stage.
- A deterministic compatibility check is a query over `product_compatibility` (`status = 'supported'`) and `product_requirements` (`alternatives`). Treat a missing row as **unknown**, never as incompatible or compatible.
- `requirements` with `kind = 'professional_installation'` identify products whose installation involves electrical work. The agent's wiring guardrail can use this.
- `products.document` holds the complete enriched product in one JSON document, which is convenient for comparison prompts.

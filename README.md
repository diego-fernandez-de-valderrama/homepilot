# HomePilot Smart Home Agent (phase 2)

A conversational shopping assistant for smart home products, built with **Google ADK + Gemini**. It answers in English or German. It recommends, filters, compares and checks compatibility of products from the catalog built by [`../catalog-ingestion`](../catalog-ingestion) (phase 1).

Gemini understands the request, picks tools and writes the answer. **It is never the source of truth.** Every price, spec, compatibility statement, requirement and piece of evidence comes from PostgreSQL (structured truth) or Qdrant (semantic discovery only), through deterministic code.

---

## Contents

1. [Architecture](#architecture)
2. [Relationship with catalog-ingestion](#relationship-with-catalog-ingestion)
3. [Tools](#tools)
4. [Compatibility](#compatibility)
5. [Recommendation flow and upselling](#recommendation-flow-and-upselling)
6. [Comparison and evidence](#comparison-and-evidence)
7. [Models: SQLAlchemy / Pydantic / dataclasses](#models-sqlalchemy--pydantic--dataclasses)
8. [Bilingual support, conversation state, guardrails](#bilingual-support-conversation-state-guardrails)
9. [Configuration](#configuration)
10. [How to run](#how-to-run)
11. [Tests](#tests)
12. [Example conversations](#example-conversations)
13. [Troubleshooting](#troubleshooting)
14. [Next iteration](#next-iteration)

---

## Architecture

```
Streamlit (ui/streamlit_app.py)          presentation only, calls AgentService.chat()
        │
AgentService + LlmAgent (agent/)         one ADK agent, Gemini, in-memory sessions
        │
Tools (tools/)                           8 small function tools: resolve input, call a service, return JSON
        │
Services (services/)                     vocabulary, retrieval, compatibility, ranking,
        │                                recommendation, comparison, evidence (pure domain logic)
        │
Repositories (repositories/)
  ├── postgres.py  CatalogRepository     SQLAlchemy, read-only sessions, ORM -> Pydantic
  └── qdrant.py    QdrantIndex           official qdrant-client, returns ids + scores only
        │
PostgreSQL + Qdrant                      the containers of catalog-ingestion (no second instance)
```

```
src/smart_home_agent/
├── config.py            AgentSettings (AGENT_*) + reused GEMINI_/POSTGRES_/QDRANT_ settings
├── container.py         composition root (engine, Qdrant client, embedder, services)
├── __main__.py          `check`, `smoke`, `chat` commands
├── agent/               orchestrator.py, prompts.py (rules + guardrails), state.py, language.py, trace.py
├── tools/               recommend.py, catalog.py (search/filter/get), compatibility.py, comparison.py,
│                        evidence.py, preferences.py, _common.py (error handling, input resolution)
├── services/            vocabulary.py, retrieval.py, filtering.py, compatibility.py, ranking.py,
│                        recommendation.py, comparison.py, evidence.py
├── repositories/        postgres.py, qdrant.py
├── models/              product.py, evidence.py, search.py, compatibility.py, comparison.py, recommendation.py
└── ui/streamlit_app.py
```

There is a single agent (no multi-agent setup). The layers only call downward: the agent never touches the database, tools never run SQL, and Streamlit holds no business logic.

---

## Relationship with catalog-ingestion

`catalog-ingestion` is a **uv path dependency** (`[tool.uv.sources]`, editable). The agent imports from it instead of copying:

| Reused from `catalog_ingestion` | Used for |
|---|---|
| `storage.postgres.models` (`ProductRecord`, `CompatibilityRecord`, `RequirementRecord`) | The ORM. Migrations stay owned by catalog-ingestion (Alembic). |
| `storage.postgres.engine.create_db_engine / create_session_factory` | Engine and sessions. The agent adds `postgresql_readonly=True`, so it cannot write. |
| `core.settings.GeminiSettings / PostgresSettings / QdrantSettings` | Same env variables, no duplicates. |
| `vocabulary.compatibility / categories / requirements` | Canonical ids (`apple_home`, `google_home`, `zigbee`, ...), aliases, labels, categories, hubs. |
| `domain.enums` (`FactStatus`, `Dimension`, `FactSource`, ...) | Status/source/dimension values in the business models. |
| `schemas.catalog_product.CatalogProductSchema` | Parses `products.document` (specs, features, provenance). |
| `llm.client.GeminiClient` + `retrieval.embeddings.GeminiEmbedder` | Query embeddings with the **same** model, dimension, task type and L2 normalization as the indexed documents. |
| `storage.qdrant.collection.create_client`, `storage.qdrant.repository.point_id` | Qdrant client and point ids. |

Data used (read-only):
- PostgreSQL tables: `products`, `product_compatibility`, `product_requirements`.
- Qdrant collection: `products` (768-dim cosine; payload used only for the category pre-filter).

At startup the agent compares the embedding model stored in the Qdrant payload with the configured one and warns on a mismatch.

---

## Tools

| Tool | When the agent uses it | Backed by |
|---|---|---|
| `recommend_products(need, category?, max_price?, min_price?, brands?, must_support?, owned_devices?, limit?)` | "I need X" | Full pipeline in code (see below) |
| `search_products(query, category?, limit?)` | Open exploration | Qdrant, then hydrated from PostgreSQL; labeled unverified |
| `filter_products(category?, min/max_price?, brands?, supports?, product_type_contains?, sort?, limit?)` | Exact lists ("Zigbee plugs under 30 EUR") | PostgreSQL |
| `get_product(product_id)` | Details | PostgreSQL |
| `check_compatibility(product_ids, requirements, owned_devices?)` | "Does X work with Y?" | Compatibility service |
| `compare_products(product_ids)` | 2-4 products side by side | Comparison service |
| `get_evidence(product_id, topic)` | "How do you know?" | Provenance stored by catalog-ingestion |
| `remember_preferences(language?, ecosystems?, protocols?, budget_max?, category?, owned_devices?, requirements?)` | User describes their setup | ADK session state |

**Design choice: a composite `recommend_products` tool next to the atomic ones.** With only atomic tools, Gemini would have to chain search, filter, compatibility and ranking itself, passing ids between calls. The rule "compatibility before upselling" would then rest on the prompt alone. The composite tool enforces the order in code; the atomic tools remain for exploration and follow-up questions.

Every tool follows the same contract:
- **Input:** primitive parameters, so ADK builds clean JSON schemas. Free text such as "HomeKit", "Thermostat", "Hue Bridge" is resolved to canonical ids in code, then validated into Pydantic models.
- **Output:** a JSON dict with a `status` field:

| Status | Meaning |
|---|---|
| `ok` | Success. |
| `needs_clarification` | Ambiguous input, for example "Apple" or "Google"; `options` lists the choices. |
| `unrecognized` | The value maps to no known term. |
| `not_found` | Unknown product id. |
| `invalid_input` | Validation failed. |
| `error` | Unexpected failure (logged). |

---

## Compatibility

Compatibility is decided in `services/compatibility.py` from the `product_compatibility` rows. Gemini never decides it.

| Facts for the requested canonical value | Status |
|---|---|
| at least one `supported`, no `unsupported` | **supported** (with all evidence) |
| only `unsupported` (explicit negative evidence) | **unsupported** |
| both | **unknown** (note: contradicting evidence) |
| none | **unknown** (note: the catalog has no information) |

**Unknown stays unknown.** Missing data never becomes supported or unsupported, and the agent says "I can't confirm ..." rather than "not compatible". This matters on the real data: the catalog contains only 3 `unsupported` facts, so "not listed" almost always means unknown.

Concepts are never merged. The vocabulary of catalog-ingestion keeps these separate, and the agent adds only aliases that point to existing ids:
- Siri (`apple_siri`, voice assistant) is not HomeKit (`apple_home`, ecosystem).
- Google Assistant is not Google Home.
- Matter is a standard (ecosystem), not a protocol.
- Zigbee is not Matter, and Wi-Fi is not Matter.

When a user asks for Google Home and a product only lists Google Assistant, the result stays `unknown` with an explanatory note. Example from the real catalog: 30 thermostats support Google Assistant, but only 2 confirm Google Home.

Requirements are reported next to the compatibility status and do not change it:
- **Hub/gateway requirements** get a status:
  - `satisfied`: the user owns one of the `alternatives`, or `standalone` is allowed;
  - `missing`: owned devices are known and none match;
  - `unverified`: owned devices were not stated.
- **Other requirements** (app, network, subscription) are informational.
- `requires_professional_installation` comes from `kind = professional_installation`.

`overall` is:
- `unsupported` if any requested term is unsupported;
- `supported` if all are supported;
- `unknown` otherwise.

---

## Recommendation flow and upselling

```
need + hard constraints (category, price range, brands, must_support, owned hubs)
  │
  ├─ Qdrant: semantic top-K (category pre-filter for recall only)
  ├─ PostgreSQL: structured matches (category + price + brand + supported facts)
  │     (so a compatible product is never lost because of its embedding rank;
  │      Qdrant then scores these ids too)
  ▼
hydrate every candidate from PostgreSQL (only these values are used from here on)
  ▼
hard filters (category, price, brand; unknown price never passes a budget)
  ▼
compatibility gate:  supported -> confirmed | unknown -> unconfirmed | unsupported -> excluded
  ▼
ranking (confirmed; price-neutral)
  ▼
upselling (at most one alternative)
  ▼
Gemini writes the answer from this result
```

**Ranking** (`services/ranking.py`, internal `RankingCandidate` dataclass) scores each product as:
- 0.6 × semantic relevance (normalized);
- 0.15 × product-type match with the need (pushes a "valve adapter" below "radiator thermostat");
- 0.1 × data completeness;
- 0.15 × number of confirmed capabilities.

Price is not part of the score. The best match is chosen on fit.

**Upselling** considers only `confirmed` products. An upsell candidate must meet all of these conditions:
- same category and compatible product type as the best match (a radiator thermostat is not upsold to an underfloor room thermostat);
- more expensive, but **never above `max_price`**;
- at least `AGENT_UPSELL_MIN_RELEVANCE` × the best match's relevance;
- a **strict superset** of the best match's confirmed capabilities.

Its `upgrade_reasons` are computed from the data (for example "Also supports Matter (confirmed in the catalog)" and "Costs 40.00 EUR more than ..."). The prompt only allows those reasons.

All confirmed alternatives are still returned, so cheaper valid options are never hidden. Unconfirmed products are returned separately and may only be mentioned as "compatibility not confirmed".

---

## Comparison and evidence

`compare_products` builds rows from PostgreSQL for 2-4 products:
- general: price, original price, brand, category, product type, data completeness;
- compatibility: every ecosystem, voice assistant or protocol any of them mentions, shown as supported / unsupported / "unknown (not listed)" per product;
- requirements and professional installation;
- specs, aligned by name, with "not listed" for missing values;
- key features;
- `only_supported_by`: capabilities that only one of the products confirms.

Retrieved text is never used for comparison.

`get_evidence` returns stored provenance only:
- **Compatibility facts and requirements:** source (`catalog` / `web` / `llm`), field, URL, verbatim text, method, confidence.
- **Price and title:** the original catalog value.
- **Descriptive fields** (summary, product type, key features, specs, ...): the `provenance` entries recorded by catalog-ingestion.
- **Any catalog attribute** by name (for example `Schutzart`).

---

## Models: SQLAlchemy / Pydantic / dataclasses

| Kind | Where | Purpose |
|---|---|---|
| SQLAlchemy ORM | `catalog_ingestion.storage.postgres.models` (reused) | Persistence only, used exclusively inside `repositories/postgres.py` |
| Pydantic `BaseModel` | `models/*`, `agent/state.py`, `agent/trace.py` | Business models and contracts: `Product`, `ProductSummary`, `CompatibilityFact`, `Evidence`, `ProductFilter`, `SearchResult`, `CompatibilityResult`, `ComparisonResult`, `RecommendationRequest`, `Recommendation`, `UpsellSuggestion`, `SessionState`, `AgentReply` |
| `dataclass` | `SearchCandidate`, `RankingCandidate`, `ResolvedTerm`, `Services`, `Settings` | Internal processing and wiring, never exposed to the model |

The repository maps ORM → Pydantic (`to_product`). ORM objects never reach services, tools or the agent.

---

## Bilingual support, conversation state, guardrails

**Language**
- Gemini replies in the language of the latest user message.
- Because the catalog data is German, the model tends to drift into German. To prevent this, `agent/language.py` detects EN/DE per turn with a small word-list heuristic. The result is passed as a per-turn state value, and the instruction turns it into an explicit "reply in English/German" line. If the heuristic is unsure, the model decides alone.
- Catalog values (titles, attributes) are never translated destructively. `summary_en` / `summary_de` are chosen by language. Retrieval works for both languages because the indexed documents contain English canonical names and the German catalog text.

**Session state** (`SessionState`, stored in the ADK in-memory session under `homepilot`) holds:
- `language`, `user_ecosystems`, `user_protocols`, `owned_devices`, `budget_max`, `requirements`;
- `current_category`, `last_search`, `candidate_products`, `selected_products`, `comparison_products`.

Tools update it automatically. `remember_preferences` stores what the user said about their home. `recommend_products` uses the stored ecosystems, protocols and budget as defaults and reports them in `applied_from_session`. The instruction includes the known state every turn. Nothing is persisted: there are no user profiles or accounts.

**Guardrails** are prompt-level (`agent/prompts.py`):
- Firm refusal of wiring, electrical installation and mains-voltage instructions, with a referral to a qualified electrician (Elektrofachkraft).
- Products with `requires_professional_installation` are flagged in the answer.
- Off-topic questions are redirected to smart home topics.
- Facts only from tools; no invented advantages.

---

## Configuration

Copy `.env.example` to `.env` in this directory. `GEMINI_*`, `POSTGRES_*` and `QDRANT_*` are **the same variables as in `../catalog-ingestion/.env`** (read by the reused settings classes). Use the same values.

| Variable | Default | Notes |
|---|---|---|
| `GEMINI_API_KEY` | none | Required: chat model and query embeddings. |
| `GEMINI_EMBEDDING_MODEL` / `GEMINI_EMBEDDING_DIM` | `gemini-embedding-001` / `768` | Must match the Qdrant index (a warning is logged on mismatch). |
| `GEMINI_MAX_RETRIES`, `GEMINI_EMBEDDING_REQUESTS_PER_MINUTE` | `8`, unset | Retry/pacing for embedding calls. |
| `POSTGRES_HOST/PORT/DB/USER/PASSWORD` | `localhost/5432/catalog/catalog/...` | The catalog-ingestion database. |
| `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION` | `http://localhost:6333`, none, `products` | The catalog-ingestion collection. |
| `AGENT_MODEL` | `gemini-2.5-flash` | Chat/orchestration model (separate from `GEMINI_MODEL`, the enrichment model). |
| `AGENT_TEMPERATURE` | `0.2` | |
| `AGENT_CANDIDATE_POOL` | `50` | Candidates per retrieval path before filtering. |
| `AGENT_UPSELL_MIN_RELEVANCE` | `0.75` | An upsell must reach this share of the best match's relevance. |

The API key is passed to ADK explicitly (`Gemini(client_kwargs={"api_key": ...})`), so no `GOOGLE_API_KEY` export is needed.

---

## How to run

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker, a Gemini API key.

```bash
# 1. Infrastructure (PostgreSQL + Qdrant) - owned by catalog-ingestion, not duplicated here
cd catalog-ingestion
cp .env.example .env                 # GEMINI_API_KEY, POSTGRES_PASSWORD
uv sync
docker compose up -d --wait

# 2. Catalog (once; re-runs are idempotent)
uv run catalog-ingestion init
uv run catalog-ingestion ingest
uv run catalog-ingestion status

# 3. Agent
cd ../smart-home-agent
cp .env.example .env                 # same GEMINI/POSTGRES/QDRANT values as above
uv sync
uv run python -m smart_home_agent check    # PostgreSQL/Qdrant counts + embedding model check
uv run python -m smart_home_agent smoke    # recommendation pipeline only (1 embedding call, no chat model)
uv run streamlit run src/smart_home_agent/ui/streamlit_app.py
```

Run commands from the `smart-home-agent` directory so `.env` is found.

- **Streamlit:** open http://localhost:8501. The sidebar has a **Developer panel** toggle, off by default. When on, it shows under each answer: language, intent, tools called, search queries, candidates, compatibility results, selected products, session state and the raw tool calls. **New conversation** resets the session.
- **Terminal chat:** `uv run python -m smart_home_agent chat` (one message per line, Ctrl-D to quit).

No extra Docker Compose file is needed: the agent runs locally with uv and connects to the `homepilot-catalog` containers on localhost.

---

## Tests

```bash
uv run pytest                  # everything (integration tests auto-skip if PostgreSQL/Qdrant are down)
uv run pytest -m "not integration"
uv run pytest -m integration   # live, read-only checks against the real catalog
uv run ruff check . && uv run ruff format --check .
uv run deptry .                # every imported package is declared, none is unused
```

**Unit tests** use in-memory fakes (`tests/fakes.py`) and never call Gemini:

| Area | What is tested |
|---|---|
| Compatibility | supported / unsupported / unknown; missing data is neither unsupported nor supported; contradicting evidence; Siri ≠ HomeKit; Google Assistant ≠ Google Home; hub requirements; professional installation. |
| Filtering | Price, category, brand, protocols, invalid ranges. |
| Comparison | Structured rows, "not listed", unknown vs unsupported, capability differences, input validation. |
| Ranking and recommendation | Compatibility gate before upselling; the budget is never exceeded; no upsell without strictly more capabilities or across product types; structured matches found even when semantic search misses them. |
| Tools | ADK declarations, input/output contracts, error statuses, session state. |
| Agent | Offline build, instruction content, language detection, trace. |
| Vocabulary and evidence | Term resolution and provenance lookup. |

**Integration tests** check against the live catalog:
- ORM → Pydantic mapping;
- SQL filters agree with the compatibility service;
- Google Assistant products are unknown for Google Home, never unsupported;
- sessions are really read-only;
- Qdrant search and by-id scoring (using a stored vector, so no Gemini call is needed).

---

## Example conversations

These are real runs against the catalog, shortened.

```
User:  I need a thermostat compatible with Google Home, max 150 euros.
Agent: I found one thermostat that is confirmed to work with Google Home within your budget:
       Ledvance Smart+ WiFi Heizkörper-Thermostat 1 Stück (54.95 EUR) ...
       I also found other thermostats that support Google Assistant, but I can't confirm
       their compatibility with Google Home from the catalog data: Bosch Smart Home
       Heizkörper-Thermostat II (55 EUR), ...
       [tools: recommend_products]

User:  Und welches davon funktioniert auch mit Matter?
Agent: Ich kann die Matter-Kompatibilität für keines der genannten Thermostate anhand der
       Katalogdaten bestätigen. Für alle Produkte ist der Status "unbekannt" ...
       [tools: check_compatibility]

User:  How do I wire the thermostat to my mains?
Agent: I cannot provide instructions for electrical installation or wiring. Working with mains
       voltage must always be done by a qualified electrician ("Elektrofachkraft") ...

User:  What is the capital of France?
Agent: I can only help with smart home products and related topics ...

User:  Compare 30173510 and 30387250
Agent: Bosch Smart Home Heizkörper-Thermostat II (55.00 EUR, radiator thermostat) vs
       Bosch Smart Home Raumthermostat II (69.95 EUR, room thermostat) ... Both require a
       Bosch Smart Home Controller ...
       [tools: compare_products]
```

`smoke` output for "Thermostat für Google Home, max 150 EUR":
- Best match: `32332362` (Ledvance, 54.95 EUR).
- The other Google Home thermostat (Osram, 164.95 EUR) is excluded by the budget.
- Assistant-only thermostats are `unconfirmed`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `GEMINI_API_KEY is not set` at startup | Set it in `smart-home-agent/.env` and run from that directory. |
| `connection refused` on 5432 / 6333 | `cd ../catalog-ingestion && docker compose up -d --wait`. |
| Integration tests skipped | Infrastructure is down or the catalog is empty: run catalog-ingestion `init` + `ingest`. |
| Warning "Qdrant vectors were built with ... but queries use ..." | Align `GEMINI_EMBEDDING_MODEL` / `GEMINI_EMBEDDING_DIM` with catalog-ingestion, or run `catalog-ingestion reindex`. |
| `404 model not found` from the chat model | Check `AGENT_MODEL` against the models available to your key. |
| 429 / quota errors | Free-tier limits; wait, or set `GEMINI_EMBEDDING_REQUESTS_PER_MINUTE`. The UI shows the error and keeps the conversation. |
| Answers in the wrong language | Very short or mixed messages give no language hint; the model then follows the conversation. Ask explicitly ("answer in English"). |
| `UserWarning: [EXPERIMENTAL] ... JSON_SCHEMA_FOR_FUNC_DECL` | Emitted by ADK 2.x when building tool schemas. It is filtered in `smart_home_agent/agent/__init__.py`; if you still see it, the code imported ADK tools without importing `smart_home_agent.agent` first. Harmless. |

---

## Next iteration

- **Extract a shared package.** Split `homepilot-catalog-core` (ORM, vocabulary, enums, schemas, embedder) out of catalog-ingestion. The agent would then not install ingestion-only dependencies (typer, bs4, ...).
- **Container image.** Add one for the agent (it needs the shared package first) and a compose service joining the `homepilot-catalog` network.
- **Evaluation set.** Build EN/DE conversations with expected tool calls and compatibility outcomes, using ADK evaluation, as regression tests for the prompt.
- **Streaming responses** in Streamlit and a tool-call timeline (`st.status(type="step")`).
- **Better ranking signals.** Price tiers per category and margin data, if the business provides them. They must stay behind the compatibility gate.
- **Category-aware product-type taxonomy.** The LLM `product_type` is free text, which limits type matching and upsell eligibility.
- **Model-level guardrails** (a before-model callback or classifier) in addition to the prompt rules.
- **Persistent sessions** (ADK `DatabaseSessionService`) once user profiles are in scope.

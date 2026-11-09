# HomePilot

A bilingual (English/German) conversational shopping assistant for smart home products, built with Google ADK and Gemini, on top of a PostgreSQL + Qdrant product catalog.

| Project | What it does |
|---|---|
| [`catalog-ingestion`](catalog-ingestion) | Loads the product export, normalizes and enriches each product (Gemini with structured output and evidence validation), stores it in PostgreSQL and indexes it in Qdrant. |
| [`smart-home-agent`](smart-home-agent) | The conversational agent (Google ADK + Gemini, Streamlit UI): recommendation with compatibility checks, comparison, upselling, customer memory, semantic guardrails and evaluation harnesses. |

## Dataset

`products.zip` at the repository root is the product export used by the ingestion: 943 smart home products, one JSON file per product (German catalog data). `catalog-ingestion` reads it from `../products.zip` by default.

## Run it locally

### Step 1: Infrastructure

```bash
cd catalog-ingestion
cp .env.example .env              # set GEMINI_API_KEY and POSTGRES_PASSWORD
uv sync
docker compose up -d --wait       # PostgreSQL + Qdrant
```

### Step 2: Dependencies of the agent

```bash
cd ../smart-home-agent
cp .env.example .env              # same GEMINI/POSTGRES/QDRANT values
uv sync
```

### Step 3: Build the catalog

```bash
cd ../catalog-ingestion
uv run catalog-ingestion init
uv run catalog-ingestion ingest   # reads ../products.zip
uv run catalog-ingestion status
```

### Step 4: Start the agent

```bash
cd ../smart-home-agent
uv run python -m smart_home_agent init-memory
uv run streamlit run src/smart_home_agent/ui/streamlit_app.py
```

See each project's README for details, tests and evaluations.
